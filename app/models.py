from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from .database import Base


class Album(Base):
    """Represents a photo album."""
    __tablename__ = "albums"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    photographer = Column(String, nullable=True)
    event_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    assets = relationship(
        "Asset",
        back_populates="album",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    shares = relationship(
        "ShareLink",
        back_populates="album",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ShareLink(Base):
    """Represents a shareable link for an album."""
    __tablename__ = "share_links"

    id = Column(Integer, primary_key=True, index=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), index=True)
    slug = Column(String, unique=True, index=True)
    expires_at = Column(DateTime, nullable=True)
    password_hash = Column(String, nullable=True)
    allow_zip = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    album = relationship("Album", back_populates="shares")


class Asset(Base):
    """Represents an individual asset (image/file) within an album."""
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)

    # Link to album
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), index=True)
    album = relationship("Album", back_populates="assets")

    # Original file info
    filename = Column(String(255), nullable=False)       # relative path under storage
    original_name = Column(String(255), nullable=False)
    mime_type = Column(String(128), nullable=True)
    size = Column(Integer, nullable=True)

    # Image dimensions (after EXIF normalize)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    # LQIP (tiny base64)
    lqip = Column(Text, nullable=True)

    # JPG variants
    jpg_480 = Column(String(255), nullable=True)
    jpg_960 = Column(String(255), nullable=True)
    jpg_1280 = Column(String(255), nullable=True)
    jpg_1920 = Column(String(255), nullable=True)

    # WEBP variants
    webp_480 = Column(String(255), nullable=True)
    webp_960 = Column(String(255), nullable=True)
    webp_1280 = Column(String(255), nullable=True)
    webp_1920 = Column(String(255), nullable=True)

    # AVIF variants (optional)
    avif_480 = Column(String(255), nullable=True)
    avif_960 = Column(String(255), nullable=True)
    avif_1280 = Column(String(255), nullable=True)
    avif_1920 = Column(String(255), nullable=True)

    # Google Drive IDs
    gdrive_file_id  = Column(String(255), nullable=True)
    gdrive_thumb_id = Column(String(255), nullable=True)


    # Meta
    is_hidden = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Helper to set variants dict from ensure_variants()
    def set_variants(self, variants: dict):
        self.width = variants.get("width")
        self.height = variants.get("height")
        for ext in ("jpg", "webp", "avif"):
            d = variants.get(ext) or {}
            setattr(self, f"{ext}_480", d.get(480))
            setattr(self, f"{ext}_960", d.get(960))
            setattr(self, f"{ext}_1280", d.get(1280))
            setattr(self, f"{ext}_1920", d.get(1920))
