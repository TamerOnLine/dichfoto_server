from pathlib import Path
from pydantic import BaseSettings

BASE_DIR = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'app.db').as_posix()}"
    SECRET_KEY: str = "change-me"
    ADMIN_PASSWORD: str = "admin123"
    SITE_TITLE: str = "Client Gallery"

    STORAGE_DIR: Path = BASE_DIR / "storage"
    THUMBS_DIR: Path = STORAGE_DIR / "_thumbs"
    THUMB_MAX_WIDTH: int = 800

    class Config:
        env_file = str(BASE_DIR / ".env")

settings = Settings()
# Ensure storage dirs exist at startup time (ok in dev)
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.THUMBS_DIR.mkdir(parents=True, exist_ok=True)
