import re
import secrets
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def gen_slug(n: int = 8) -> str:
    """
    Generate a URL-safe short token.

    Args:
        n (int, optional): Length of the token. Defaults to 8.

    Returns:
        str: URL-safe token string.
    """
    return secrets.token_urlsafe(n)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify that a plain password matches its hashed version.

    Args:
        plain (str): Plain text password.
        hashed (str): Hashed password.

    Returns:
        bool: True if the password matches, False otherwise.
    """
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    """
    Hash a plain password using bcrypt.

    Args:
        plain (str): Plain text password.

    Returns:
        str: Hashed password.
    """
    return pwd_context.hash(plain)


def is_expired(expires_at: Optional[datetime]) -> bool:
    """
    Check if a given datetime is in the past.

    Args:
        expires_at (Optional[datetime]): The expiration datetime.

    Returns:
        bool: True if expired, False otherwise.
    """
    if not expires_at:
        return False
    return datetime.utcnow() > expires_at


def safe_filename(name: str) -> str:
    """
    Sanitize a filename by removing unsafe characters and normalizing.

    Args:
        name (str): Original filename.

    Returns:
        str: Sanitized and normalized filename.
    """
    p = Path(name)
    stem, ext = p.stem, p.suffix.lower()

    norm = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    norm = re.sub(r"[^A-Za-z0-9._-]+", "_", norm).strip("._-")
    if not norm:
        norm = "file"

    return norm + (ext if ext else "")


def unique_name(clean: str) -> str:
    """
    Append a short unique identifier to a filename to prevent collisions.

    Args:
        clean (str): Clean filename.

    Returns:
        str: Unique filename.
    """
    p = Path(clean)
    return f"{p.stem}-{uuid.uuid4().hex[:8]}{p.suffix}"
