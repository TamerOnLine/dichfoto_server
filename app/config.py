"""
Configuration settings for the Dich Foto application.

This module defines application-wide configuration variables using Pydantic's
BaseSettings for environment-based overrides. It also ensures proper setup
of local storage directories and Google Drive credentials when applicable.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root directory: dichfoto/
BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """
    Application configuration settings.

    These settings can be overridden by environment variables or values
    defined in the `.env` file located at the project root.
    """

    # ===== Core =====
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'app.db').as_posix()}"
    SECRET_KEY: str = "change-me"      # Should be set in .env for production
    ADMIN_PASSWORD: str = "admin123"   # Should be set in .env for production
    SITE_TITLE: str = "Dich Foto"

    # ===== Local storage (always available) =====
    STORAGE_DIR: Path = BASE_DIR / "storage"
    THUMBS_DIR: Path = STORAGE_DIR / "_thumbs"
    THUMB_MAX_WIDTH: int = 800

    # ===== Google Drive =====
    USE_GDRIVE: bool = False
    GDRIVE_ROOT_FOLDER_ID: Optional[str] = None
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = None
    # This can be a relative path like "secrets/xxx.json"

    # Pydantic v2 configuration
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Initialize settings
settings = Settings()

# --- Ensure GOOGLE_APPLICATION_CREDENTIALS path is absolute ---
if settings.GOOGLE_APPLICATION_CREDENTIALS:
    cred_path = Path(settings.GOOGLE_APPLICATION_CREDENTIALS)
    if not cred_path.is_absolute():
        cred_path = BASE_DIR / cred_path
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_path)
    print("[config] CRED PATH ->", cred_path, cred_path.exists())

# --- Ensure local storage directories exist ---
# This is always done, even if USE_GDRIVE=True, to allow fallback to local.
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.THUMBS_DIR.mkdir(parents=True, exist_ok=True)

# --- Warnings (non-blocking) ---
if settings.USE_GDRIVE:
    if not settings.GDRIVE_ROOT_FOLDER_ID:
        print("[config] WARNING: USE_GDRIVE=True but GDRIVE_ROOT_FOLDER_ID is not set.")
    cred_env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_env or not Path(cred_env).exists():
        print(
            "[config] WARNING: GOOGLE_APPLICATION_CREDENTIALS is missing "
            "or points to a non-existent file."
        )
