from __future__ import annotations

from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ============================
# Base Schema
# ============================
class BaseSchema(BaseModel):
    """Base schema class for all models.

    This class enables Pydantic's `from_attributes` mode, which is
    equivalent to the deprecated `orm_mode` in Pydantic v1.
    """

    model_config = ConfigDict(from_attributes=True)


# ============================
# Helper Functions
# ============================
def _parse_dt(value: Optional[str | datetime | date]) -> Optional[datetime]:
    """Convert a string, date, or datetime into a datetime object.

    Args:
        value (Optional[str | datetime | date]): Input value to parse.

    Returns:
        Optional[datetime]: A valid datetime object if parsing succeeds,
        otherwise None.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        # Convert `date` to `datetime` at midnight
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        # Accepts "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM:SS"
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


# ============================
# Input Schemas
# ============================
class AlbumCreate(BaseSchema):
    """Schema for creating a new album."""

    title: str = Field(..., min_length=1)
    photographer: Optional[str] = None
    event_date: Optional[datetime] = None

    @field_validator("event_date", mode="before")
    @classmethod
    def _coerce_event_date(cls, value):
        """Validate and coerce event_date into a datetime object."""
        return _parse_dt(value)


class ShareCreate(BaseSchema):
    """Schema for creating a share link for an album."""

    album_id: int
    expires_at: Optional[datetime] = None
    password: Optional[str] = None
    allow_zip: bool = True

    @field_validator("expires_at", mode="before")
    @classmethod
    def _coerce_expires_at(cls, value):
        """Validate and coerce expires_at into a datetime object."""
        return _parse_dt(value)


# ============================
# Output Schemas
# ============================
class AssetOut(BaseSchema):
    """Schema for returning asset details."""

    id: int
    album_id: int
    filename: str
    original_name: str
    mime_type: Optional[str] = None
    size: Optional[int] = None
    created_at: datetime


class ShareOut(BaseSchema):
    """Schema for returning share link details."""

    id: int
    album_id: int
    slug: str
    expires_at: Optional[datetime] = None
    allow_zip: bool = True
    created_at: datetime
    protected: bool = Field(default=False)

    @field_validator("protected", mode="before")
    @classmethod
    def _derive_protected(cls, value, info):
        """Determine if a share is protected by a password.

        Args:
            value: Explicit value passed to `protected`.
            info: Validation information, may include ORM object or dict.

        Returns:
            bool: True if the share is password-protected, otherwise False.
        """
        data = info.data if hasattr(info, "data") else None

        if isinstance(value, bool):
            return value

        password_hash = None
        if isinstance(data, dict):
            password_hash = (
                data.get("password_hash") or data.get("password") or None
            )
        else:
            obj = info.data
            password_hash = (
                getattr(obj, "password_hash", None) if obj is not None else None
            )

        return bool(password_hash)


class AlbumOut(BaseSchema):
    """Schema for returning album details with optional relations."""

    id: int
    title: str
    photographer: Optional[str] = None
    event_date: Optional[datetime] = None
    created_at: datetime
    assets: Optional[List[AssetOut]] = None
    shares: Optional[List[ShareOut]] = None
