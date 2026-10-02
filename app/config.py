"""
Application configuration for the LOUD Platform Licensing System.

Loads and validates all required environment variables.
"""

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        self.APP_NAME = "LOUD License Server"
        self.VERSION = "2.0.0"

        self.APP_ENV = (
            os.getenv("APP_ENV", "production")
            .strip()
            .lower()
        )

        self.DEBUG = (
            os.getenv("DEBUG", "false")
            .strip()
            .lower()
            in {"1", "true", "yes", "on"}
        )

        # Project Root directory
        self.PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.IS_PRODUCTION = (
            self.APP_ENV == "production"
            or bool(os.getenv("RENDER"))
            or bool(os.getenv("PRODUCTION"))
        )

        # Database configuration with persistence resolution
        raw_db_url = os.getenv("DATABASE_URL", "").strip()
        self.DATABASE_URL = self._resolve_database_url(raw_db_url)

        self.SECRET_KEY = self._get_required_env("SECRET_KEY")
        if len(self.SECRET_KEY) < 32:
            raise RuntimeError(
                "SECRET_KEY must be at least 32 characters long."
            )

        self.JWT_ALGORITHM = (
            os.getenv("JWT_ALGORITHM", "HS256")
            .strip()
            or "HS256"
        )

        self.ACCESS_TOKEN_EXPIRE_MINUTES = self._get_int_env(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            1440,
        )

        if self.ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
            raise RuntimeError(
                "ACCESS_TOKEN_EXPIRE_MINUTES must be greater than 0."
            )

        # Initial admin (optional)
        self.ADMIN_USERNAME = self._get_optional_env("ADMIN_USERNAME")
        self.ADMIN_PASSWORD = self._get_optional_env("ADMIN_PASSWORD")

    def _get_required_env(self, name: str) -> str:
        """
        Return a required environment variable.

        Raises:
            RuntimeError: If the variable is missing or empty.
        """
        value = os.getenv(name, "").strip()

        if not value:
            raise RuntimeError(
                f"Missing required environment variable: {name}. "
                "Set it before starting the application."
            )

        return value

    def _get_int_env(self, name: str, default: int) -> int:
        """
        Return an integer environment variable.

        Raises:
            RuntimeError: If the value cannot be converted to an integer.
        """
        value = os.getenv(name, str(default)).strip()

        try:
            return int(value)
        except ValueError as exc:
            raise RuntimeError(
                f"Environment variable '{name}' must be an integer. Got: '{value}'."
            ) from exc

    def _ensure_seed_if_needed(self, target_path: str) -> None:
        """Ensure persistent database is populated from best available seed only if missing or 0 bytes."""
        try:
            if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
                # Target database already exists and has data: NEVER overwrite!
                return

            candidates = [
                os.path.normpath(os.path.join(self.PROJECT_ROOT, "licenses.db")),
                os.path.normpath(os.path.join(self.PROJECT_ROOT, "licenses.db.backup")),
                os.path.normpath(os.path.join(self.PROJECT_ROOT, "licenses.db.safe_backup")),
            ]
            best_seed = None
            best_size = 0
            for seed in candidates:
                if os.path.isfile(seed):
                    sz = os.path.getsize(seed)
                    if sz > best_size:
                        best_seed = seed
                        best_size = sz

            if best_seed and best_size > 0:
                import shutil
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(best_seed, target_path)
        except Exception:
            pass

    def _resolve_database_url(self, raw_url: str) -> str:
        """
        Deterministically resolve and normalize the database URL.

        In production (or Render):
        - DATABASE_URL must be provided in the environment.
        - Must be PostgreSQL (Neon).
        - Silent fallback to SQLite in production is strictly forbidden to prevent data loss.
        - Normalizes postgres:// to postgresql:// for SQLAlchemy compatibility.

        In local development:
        - If DATABASE_URL is unset, defaults to local SQLite: sqlite:///./licenses.db.
        """
        raw_url = raw_url.strip()

        # 1. Production Mode - Strict Neon PostgreSQL requirement (NO silent SQLite fallback)
        if self.IS_PRODUCTION:
            if not raw_url:
                raise RuntimeError(
                    "CRITICAL CONFIGURATION ERROR: DATABASE_URL environment variable is missing in production. "
                    "Production requires a PostgreSQL (Neon) connection string. "
                    "Silent fallback to SQLite in production is disabled to protect against data loss."
                )
            if raw_url.startswith("sqlite"):
                raise RuntimeError(
                    "CRITICAL CONFIGURATION ERROR: Production environment is configured with an ephemeral SQLite database URL. "
                    "Production requires a PostgreSQL (Neon) connection string to prevent data loss across restarts. "
                    "Set DATABASE_URL to your Neon PostgreSQL connection string."
                )

        # 2. Local / Development Fallback
        if not raw_url:
            raw_url = "sqlite:///./licenses.db"

        # 3. PostgreSQL / Neon Normalization
        if raw_url.startswith("postgres://"):
            raw_url = "postgresql://" + raw_url[len("postgres://"):]

        if raw_url.startswith("postgresql://") or raw_url.startswith("postgresql+"):
            return raw_url

        # 4. Local SQLite Path Resolution (development only)
        if raw_url.startswith("sqlite"):
            prefix = "sqlite:///"
            if not raw_url.startswith(prefix):
                return raw_url

            path_part = raw_url[len(prefix):]
            if not os.path.isabs(path_part):
                cleaned_rel = path_part.lstrip("./").lstrip(".\\")
                abs_path = os.path.normpath(os.path.join(self.PROJECT_ROOT, cleaned_rel))
            else:
                abs_path = os.path.normpath(path_part)

            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            self._ensure_seed_if_needed(abs_path)
            return f"sqlite:///{abs_path.replace(os.sep, '/')}"

        return raw_url

    def _get_optional_env(self, name: str) -> str | None:
        """Return an optional environment variable, normalized to None when unset."""
        value = os.getenv(name, "")
        return value.strip() or None


settings = Settings()