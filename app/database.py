"""
Database configuration for the LOUD Platform Licensing System.

Provides SQLAlchemy engine setup, session management, and FastAPI database
session dependency wiring.
"""

import os
import shutil
import logging
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

engine_kwargs = {
    "pool_pre_ping": True,
    "future": True,
}

if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {
        "check_same_thread": False,
    }
else:
    # PostgreSQL (Neon) connection pool configuration
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_recycle"] = 300

engine = create_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)

if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    # Ensure safety backup and restore protection ONLY for SQLite
    db_file_path = os.path.normpath(settings.DATABASE_URL[len("sqlite:///"):])
    backup_path = f"{db_file_path}.backup"

    # If the active DB is missing or 0-bytes, but a valid backup exists, auto-restore
    if os.path.isfile(backup_path) and os.path.getsize(backup_path) > 0:
        if not os.path.isfile(db_file_path) or os.path.getsize(db_file_path) == 0:
            try:
                shutil.copy2(backup_path, db_file_path)
                logger.info("Restored database from safety backup: %s -> %s", backup_path, db_file_path)
            except Exception as e:
                logger.warning("Failed to restore database from backup: %s", e)

    if os.path.isfile(db_file_path) and os.path.getsize(db_file_path) > 0:
        try:
            should_backup = False
            if not os.path.exists(backup_path):
                should_backup = True
            elif (os.path.getmtime(db_file_path) - os.path.getmtime(backup_path) > 3600):
                # Never overwrite a valid backup with an empty or significantly shrunk database
                if os.path.getsize(db_file_path) >= os.path.getsize(backup_path) * 0.9:
                    should_backup = True
                else:
                    logger.warning(
                        "Skipping safety backup update: active DB (%d bytes) is smaller than backup (%d bytes)",
                        os.path.getsize(db_file_path),
                        os.path.getsize(backup_path),
                    )

            if should_backup:
                shutil.copy2(db_file_path, backup_path)
                logger.info("Database safety backup created at: %s", backup_path)
        except Exception as e:
            logger.warning("Failed to create safety backup: %s", e)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for FastAPI request handling."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_masked_db_url(url: str) -> str:
    """Return a sanitized connection string with password masked."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme.startswith("sqlite"):
            return url
        netloc = parsed.netloc
        if "@" in netloc:
            creds, host_port = netloc.split("@", 1)
            user = creds.split(":", 1)[0] if ":" in creds else creds
            masked_netloc = f"{user}:***@{host_port}"
        else:
            masked_netloc = netloc
        return f"{parsed.scheme}://{masked_netloc}{parsed.path}"
    except Exception:
        return "postgresql://***:***@hidden"


def log_safe_database_info() -> None:
    """Log database connection information safely without exposing credentials."""
    if settings.DATABASE_URL.startswith("sqlite"):
        logger.info("Database backend: SQLite (development mode, local file: %s)", settings.DATABASE_URL)
    else:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(settings.DATABASE_URL)
            host = parsed.hostname or "unknown"
            dbname = parsed.path.lstrip("/") or "unknown"
            logger.info("Database backend: PostgreSQL | Host: %s | Database: %s", host, dbname)
        except Exception:
            logger.info("Database backend: PostgreSQL (credentials masked)")