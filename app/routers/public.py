from __future__ import annotations

from datetime import datetime
from typing import Generator
from urllib.parse import quote
import unicodedata

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
from ..services import gdrive, storage, thumbs, zips
from ..utils import is_expired, verify_password


templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/s", tags=["public"])


def ascii_fallback(name: str) -> str:
    """Return an ASCII-only filename fallback.

    Non-ASCII characters are stripped via NFKD normalization and ASCII encoding.

    Args:
        name (str): Original filename that may contain non-ASCII characters.

    Returns:
        str: ASCII-only safe filename. Defaults to "file" if empty after
            normalization.
    """

    normalized = unicodedata.normalize("NFKD", name or "").encode(
        "ascii", "ignore"
    ).decode("ascii")
    return normalized or "file"


def get_db() -> Generator[Session, None, None]:
    """Yield a database session.

    Yields:
        Generator[Session, None, None]: SQLAlchemy session object.

    Notes:
        The session is closed after use via a ``finally`` block.
    """

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def load_share(db: Session, slug: str) -> models.ShareLink:
    """Fetch and validate a share link by slug.

    Args:
        db (Session): Active SQLAlchemy session.
        slug (str): Share link slug.

    Returns:
        models.ShareLink: The resolved ShareLink instance.

    Raises:
        HTTPException: If the share link is not found (404) or expired (403).
    """

    share_link = db.query(models.ShareLink).filter(models.ShareLink.slug == slug).first()
    if not share_link:
        raise HTTPException(status_code=404, detail="Not found")
    if is_expired(share_link.expires_at):
        raise HTTPException(status_code=403, detail="Link expired")
    return share_link


@router.get("/{slug}", response_class=HTMLResponse)
def open_share(request: Request, slug: str, db: Session = Depends(get_db)):
    """Render a public album page for a share link.

    If the share link is password-protected and the session has not been
    unlocked, a locked view is returned. Otherwise, assets and thumbnails are
    prepared for rendering.

    Args:
        request (Request): FastAPI request object.
        slug (str): Share link slug.
        db (Session): Database session (dependency-injected).

    Returns:
        HTMLResponse: Rendered template response.
    """

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
        if settings.USE_GDRIVE and asset.gdrive_thumb_id:
            thumb_rel = f"/s/{slug}/thumb/{asset.id}"
        else:
            apath = storage.album_dir(album.id) / asset.filename
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
    """Unlock a password-protected share link for the current session.

    Args:
        request (Request): FastAPI request object.
        slug (str): Share link slug.
        password (str): Password submitted via form.
        db (Session): Database session (dependency-injected).

    Returns:
        RedirectResponse: Redirect to the share page upon success or if no
            password protection is set.

    Raises:
        HTTPException: If the provided password is incorrect (403).
    """

    sl = load_share(db, slug)
    if not sl.password_hash:
        return RedirectResponse(f"/s/{slug}", status_code=302)
    if verify_password(password, sl.password_hash):
        request.session[f"unlocked:{slug}"] = True
        return RedirectResponse(f"/s/{slug}", status_code=302)
    raise HTTPException(status_code=403, detail="Wrong password")


@router.get("/{slug}/file/{asset_id}")
def get_file(slug: str, asset_id: int, db: Session = Depends(get_db)):
    """Stream or serve an asset file by ID.

    The source is either Google Drive (if enabled) or the local filesystem.

    Args:
        slug (str): Share link slug.
        asset_id (int): Asset identifier within the album.
        db (Session): Database session (dependency-injected).

    Returns:
        StreamingResponse | FileResponse: File stream response.

    Raises:
        HTTPException: If the asset is not found or not part of the album.
    """

    sl = load_share(db, slug)
    asset = db.get(models.Asset, asset_id)
    if not asset or asset.album_id != sl.album_id:
        raise HTTPException(status_code=404)

    # Google Drive source
    if settings.USE_GDRIVE and asset.gdrive_file_id:
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

        # Stream via AuthorizedSession
        generator = gdrive.stream_via_requests(
            asset.gdrive_file_id, chunk_size=256 * 1024
        )
        return StreamingResponse(generator, media_type=mime, headers=headers)

    # Local filesystem
    fpath = storage.album_dir(sl.album_id) / asset.filename
    if not fpath.exists():
        raise HTTPException(status_code=404)
    return FileResponse(fpath, filename=asset.original_name)


@router.get("/{slug}/thumb/{asset_id}")
def get_thumb(slug: str, asset_id: int, db: Session = Depends(get_db)):
    """Serve a thumbnail image for an asset.

    Args:
        slug (str): Share link slug.
        asset_id (int): Asset identifier within the album.
        db (Session): Database session (dependency-injected).

    Returns:
        StreamingResponse | FileResponse: JPEG thumbnail response.

    Raises:
        HTTPException: If the asset is not found or the thumbnail cannot be
            produced.
    """

    sl = load_share(db, slug)
    asset = db.get(models.Asset, asset_id)
    if not asset or asset.album_id != sl.album_id:
        raise HTTPException(status_code=404)

    # Google Drive thumbnail
    if settings.USE_GDRIVE and asset.gdrive_thumb_id:
        generator = gdrive.stream_via_requests(asset.gdrive_thumb_id, chunk_size=256 * 1024)
        return StreamingResponse(generator, media_type="image/jpeg")

    # Local thumbnail
    tpath = thumbs.thumb_path(storage.album_dir(sl.album_id) / asset.filename)
    if not tpath.exists():
        apath = storage.album_dir(sl.album_id) / asset.filename
        thumbs.ensure_thumb(apath)
    if not tpath.exists():
        raise HTTPException(status_code=404)
    return FileResponse(tpath, filename=f"thumb_{asset.original_name}", media_type="image/jpeg")


@router.get("/{slug}/download")
def download_album(slug: str, db: Session = Depends(get_db)):
    """Download an entire album as a ZIP archive.

    Uses Google Drive streaming when enabled; otherwise creates an in-memory
    ZIP from local files.

    Args:
        slug (str): Share link slug.
        db (Session): Database session (dependency-injected).

    Returns:
        StreamingResponse | Response: A ZIP file response.

    Raises:
        HTTPException: If ZIP downloads are disabled (403) or if the required
            streaming package is not installed (500).
    """

    sl = load_share(db, slug)
    if not sl.allow_zip:
        raise HTTPException(status_code=403, detail="ZIP not allowed")

    album = sl.album

    if settings.USE_GDRIVE:
        try:
            from zipstream import ZipStream
        except Exception:
            raise HTTPException(status_code=500, detail="zipstream-ng not installed on server")

        def gen_for(file_id: str):
            """Create a generator streaming a Google Drive file.

            Args:
                file_id (str): Google Drive file identifier.

            Returns:
                Iterator[bytes]: Byte chunks from the remote file.
            """

            return gdrive.stream_via_requests(file_id, chunk_size=256 * 1024)

        zs = ZipStream(mode="w", compression="deflated")
        for asset in album.assets:
            if asset.gdrive_file_id:
                arcname = f"{album.title}/{asset.original_name}"
                zs.add(arcname, gen_for(asset.gdrive_file_id))

        headers = {
            "Content-Disposition": f'attachment; filename="{album.title.replace(" ", "_")}.zip"'
        }
        return StreamingResponse(zs, media_type="application/zip", headers=headers)

    # Local ZIP in-memory
    files = []
    folder = storage.album_dir(album.id)
    for asset in album.assets:
        fpath = folder / asset.filename
        if fpath.exists():
            files.append(fpath)

    zip_bytes = zips.make_zip_in_memory(files, base_prefix=album.title)
    headers = {
        "Content-Disposition": f'attachment; filename="{album.title.replace(" ", "_")}.zip"'
    }
    return Response(content=zip_bytes, media_type="application/zip", headers=headers)
