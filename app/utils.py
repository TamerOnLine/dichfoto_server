import secrets
from datetime import datetime
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def gen_slug(n: int = 8) -> str:
    # URL-safe short token
    return secrets.token_urlsafe(n)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def is_expired(expires_at) -> bool:
    if not expires_at:
        return False
    return datetime.utcnow() > expires_at
