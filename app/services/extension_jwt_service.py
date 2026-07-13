"""
Extension JWT token management service.
"""

from datetime import datetime, timedelta
from typing import Optional

import jwt
from pydantic import BaseModel

from app.config import settings
from app.exceptions import InvalidTokenError
from app.utils.datetime_utils import get_current_time


class ExtensionTokenPayload(BaseModel):
    """Extension JWT token payload."""
    
    license_id: int
    license_key: str
    product_id: int
    customer_id: int
    device_uuid: str
    token_version: int
    issued_at: datetime
    expires_at: datetime


class ExtensionJWTService:
    """Service for managing extension JWT tokens."""
    
    ALGORITHM = "HS256"
    TOKEN_EXPIRY_HOURS = 24
    
    @staticmethod
    def generate_token(
        license_id: int,
        license_key: str,
        product_id: int,
        customer_id: int,
        device_uuid: str,
        device_token_version: int,
    ) -> str:
        """
        Generate an extension JWT token.
        
        Args:
            license_id: License database ID
            license_key: License public key
            product_id: Product database ID
            customer_id: Customer database ID
            device_uuid: Device UUID
        
        Returns:
            Encoded JWT token string
        """
        now = get_current_time()
        expires_at = now + timedelta(hours=ExtensionJWTService.TOKEN_EXPIRY_HOURS)
        
        payload = {
            "license_id": license_id,
            "license_key": license_key,
            "product_id": product_id,
            "customer_id": customer_id,
            "device_uuid": device_uuid,
            "token_version": device_token_version,
            "issued_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        
        token = jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm=ExtensionJWTService.ALGORITHM,
        )
        
        return token
    
    @staticmethod
    def verify_token(token: str) -> ExtensionTokenPayload:
        """
        Verify and decode an extension JWT token.
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded token payload
        
        Raises:
            InvalidTokenError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[ExtensionJWTService.ALGORITHM],
            )
            
            return ExtensionTokenPayload(
                license_id=payload["license_id"],
                license_key=payload["license_key"],
                product_id=payload["product_id"],
                customer_id=payload["customer_id"],
                device_uuid=payload["device_uuid"],
                token_version=payload.get("token_version", 0),
                issued_at=datetime.fromisoformat(payload["issued_at"]),
                expires_at=datetime.fromisoformat(payload["expires_at"]),
            )
        
        except jwt.ExpiredSignatureError as exc:
            raise InvalidTokenError("Extension token has expired.") from exc
        
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError("Invalid extension token.") from exc
