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
from app.models import AdminUser, Product
from app.routers import (
    admin,
    auth,
    customers,
    devices,
    extensions,
    licenses,
    plans,
    products,
)
from app.services.admin_service import AdminService
from app.utils.responses import error_response


logger = logging.getLogger(__name__)


def _validate_database_ready() -> None:
    """Ensure the database is available before serving requests."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise RuntimeError(
            "Database is unavailable during startup. "
            "Ensure the database server is running and migrations have been applied."
        ) from exc


def _ensure_initial_admin() -> None:
    """Create the initial owner admin from environment settings when needed."""
    if not settings.ADMIN_USERNAME or not settings.ADMIN_PASSWORD:
        logger.warning(
            "ADMIN_USERNAME or ADMIN_PASSWORD is not configured; skipping initial admin seeding."
        )
        return

    db = SessionLocal()
    try:
        owner_exists = (
            db.query(AdminUser)
            .filter(AdminUser.role == "owner")
            .first()
        )
        if owner_exists is not None:
            return

        AdminService.create_admin(
            db,
            username=settings.ADMIN_USERNAME,
            password=settings.ADMIN_PASSWORD,
            role="owner",
        )
        logger.info("Initial admin user created successfully from environment settings.")
    except SQLAlchemyError as exc:
        logger.exception("Failed to create the initial admin user: %s", exc)
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
    """Validate database connectivity, seed initial admin, and ensure default product."""
    _validate_database_ready()
    _ensure_initial_admin()
    _ensure_default_product()
    logger.info("LOUD License Server started successfully.")


# --------------------------------------------------------------------
# Middleware
# --------------------------------------------------------------------

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

allow_credentials = True
if not cors_origins and settings.DEBUG:
    cors_origins = ["*"]
    allow_credentials = False

if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
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
app.include_router(extensions.router)


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


@app.exception_handler(HTTPException)
async def handle_http_exception(
    request: Request,
    exc: HTTPException,
):
    message = (
        exc.detail
        if isinstance(exc.detail, str)
        else str(exc.detail)
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            "HTTP_EXCEPTION",
            message,
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(request: Request, exc: RequestValidationError):
    """Log request validation errors and return the standard FastAPI response.

    This helps capture the exact Pydantic validation messages and the request body
    when a 422 Unprocessable Entity is raised.
    """
    try:
        body = await request.body()
        logger.error(
            "Request validation error for %s %s: %s - body: %s",
            request.method,
            request.url.path,
            exc.errors(),
            body.decode('utf-8', errors='replace'),
        )
    except Exception:
        logger.exception("Failed to read request body for validation error")

    # Delegate to FastAPI's default handler to produce the usual 422 response
    return await request_validation_exception_handler(request, exc)


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

@app.get("/", tags=["Root"])
def home(request: Request):
    """Root endpoint serving the HTML dashboard/landing page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health", tags=["Health"])
def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "version": settings.VERSION,
    }