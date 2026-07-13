"""
Security utilities for the LOUD Platform Licensing System.

Provides:
- Password hashing
- Password verification
- JWT token creation
- JWT token verification
"""

from app.utils.datetime_utils import get_current_time, minutes_from_now
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.exceptions import InvalidTokenError

# Password hashing configuration
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty.")
    return pwd_context.hash(password)

def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    if not plain_password or not hashed_password:
        return False

    return pwd_context.verify(
        plain_password,
        hashed_password,
    )

def create_access_token(
    data: dict[str, Any],
) -> str:
    """
    Create a signed JWT access token.
    """
    payload = data.copy()

    now = get_current_time()
    expire = minutes_from_now(settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload["iat"] = now
    payload["exp"] = expire

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_token(
    token: str,
) -> dict[str, Any]:
    """
    Verify and decode a JWT access token.

    Raises:
        InvalidTokenError: If the token is invalid or expired.
    """
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise InvalidTokenError(f"Invalid token: {exc}") from exc