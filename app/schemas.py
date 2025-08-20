from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ==========
# Base
# ==========
class BaseSchema(BaseModel):
    # بديل orm_mode في Pydantic v2
    model_config = ConfigDict(from_attributes=True)


# ==========
# Helpers
# ==========
def _parse_dt(value: Optional[str | datetime | date]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        # حوّل date إلى datetime عند منتصف الليل
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        # يقبل "YYYY-MM-DD" أو "YYYY-MM-DDTHH:MM:SS"
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


# ==========
# Inputs
# ==========
class AlbumCreate(BaseSchema):
    title: str = Field(..., min_length=1)
    photographer: Optional[str] = None
    # نقبل تاريخ أو نص ISO ونحوّله لdatetime
    event_date: Optional[datetime] = None

    @field_validator("event_date", mode="before")
    @classmethod
    def _coerce_event_date(cls, v):
        return _parse_dt(v)


class ShareCreate(BaseSchema):
    album_id: int
    expires_at: Optional[datetime] = None
    password: Optional[str] = None
    allow_zip: bool = True

    @field_validator("expires_at", mode="before")
    @classmethod
    def _coerce_expires_at(cls, v):
        return _parse_dt(v)


# ==========
# Outputs
# ==========
class AssetOut(BaseSchema):
    id: int
    album_id: int
    filename: str
    original_name: str
    mime_type: Optional[str] = None
    size: Optional[int] = None
    created_at: datetime


class ShareOut(BaseSchema):
    id: int
    album_id: int
    slug: str
    expires_at: Optional[datetime] = None
    allow_zip: bool = True
    created_at: datetime
    # حقل مشتق لعدم كشف password_hash
    protected: bool = Field(default=False)

    @field_validator("protected", mode="before")
    @classmethod
    def _derive_protected(cls, v, info):
        # لو جاء dict من ORM، ممكن يحتوي password_hash
        data = info.data if hasattr(info, "data") else None
        if isinstance(v, bool):
            return v
        # حاول قراءة password_hash من المصدر إن وجد
        ph = None
        if isinstance(data, dict):
            ph = data.get("password_hash") or data.get("password") or None
        else:
            # من كائن ORM
            obj = info.data
            ph = getattr(obj, "password_hash", None) if obj is not None else None
        return bool(ph)


class AlbumOut(BaseSchema):
    id: int
    title: str
    photographer: Optional[str] = None
    event_date: Optional[datetime] = None
    created_at: datetime
    # اختيارياً نضمّن العلاقات
    assets: Optional[List[AssetOut]] = None
    shares: Optional[List[ShareOut]] = None
