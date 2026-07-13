"""Centralized datetime utilities for the LOUD Licensing Platform.

This module ensures the backend uses a single UTC datetime strategy.
All datetimes are naive UTC, which is compatible with SQLite while still
being easy to migrate to PostgreSQL later.
"""

from datetime import datetime, timedelta
from typing import Optional


def get_current_time() -> datetime:
    """Return the current UTC time as a naive datetime."""
    return datetime.utcnow()


def is_expired(expires_at: datetime, now: Optional[datetime] = None) -> bool:
    """Return whether an expiry timestamp has passed."""
    current = now if now is not None else get_current_time()
    return expires_at < current


def remaining_days(expires_at: datetime, now: Optional[datetime] = None) -> int:
    """Return non-negative remaining whole days until expiry."""
    current = now if now is not None else get_current_time()
    return max(0, (expires_at.date() - current.date()).days)


def minutes_from_now(minutes: int) -> datetime:
    """Return a naive UTC datetime minutes from now."""
    return get_current_time() + timedelta(minutes=minutes)


def hours_from_now(hours: int) -> datetime:
    """Return a naive UTC datetime hours from now."""
    return get_current_time() + timedelta(hours=hours)
