from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.exceptions import InvalidProductKeyError
from app.schemas import ExtensionActivateRequest
from app.services.extension_service import ExtensionService


def test_activate_schema_accepts_product_api_key() -> None:
    payload = ExtensionActivateRequest(
        product_api_key="prod_key_123",
        license_key="license_key_123456",
        device_uuid="device-uuid-123",
        browser="Chrome",
        customer_email="user@example.com",
    )

    assert payload.product_api_key == "prod_key_123"


def test_activate_schema_requires_customer_email() -> None:
    with pytest.raises(ValidationError):
        ExtensionActivateRequest(
            product_api_key="prod_key_123",
            license_key="license_key_123456",
            device_uuid="device-uuid-123",
            browser="Chrome",
        )


def test_validate_product_api_key_raises_for_invalid_key() -> None:
    db = SimpleNamespace()
    db.query = lambda *args, **kwargs: SimpleNamespace(
        filter=lambda *args, **kwargs: SimpleNamespace(first=lambda: None)
    )

    with pytest.raises(InvalidProductKeyError):
        ExtensionService.validate_product_api_key(db, "bad_key")
