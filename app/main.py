"""
Main application entry point for the LOUD Platform Licensing System.
"""

import logging
import os
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.database import SessionLocal, engine
from app.exceptions import (
    AuthenticationException,
    AuthorizationException,
    BusinessRuleException,
    DatabaseException,
    LicenseServerException,
    ResourceNotFoundError,
    ValidationException,
)
from app.models import AdminUser, Plan, Product
from app.routers import (
    admin,
    analytics,
    auth,
    customers,
    devices,
    extensions,
    licenses,
    plans,
    products,
)
from app.security import hash_password, verify_password
from app.services.admin_service import AdminService
from app.utils.responses import error_response


logger = logging.getLogger(__name__)


def _validate_database_ready() -> None:
    """Ensure the database is available and all tables exist safely before serving requests."""
    try:
        from app.database import Base, engine, log_safe_database_info
        log_safe_database_info()

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        # Non-destructive table creation: CREATE TABLE IF NOT EXISTS
        Base.metadata.create_all(bind=engine)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE licenses SET activated_device_count = "
                    "(SELECT COUNT(*) FROM devices WHERE devices.license_id = licenses.id)"
                )
            )
        # Migrate baseline data from SQLite if target database is empty
        _ensure_baseline_data_migrated()
    except SQLAlchemyError as exc:
        raise RuntimeError(
            "Database is unavailable during startup. "
            "Ensure the database server is running."
        ) from exc


def _ensure_baseline_data_migrated() -> None:
    """
    Safely and idempotently migrate existing records from the SQLite repository seed
    into the production database (Neon PostgreSQL) if the target database has no customers.
    Preserves exact IDs, relationships, and created timestamps.
    Never overwrites or duplicates existing records.
    """
    import sqlite3
    from app.database import engine

    try:
        with engine.connect() as conn:
            cust_count = conn.execute(text("SELECT COUNT(*) FROM customers")).scalar()
            if cust_count and cust_count > 0:
                logger.info("Target database already contains %d customers; baseline seed migration skipped.", cust_count)
                return

        # Locate best available SQLite seed file
        seed_candidates = [
            os.path.normpath(os.path.join(settings.PROJECT_ROOT, "licenses.db")),
            os.path.normpath(os.path.join(settings.PROJECT_ROOT, "licenses.db.backup")),
            os.path.normpath(os.path.join(settings.PROJECT_ROOT, "licenses.db.safe_backup")),
        ]
        best_seed = None
        for cand in seed_candidates:
            if os.path.isfile(cand) and os.path.getsize(cand) > 0:
                best_seed = cand
                break

        if not best_seed:
            logger.info("No SQLite baseline seed found to migrate.")
            return

        logger.info("Migrating baseline records from SQLite seed: %s", best_seed)
        sconn = sqlite3.connect(f"file:{best_seed}?mode=ro", uri=True)
        scur = sconn.cursor()

        tables_to_migrate = [
            "admin_users",
            "products",
            "plans",
            "customers",
            "licenses",
            "devices",
            "activity_logs",
        ]

        with engine.begin() as dest_conn:
            for table_name in tables_to_migrate:
                try:
                    scur.execute(f"PRAGMA table_info({table_name})")
                    col_info = scur.fetchall()
                    if not col_info:
                        continue
                    col_names = [c[1] for c in col_info]

                    cols_str = ", ".join(f'"{c}"' for c in col_names)
                    scur.execute(f"SELECT {cols_str} FROM {table_name}")
                    rows = scur.fetchall()
                    if not rows:
                        continue

                    placeholders = ", ".join(f":{c}" for c in col_names)
                    if engine.dialect.name == "postgresql":
                        insert_stmt = text(
                            f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders}) "
                            f"ON CONFLICT (id) DO NOTHING"
                        )
                    else:
                        insert_stmt = text(
                            f"INSERT OR IGNORE INTO {table_name} ({cols_str}) VALUES ({placeholders})"
                        )

                    row_dicts = [dict(zip(col_names, r)) for r in rows]
                    dest_conn.execute(insert_stmt, row_dicts)
                    logger.info("Migrated %d rows into '%s'", len(row_dicts), table_name)

                except Exception as table_err:
                    logger.warning("Migration notice for table '%s': %s", table_name, table_err)

            # In PostgreSQL, synchronize primary key sequences after inserting explicit IDs
            if engine.dialect.name == "postgresql":
                for table_name in tables_to_migrate:
                    try:
                        dest_conn.execute(
                            text(
                                f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                                f"coalesce((SELECT MAX(id) FROM {table_name}), 1))"
                            )
                        )
                    except Exception as seq_err:
                        logger.debug("Sequence synchronization for '%s': %s", table_name, seq_err)

        sconn.close()
        logger.info("Baseline seed migration to persistent database completed successfully.")

    except Exception as exc:
        logger.warning("Baseline seed migration notice: %s", exc)


def _ensure_initial_admin() -> None:
    """Create or synchronize the initial owner admin from environment settings."""
    if not settings.ADMIN_USERNAME or not settings.ADMIN_PASSWORD:
        logger.warning(
            "ADMIN_USERNAME or ADMIN_PASSWORD is not configured; skipping initial admin seeding."
        )
        return

    db = SessionLocal()
    try:
        admin_user = (
            db.query(AdminUser)
            .filter(AdminUser.username == settings.ADMIN_USERNAME)
            .first()
        )
        if admin_user is not None:
            if not verify_password(settings.ADMIN_PASSWORD, admin_user.password_hash):
                admin_user.password_hash = hash_password(settings.ADMIN_PASSWORD)
                db.commit()
                logger.info(
                    "Synchronized password hash for admin '%s' with environment settings.",
                    admin_user.username,
                )
            return

        AdminService.create_admin(
            db,
            username=settings.ADMIN_USERNAME,
            password=settings.ADMIN_PASSWORD,
            role="owner",
        )
        logger.info("Initial admin user created successfully from environment settings.")
    except SQLAlchemyError as exc:
        logger.exception("Failed to create/synchronize the initial admin user: %s", exc)
    finally:
        db.close()


def _ensure_default_product() -> None:
    """Ensure the default product (LOUD Premium) exists with its designated API key."""
    db = SessionLocal()
    try:
        prod = db.query(Product).filter(Product.id == 1).first()
        default_key = "lp_AqzVY9OZc1ZyVSYgfc-J6XLxff9lejdLtzClROBrUgU"
        if prod:
            if prod.api_key != default_key:
                prod.api_key = default_key
                prod.status = "active"
                db.commit()
                logger.info("Default product API key reset to: %s", default_key)
        else:
            new_prod = Product(
                id=1,
                name="LOUD Premium",
                slug="loud-premium",
                version="1.0.0",
                api_key=default_key,
                status="active"
            )
            db.add(new_prod)
            db.commit()
            logger.info("Created default product: LOUD Premium with API key: %s", default_key)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to ensure default product: %s", exc)
    finally:
        db.close()


def _ensure_default_plans() -> None:
    """Ensure standard plans exist if table is empty."""
    db = SessionLocal()
    try:
        plan_count = db.query(Plan).count()
        if plan_count == 0:
            default_plans = [
                Plan(id=1, name="Trial", duration_days=1, max_devices=1, price=0.0, status="active"),
                Plan(id=2, name="Weekly", duration_days=7, max_devices=1, price=5.0, status="active"),
                Plan(id=3, name="Monthly", duration_days=30, max_devices=2, price=15.0, status="active"),
                Plan(id=4, name="Lifetime", duration_days=99999, max_devices=5, price=99.0, status="active"),
                Plan(id=5, name="Ultra", duration_days=90, max_devices=3, price=6.0, status="active"),
            ]
            db.add_all(default_plans)
            db.commit()
            logger.info("Default billing plans initialized successfully.")
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("Failed to initialize default plans: %s", exc)
    finally:
        db.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description=(
        "Professional multi-product licensing platform for "
        "browser extensions and desktop applications."
    ),
)


# --------------------------------------------------------------------
# Startup Event
# --------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Validate database connectivity, create tables non-destructively, seed initial admin, and ensure defaults."""
    _validate_database_ready()
    _ensure_initial_admin()
    _ensure_default_product()
    _ensure_default_plans()

    # Log database persistence status
    if settings.DATABASE_URL.startswith("sqlite"):
        logger.info("Database persistence: Local SQLite storage (development mode)")
    else:
        logger.info("Database persistence: Neon PostgreSQL PERSISTENT STORAGE ACTIVE")

    logger.info("LOUD License Server started successfully.")


# --------------------------------------------------------------------
# Middleware
# --------------------------------------------------------------------

DEFAULT_ALLOWED_ORIGINS = [
    "https://louders-official.onrender.com",
    "http://localhost:8000",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
env_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
cors_origins = list(dict.fromkeys(DEFAULT_ALLOWED_ORIGINS + env_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"^chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,
)

trusted_hosts = [
    host.strip()
    for host in os.getenv("TRUSTED_HOSTS", "").split(",")
    if host.strip()
]

if trusted_hosts:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=trusted_hosts,
    )


@app.middleware("http")
async def add_security_headers_and_logging(request: Request, call_next):
    """Add common security headers and request logging."""

    start_time = perf_counter()

    response = await call_next(request)

    process_time = perf_counter() - start_time

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = (
        "geolocation=(), microphone=(), camera=()"
    )

    if os.getenv("HTTPS_DEPLOYMENT", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    logger.info(
        "%s %s %s %.3fs",
        request.method,
        request.url.path,
        response.status_code,
        process_time,
    )

    return response


# --------------------------------------------------------------------
# Routers
# --------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(customers.router)
app.include_router(licenses.router)
app.include_router(devices.router)
app.include_router(plans.router)
app.include_router(admin.router)
app.include_router(admin.alias_router)
app.include_router(extensions.router)
app.include_router(analytics.router)



# --------------------------------------------------------------------
# Exception Handlers
# --------------------------------------------------------------------

@app.exception_handler(ResourceNotFoundError)
async def handle_not_found_exception(
    request: Request,
    exc: ResourceNotFoundError,
):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=error_response(
            "RESOURCE_NOT_FOUND",
            str(exc),
        ).model_dump(),
    )


@app.exception_handler(ValidationException)
async def handle_validation_exception(
    request: Request,
    exc: ValidationException,
):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response(
            "VALIDATION_ERROR",
            str(exc),
        ).model_dump(),
    )


@app.exception_handler(AuthenticationException)
async def handle_authentication_exception(
    request: Request,
    exc: AuthenticationException,
):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=error_response(
            "AUTHENTICATION_ERROR",
            str(exc),
        ).model_dump(),
    )


@app.exception_handler(AuthorizationException)
async def handle_authorization_exception(
    request: Request,
    exc: AuthorizationException,
):
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=error_response(
            "AUTHORIZATION_ERROR",
            str(exc),
        ).model_dump(),
    )


@app.exception_handler(DatabaseException)
async def handle_database_exception(
    request: Request,
    exc: DatabaseException,
):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            "DATABASE_ERROR",
            str(exc) or "Database error occurred.",
        ).model_dump(),
    )


@app.exception_handler(LicenseServerException)
async def handle_license_server_exception(
    request: Request,
    exc: LicenseServerException,
):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            "LICENSE_SERVER_ERROR",
            str(exc),
        ).model_dump(),
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(
    request: Request,
    exc: StarletteHTTPException,
):
    message = (
        exc.detail
        if isinstance(exc.detail, str)
        else str(exc.detail)
    )

    code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_EXCEPTION"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            code,
            message,
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(request: Request, exc: RequestValidationError):
    """Return standard JSON error on request validation errors."""
    try:
        errors = exc.errors()
        err_msg = "; ".join(
            [f"{'.'.join(str(loc) for loc in err.get('loc', []))}: {err.get('msg')}" for err in errors]
        )
    except Exception:
        err_msg = "Request validation failed."

    logger.warning("Request validation error on %s %s: %s", request.method, request.url.path, err_msg)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response(
            "VALIDATION_ERROR",
            err_msg,
        ).model_dump(),
    )


@app.exception_handler(SQLAlchemyError)
async def handle_sqlalchemy_exception(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            "DATABASE_ERROR",
            "A database error occurred. Please try again.",
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def handle_general_exception(request: Request, exc: Exception):
    logger.exception("Unhandled server exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response(
            "INTERNAL_SERVER_ERROR",
            "An internal server error occurred. Please try again.",
        ).model_dump(),
    )


# --------------------------------------------------------------------
# Static Files & Templates
# --------------------------------------------------------------------

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)

templates = Jinja2Templates(
    directory="app/templates",
)


# --------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------

def _render_index(request: Request):
    """Render index.html with backward- and forward-compatible Starlette TemplateResponse."""
    context = {"request": request}
    try:
        return templates.TemplateResponse(request=request, name="index.html", context=context)
    except TypeError:
        return templates.TemplateResponse("index.html", context)


@app.get("/", tags=["Root"])
def home(request: Request):
    """Root endpoint serving the HTML dashboard/landing page."""
    return _render_index(request)


@app.get("/health", tags=["Health"])
def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "application": settings.APP_NAME,
        "version": settings.VERSION,
    }