from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]

class Settings(BaseSettings):
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'app.db').as_posix()}"
    SECRET_KEY: str = "change-me"
    ADMIN_PASSWORD: str = "admin123"
    SITE_TITLE: str = "Client Gallery"

    STORAGE_DIR: Path = BASE_DIR / "storage"
    THUMBS_DIR: Path = STORAGE_DIR / "_thumbs"
    THUMB_MAX_WIDTH: int = 800

    # Pydantic v2 style
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
    )

settings = Settings()
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.THUMBS_DIR.mkdir(parents=True, exist_ok=True)
