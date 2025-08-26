from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class Album(Base):
    """Represents a photo album entity with associated metadata and assets."""

    __tablename__ = "albums"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    photographer = Column(String, nullable=True)
    photographer_url = Column(String(255), nullable=True)

    event_date = Column(DateTime, nullable=True)  # Event date (optional)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Cover image: Explicit FK to assets.id
    cover_asset_id = Column(
        Integer,
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cover_asset = relationship(
        "Asset",
        foreign_keys=[cover_asset_id],
        uselist=False,
        post_update=True,  # Helps with circular reference during updates
    )

    # Album-to-assets relationship: specify that the FK used is Asset.album_id
    assets = relationship(
        "Asset",
        back_populates="album",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Asset.album_id",
        order_by="Asset.sort_order",  # Optional ordering
    )

    shares = relationship(
        "ShareLink",
        back_populates="album",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ShareLink(Base):
    """Represents a shareable link to an album with optional expiration and password."""

    __tablename__ = "share_links"

    id = Column(Integer, primary_key=True, index=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), index=True)
    slug = Column(String, unique=True, index=True)
    expires_at = Column(DateTime, nullable=True)
    password_hash = Column(String, nullable=True)
    allow_zip = Column(Boolean, default=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    album = relationship("Album", back_populates="shares")


class Asset(Base):
    """Represents a digital asset (e.g., photo) linked to an album with multiple formats."""

    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)

    # Explicit FK to the album
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), index=True)

    # Also declare the foreign_keys argument here
    album = relationship("Album", back_populates="assets", foreign_keys=[album_id])

    sort_order = Column(Integer, nullable=True)  # Optional ordering

    # File information
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    mime_type = Column(String(128), nullable=True)
    size = Column(Integer, nullable=True)

    # Dimensions + LQIP (Low Quality Image Placeholder)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
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

    # AVIF variants
    avif_480 = Column(String(255), nullable=True)
    avif_960 = Column(String(255), nullable=True)
    avif_1280 = Column(String(255), nullable=True)
    avif_1920 = Column(String(255), nullable=True)

    # Google Drive information
    gdrive_file_id = Column(String(255), nullable=True)
    gdrive_thumb_id = Column(String(255), nullable=True)

    is_hidden = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)

    def set_variants(self, variants: dict):
        """Set variant URLs and dimensions based on the provided dictionary.

        Args:
            variants (dict): Dictionary containing width, height, and URLs for each format.
        """
        self.width = variants.get("width")
        self.height = variants.get("height")
        for ext in ("jpg", "webp", "avif"):
            d = variants.get(ext) or {}
            setattr(self, f"{ext}_480", d.get(480))
            setattr(self, f"{ext}_960", d.get(960))
            setattr(self, f"{ext}_1280", d.get(1280))
            setattr(self, f"{ext}_1920", d.get(1920))


class Like(Base):
    """Represents a user's like on an image, optionally linked to a user ID."""

    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, index=True)  # Image URL
    user_id = Column(Integer, nullable=True)  # (Optional) if users exist
    liked = Column(Boolean, default=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())