# app/config.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# جذر المشروع: dichfoto/
BASE_DIR = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    # ===== Core =====
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'app.db').as_posix()}"
    SECRET_KEY: str = "change-me"     # ضعها في .env للإنتاج
    ADMIN_PASSWORD: str = "admin123"  # ضعها في .env للإنتاج
    SITE_TITLE: str = "Dich Foto"

    # ===== Local storage (fallback & always available) =====
    STORAGE_DIR: Path = BASE_DIR / "storage"
    THUMBS_DIR: Path = STORAGE_DIR / "_thumbs"
    THUMB_MAX_WIDTH: int = 800

    # ===== Google Drive =====
    USE_GDRIVE: bool = False
    GDRIVE_ROOT_FOLDER_ID: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None  # قد تكون نسبية مثل "secrets/xxx.json"

    # Pydantic v2
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()

# --- اجعل مسار GOOGLE_APPLICATION_CREDENTIALS ديناميكيًا من .env ---
# لو كان المسار نسبيًا، نخليه مطلقًا بناءً على BASE_DIR، ونضبط المتغير البيئي.
if settings.GOOGLE_APPLICATION_CREDENTIALS:
    cred_path = Path(settings.GOOGLE_APPLICATION_CREDENTIALS)
    if not cred_path.is_absolute():
        cred_path = BASE_DIR / cred_path
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path)
    print("[config] CRED PATH ->", cred_path, cred_path.exists())

# --- حضّر مجلدات التخزين المحلي دائمًا (حتى مع USE_GDRIVE=True) ---
# هذا لا يؤثر على Drive لكنه يسهل الرجوع للـ local فورًا.
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.THUMBS_DIR.mkdir(parents=True, exist_ok=True)

# --- تحذيرات لطيفة بدون كسر التشغيل ---
if settings.USE_GDRIVE:
    if not settings.GDRIVE_ROOT_FOLDER_ID:
        print("[config] WARNING: USE_GDRIVE=True لكن GDRIVE_ROOT_FOLDER_ID غير مضبوط.")
    cred_env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_env or not Path(cred_env).exists():
        print("[config] WARNING: GOOGLE_APPLICATION_CREDENTIALS غير موجود أو يشير إلى ملف غير موجود.")
