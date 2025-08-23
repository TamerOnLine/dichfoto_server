from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from .database import Base

class Album(Base):
    __tablename__ = "albums"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    photographer = Column(String, nullable=True)
    photographer_url = Column(String(255), nullable=True)
    
    event_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # ⭐ صورة الغلاف: FK صريح إلى assets.id
    cover_asset_id = Column(Integer, ForeignKey("assets.id", ondelete="SET NULL"),
                            nullable=True, index=True)
    # ⭐ حدّد أي FK تُستخدم هنا
    cover_asset = relationship(
        "Asset",
        foreign_keys=[cover_asset_id],
        uselist=False,
        post_update=True,   # يساعد على حلقة المرجعية عند التحديث
    )

    # ⭐ علاقة الألبوم → الأصول: حدّد أن الـ FK المقصود هو Asset.album_id
    assets = relationship(
        "Asset",
        back_populates="album",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Asset.album_id",
        order_by="Asset.sort_order"  # اختياري
    )

    shares = relationship(
        "ShareLink",
        back_populates="album",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

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

class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)

    # ⭐ FK صريح إلى الألبوم
    album_id = Column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), index=True)

    # ⭐ صرّح أيضًا بـ foreign_keys هنا
    album = relationship("Album", back_populates="assets", foreign_keys=[album_id])

    # ترتيب اختياري
    sort_order = Column(Integer, nullable=True)

    # معلومات الملف
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    mime_type = Column(String(128), nullable=True)
    size = Column(Integer, nullable=True)

    # أبعاد + LQIP
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    lqip = Column(Text, nullable=True)

    # JPG
    jpg_480 = Column(String(255), nullable=True)
    jpg_960 = Column(String(255), nullable=True)
    jpg_1280 = Column(String(255), nullable=True)
    jpg_1920 = Column(String(255), nullable=True)

    # WEBP
    webp_480 = Column(String(255), nullable=True)
    webp_960 = Column(String(255), nullable=True)
    webp_1280 = Column(String(255), nullable=True)
    webp_1920 = Column(String(255), nullable=True)

    # AVIF
    avif_480 = Column(String(255), nullable=True)
    avif_960 = Column(String(255), nullable=True)
    avif_1280 = Column(String(255), nullable=True)
    avif_1920 = Column(String(255), nullable=True)

    # Google Drive
    gdrive_file_id  = Column(String(255), nullable=True)
    gdrive_thumb_id = Column(String(255), nullable=True)

    is_hidden = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def set_variants(self, variants: dict):
        self.width = variants.get("width")
        self.height = variants.get("height")
        for ext in ("jpg", "webp", "avif"):
            d = variants.get(ext) or {}
            setattr(self, f"{ext}_480", d.get(480))
            setattr(self, f"{ext}_960", d.get(960))
            setattr(self, f"{ext}_1280", d.get(1280))
            setattr(self, f"{ext}_1920", d.get(1920))


class Like(Base):
    __tablename__ = "likes"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, index=True)       # رابط الصورة
    user_id = Column(Integer, nullable=True)  # (اختياري) لو عندك مستخدمين
    liked = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)