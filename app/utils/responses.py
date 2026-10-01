"""Reusable API response helpers for the LOUD License Server."""

from typing import Any

from app.schemas import ErrorDetail, ErrorResponse, SuccessResponse


def success_response(message: str, data: Any | None = None) -> SuccessResponse:
    """Build a standardized success response."""
    return SuccessResponse(success=True, message=message, data=data)


def error_response(code: str, message: str) -> ErrorResponse:
    """Build a standardized error response."""
    return ErrorResponse(
        success=False,
        message=message,
        error_code=code,
        error=ErrorDetail(code=code, message=message),
    )

