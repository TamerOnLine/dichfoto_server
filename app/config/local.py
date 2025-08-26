from typing import List
from .base import BaseConfig, BASE_DIR

# احسب env_file خارج الكلاس كما نصحتك سابقًا
_local_env = BASE_DIR / ".env.local"
_default_env = BASE_DIR / ".env"
_env_file = str(_local_env if _local_env.exists() else _default_env)

class Settings(BaseConfig):
    ENV: str = "dev"

    model_config = BaseConfig.model_config.copy()
    model_config.update(env_file=_env_file)

    # لازم نكتب type annotation
    CORS_ALLOW_ORIGINS: List[str] = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]

    USE_GDRIVE: bool = False
    UPLOAD_BASE_URL: str = ""
