# app/config/__init__.py
from __future__ import annotations
import os

# اختر الإعداد حسب ENV (dev هو الافتراضي)
ENV = os.getenv("ENV", "dev").lower()

if ENV == "prod":
    from .server import Settings
else:
    from .local import Settings

settings = Settings()

# ---- Post-init helpers/warnings ----
from pathlib import Path
import os as _os

# set GOOGLE_APPLICATION_CREDENTIALS فقط عندما USE_GDRIVE=True
if settings.USE_GDRIVE and settings.GOOGLE_APPLICATION_CREDENTIALS:
    cred_path = Path(settings.GOOGLE_APPLICATION_CREDENTIALS)
    if not cred_path.is_absolute():
        # BASE_DIR من base.py
        from .base import BASE_DIR
        cred_path = BASE_DIR / cred_path
    _os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path)
    print("[config] CRED PATH ->", cred_path, cred_path.exists())

# تأكد من مجلدات التخزين
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.THUMBS_DIR.mkdir(parents=True, exist_ok=True)

# تحذيرات Drive
if settings.USE_GDRIVE:
    if not settings.GDRIVE_ROOT_FOLDER_ID:
        print("[config] WARNING: USE_GDRIVE=True but GDRIVE_ROOT_FOLDER_ID is not set.")
    cred_env = _os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_env or not Path(cred_env).exists():
        print("[config] WARNING: GOOGLE_APPLICATION_CREDENTIALS is missing or invalid.")

print(f"[config] Loaded {settings.ENV} config | USE_GDRIVE={settings.USE_GDRIVE}")
