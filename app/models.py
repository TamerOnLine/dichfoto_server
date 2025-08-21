from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Album(Base):
    __tablename__ = "albums"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    photographer = Column(String, nullable=True)
    event_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    assets = relationship("Asset", back_populates="album", cascade="all, delete-orphan")
    shares = relationship("ShareLink", back_populates="album", cascade="all, delete-orphan")

class Asset(Base):
    __tablename__ = "assets"
    id = Column(Integer, primary_key=True, index=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), index=True)
    filename = Column(String, nullable=False)      # relative path under storage (album folder)
    original_name = Column(String, nullable=False) # original uploaded filename
    mime_type = Column(String, nullable=True)
    size = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    gdrive_file_id = Column(String, nullable=True, index=True)
    gdrive_thumb_id = Column(String, nullable=True, index=True)

    album = relationship("Album", back_populates="assets")

class ShareLink(Base):
    __tablename__ = "share_links"
    id = Column(Integer, primary_key=True, index=True)
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), index=True)
    slug = Column(String, unique=True, index=True)
    expires_at = Column(DateTime, nullable=True)
    password_hash = Column(String, nullable=True)
    allow_zip = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    album = relationship("Album", back_populates="shares")
