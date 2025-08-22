from __future__ import annotations

from datetime import datetime
from typing import Generator
from urllib.parse import quote
import unicodedata
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import SessionLocal
from ..services import gdrive, thumbs, zips
from ..utils import is_expired, verify_password

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/s", tags=["public"])


def ascii_fallback(name: str) -> str:
    """Return an ASCII-only filename fallback.

    Non-ASCII characters are stripped via NFKD normalization and ASCII encoding.
    """
    normalized = (
        unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii")
    )
    return normalized or "file"


def get_db() -> Generator[Session, None, None]:
    """Yield a database session; closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def load_share(db: Session, slug: str) -> models.ShareLink:
    """Fetch and validate a share link by slug."""
    share_link = db.query(models.ShareLink).filter(models.ShareLink.slug == slug).first()
    if not share_link:
        raise HTTPException(status_code=404, detail="Not found")
    if is_expired(share_link.expires_at):
        raise HTTPException(status_code=403, detail="Link expired")
    return share_link


@router.get("/{slug}", response_class=HTMLResponse)
def open_share(request: Request, slug: str, db: Session = Depends(get_db)):
    """Render a public album page for a share link."""
    sl = load_share(db, slug)
    album = sl.album

    if sl.password_hash and not request.session.get(f"unlocked:{slug}"):
        return templates.TemplateResponse(
            "public_album.html",
            {
                "request": request,
                "album": album,
                "share": sl,
                "locked": True,
                "site_title": settings.SITE_TITLE,
                "assets": [],
            },
        )

    assets_info = []
    for asset in album.assets:
        # Determine thumbnail URL
        if getattr(settings, "USE_GDRIVE", False) and getattr(asset, "gdrive_thumb_id", None):
            thumb_rel = f"/s/{slug}/thumb/{asset.id}"
        else:
            apath = Path(settings.STORAGE_DIR) / asset.filename
            tpath = thumbs.ensure_thumb(apath)
            if tpath:
                try:
                    thumb_rel = (
                        "/static/thumbs/"
                        + str(tpath.relative_to(settings.THUMBS_DIR)).replace("\\", "/")
                    )
                except Exception:
                    thumb_rel = None
            else:
                thumb_rel = None

        assets_info.append(
            {
                "id": asset.id,
                "name": asset.original_name,
                "url": f"/s/{slug}/file/{asset.id}",
                "thumb": thumb_rel,
                # ملاحظة: لو أردت تمرير مسارات الـ variants إلى القالب أضفها هنا.
            }
        )

    return templates.TemplateResponse(
        "public_album.html",
        {
            "request": request,
            "album": album,
            "share": sl,
            "locked": False,
            "site_title": settings.SITE_TITLE,
            "assets": assets_info,
        },
    )


@router.post("/{slug}/unlock")
def unlock(
    request: Request, slug: str, password: str = Form(...), db: Session = Depends(get_db)
):
    """Unlock a password-protected share link for the current session."""
    sl = load_share(db, slug)
    if not sl.password_hash:
        return RedirectResponse(f"/s/{slug}", status_code=302)
    if verify_password(password, sl.password_hash):
        request.session[f"unlocked:{slug}"] = True
        return RedirectResponse(f"/s/{slug}", status_code=302)
    raise HTTPException(status_code=403, detail="Wrong password")


@router.get("/{slug}/file/{asset_id}")
def get_file(slug: str, asset_id: int, db: Session = Depends(get_db)):
    """Stream or serve an asset file by ID."""
    sl = load_share(db, slug)
    asset = db.get(models.Asset, asset_id)
    if not asset or asset.album_id != sl.album_id:
        raise HTTPException(status_code=404)

    # Google Drive source
    if getattr(settings, "USE_GDRIVE", False) and getattr(asset, "gdrive_file_id", None):
        meta = gdrive.get_meta(asset.gdrive_file_id)
        original_name = asset.original_name or meta.get("name") or "file"
        safe_name = ascii_fallback(original_name)

        headers = {
            "Content-Disposition": (
                f'inline; filename="{safe_name}"; '
                f"filename*=UTF-8''{quote(original_name)}"
            )
        }
        mime = meta.get("mimeType") or "application/octet-stream"

        generator = gdrive.stream_via_requests(asset.gdrive_file_id, chunk_size=256 * 1024)
        return StreamingResponse(generator, media_type=mime, headers=headers)

    # Local filesystem
    fpath = Path(settings.STORAGE_DIR) / asset.filename
    if not fpath.exists():
        raise HTTPException(status_code=404)
    return FileResponse(fpath, filename=asset.original_name)


@router.get("/{slug}/thumb/{asset_id}")
def get_thumb(slug: str, asset_id: int, db: Session = Depends(get_db)):
    """Serve a thumbnail image for an asset."""
    sl = load_share(db, slug)
    asset = db.get(models.Asset, asset_id)
    if not asset or asset.album_id != sl.album_id:
        raise HTTPException(status_code=404)

    # Google Drive thumbnail
    if getattr(settings, "USE_GDRIVE", False) and getattr(asset, "gdrive_thumb_id", None):
        generator = gdrive.stream_via_requests(asset.gdrive_thumb_id, chunk_size=256 * 1024)
        return StreamingResponse(generator, media_type="image/jpeg")

    # Local thumbnail
    tpath = thumbs.thumb_path(Path(settings.STORAGE_DIR) / asset.filename)
    if not tpath.exists():
        apath = Path(settings.STORAGE_DIR) / asset.filename
        thumbs.ensure_thumb(apath)
    if not tpath.exists():
        raise HTTPException(status_code=404)
    return FileResponse(tpath, filename=f"thumb_{asset.original_name}", media_type="image/jpeg")


@router.get("/{slug}/download")
def download_album(slug: str, db: Session = Depends(get_db)):
    """Download an entire album as a ZIP archive."""
    sl = load_share(db, slug)
    if not sl.allow_zip:
        raise HTTPException(status_code=403, detail="ZIP not allowed")

    album = sl.album

    if getattr(settings, "USE_GDRIVE", False):
        try:
            from zipstream import ZipStream  # noqa: F401  (ensures package present)
        except Exception:
            raise HTTPException(status_code=500, detail="zipstream-ng not installed on server")

        def gen_for(file_id: str):
            return gdrive.stream_via_requests(file_id, chunk_size=256 * 1024)

        zs = zips.ZipStream(mode="w", compression="deflated")  # type: ignore
        for asset in album.assets:
            if getattr(asset, "gdrive_file_id", None):
                arcname = f"{album.title}/{asset.original_name}"
                zs.add(arcname, gen_for(asset.gdrive_file_id))

        headers = {
            "Content-Disposition": f'attachment; filename="{album.title.replace(" ", "_")}.zip"'
        }
        return StreamingResponse(zs, media_type="application/zip", headers=headers)

    # Local ZIP in-memory
    files = []
    for asset in album.assets:
        fpath = Path(settings.STORAGE_DIR) / asset.filename
        if fpath.exists():
            files.append(fpath)

    zip_bytes = zips.make_zip_in_memory(files, base_prefix=album.title)
    headers = {
        "Content-Disposition": f'attachment; filename="{album.title.replace(" ", "_")}.zip"'
    }
    return Response(content=zip_bytes, media_type="application/zip", headers=headers)
