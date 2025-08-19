from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date

class AlbumCreate(BaseModel):
    title: str
    photographer: Optional[str] = None
    event_date: Optional[date] = None

class ShareCreate(BaseModel):
    album_id: int
    expires_at: Optional[datetime] = None
    password: Optional[str] = None
    allow_zip: bool = True
