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

        # Database configuration with persistence resolution
        raw_db_url = self._get_required_env("DATABASE_URL")
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
        Deterministically resolve the database URL.

        - If SQLite:
          - If DATA_DIR environment variable is set, place licenses.db in DATA_DIR.
          - If standard persistent directories (/var/data, /data, /app/data) exist, use persistent disk.
          - Otherwise, resolve relative paths against the project root directory.
          - Ensure parent directory exists.
        """
        if not raw_url.startswith("sqlite"):
            return raw_url

        prefix = "sqlite:///"
        if not raw_url.startswith(prefix):
            return raw_url

        path_part = raw_url[len(prefix):]

        # 1. Custom persistent DATA_DIR override
        data_dir = os.getenv("DATA_DIR", "").strip()
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
            db_filename = os.path.basename(path_part) or "licenses.db"
            resolved_path = os.path.join(data_dir, db_filename)
            self._ensure_seed_if_needed(resolved_path)
            normalized_path = os.path.abspath(resolved_path).replace("\\", "/")
            return f"sqlite:///{normalized_path}"

        # 2. Standard Render (/var/data) / Cloud (/data) / Docker (/app/data) persistent volume check
        if "./licenses.db" in path_part or path_part == "licenses.db":
            candidate_persistent_dirs = ["/var/data", "/data", "/app/data"]
            for cand in candidate_persistent_dirs:
                if os.path.isdir(cand) and os.access(cand, os.W_OK):
                    persistent_db = os.path.join(cand, "licenses.db").replace("\\", "/")
                    self._ensure_seed_if_needed(persistent_db)
                    return f"sqlite:///{persistent_db}"

        # 3. Resolve relative paths deterministically relative to PROJECT_ROOT
        if not os.path.isabs(path_part):
            cleaned_rel = path_part.lstrip("./").lstrip(".\\")
            abs_path = os.path.normpath(os.path.join(self.PROJECT_ROOT, cleaned_rel))
        else:
            abs_path = os.path.normpath(path_part)

        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        normalized_url = f"sqlite:///{abs_path.replace(os.sep, '/')}"
        return normalized_url

    def _get_optional_env(self, name: str) -> str | None:
        """Return an optional environment variable, normalized to None when unset."""
        value = os.getenv(name, "")
        return value.strip() or None


settings = Settings()