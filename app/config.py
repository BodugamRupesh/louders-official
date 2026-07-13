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

        # Required configuration
        self.DATABASE_URL = self._get_required_env("DATABASE_URL")

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

    def _get_optional_env(self, name: str) -> str | None:
        """Return an optional environment variable, normalized to None when unset."""
        value = os.getenv(name, "")
        return value.strip() or None


settings = Settings()