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

    # Create safety backup if database exists and has data
    db_file_path = os.path.normpath(settings.DATABASE_URL[len("sqlite:///"):])
    if os.path.isfile(db_file_path) and os.path.getsize(db_file_path) > 0:
        backup_path = f"{db_file_path}.backup"
        try:
            if not os.path.exists(backup_path) or (os.path.getmtime(db_file_path) - os.path.getmtime(backup_path) > 3600):
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