from typing import List
from .base import BaseConfig, BASE_DIR

_env_file = BASE_DIR / ".env"

class Settings(BaseConfig):
    ENV: str = "prod"

    model_config = BaseConfig.model_config.copy()
    model_config.update(env_file=str(_env_file))

    CORS_ALLOW_ORIGINS: List[str] = [
        "https://dichfoto.com",
        "https://www.dichfoto.com",
        "https://upload.dichfoto.com",
    ]

    USE_GDRIVE: bool = True  # أو True حسب حاجتك
    UPLOAD_BASE_URL: str = "https://upload.dichfoto.com"

