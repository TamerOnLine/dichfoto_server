# app/routers/public.py
from __future__ import annotations
from typing import Generator
from urllib.parse import quote
from pathlib import Path
import unicodedata

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import SessionLocal
from ..services import gdrive, zips
from ..utils import is_expired, verify_password

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/s", tags=["public"])

def ascii_fallback(name: str) -> str:
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii")
    return n or "file"

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def load_share(db: Session, slug: str) -> models.ShareLink:
    sl = db.query(models.ShareLink).filter(models.ShareLink.slug == slug).first()
    if not sl:
        raise HTTPException(404, "Not found")
    if is_expired(sl.expires_at):
        raise HTTPException(403, "Link expired")
    return sl

def _url(rel: str | None) -> str | None:
    return f"/media/{rel}" if rel else None

def _asset_to_dict(a: models.Asset, slug: str) -> dict:
    return {
        "id": a.id,
        "name": a.original_name,
        "url": f"/s/{slug}/file/{a.id}",       # الأصل عبر الراوتر (محمي/سجل)
        "thumb": f"/s/{slug}/thumb/{a.id}",    # الثمبنيل統 واحد: لو محلي أو درايف
        "width": a.width, "height": a.height, "lqip": a.lqip,
        # مشتقات مباشرة من /media (مسارات نسبية مخزنة)
        "jpg_480": _url(a.jpg_480),   "jpg_960": _url(a.jpg_960),
        "jpg_1280": _url(a.jpg_1280), "jpg_1920": _url(a.jpg_1920),
        "webp_480": _url(a.webp_480), "webp_960": _url(a.webp_960),
        "webp_1280": _url(a.webp_1280), "webp_1920": _url(a.webp_1920),
        "avif_480": _url(a.avif_480), "avif_960": _url(a.avif_960),
        "avif_1280": _url(a.avif_1280), "avif_1920": _url(a.avif_1920),
    }

@router.get("/{slug}", response_class=HTMLResponse)
def open_share(request: Request, slug: str, db: Session = Depends(get_db)):
    sl = load_share(db, slug)
    album = sl.album

    # محمي؟
    if sl.password_hash and not request.session.get(f"unlocked:{slug}"):
        return templates.TemplateResponse("public_album.html", {
            "request": request, "album": album, "share": sl,
           "locked": True, "site_title": settings.SITE_TITLE,
            "hero": None, "gallery_assets": [],
        })

    assets_orm = [a for a in album.assets if not a.is_hidden]
    # ترتيب بالـ sort_order ثم id
    assets_orm.sort(key=lambda a: ((a.sort_order or 0), a.id))

    # اختَر الغلاف (إن وُجد) وإلا أول صورة
    hero_orm = None
    if album.cover_asset_id:
        hero_orm = next((x for x in assets_orm if x.id == album.cover_asset_id), None)
    if not hero_orm and assets_orm:
        hero_orm = assets_orm[0]

    hero = _asset_to_dict(hero_orm, slug) if hero_orm else None
    others = [_asset_to_dict(a, slug) for a in assets_orm if not hero_orm or a.id != hero_orm.id]

    return templates.TemplateResponse("public_album.html", {
        "request": request, "album": album, "share": sl, "locked": False,
        "site_title": settings.SITE_TITLE,
        "hero": hero,
        "gallery_assets": others
    })

@router.post("/{slug}/unlock")
def unlock(request: Request, slug: str, password: str = Form(...), db: Session = Depends(get_db)):
    sl = load_share(db, slug)
    if not sl.password_hash:
        return RedirectResponse(f"/s/{slug}", status_code=302)
    if verify_password(password, sl.password_hash):
        request.session[f"unlocked:{slug}"] = True
        return RedirectResponse(f"/s/{slug}", status_code=302)
    raise HTTPException(403, "Wrong password")

@router.get("/{slug}/file/{asset_id}")
def get_file(slug: str, asset_id: int, db: Session = Depends(get_db)):
    sl = load_share(db, slug)
    a = db.get(models.Asset, asset_id)
    if not a or a.album_id != sl.album_id:
        raise HTTPException(404)

    # Drive؟
    if getattr(settings, "USE_GDRIVE", False) and getattr(a, "gdrive_file_id", None):
        meta = gdrive.get_meta(a.gdrive_file_id)
        original_name = a.original_name or meta.get("name") or "file"
        safe_name = ascii_fallback(original_name)
        headers = {
            "Content-Disposition": (
                f'inline; filename="{safe_name}"; '
                f"filename*=UTF-8''{quote(original_name)}"
            )
        }
        mime = meta.get("mimeType") or "application/octet-stream"
        gen = gdrive.stream_via_requests(a.gdrive_file_id, chunk_size=256 * 1024)
        return StreamingResponse(gen, media_type=mime, headers=headers)

    # محلي
    fpath = Path(settings.STORAGE_DIR) / a.filename
    if not fpath.exists():
        raise HTTPException(404)
    return FileResponse(fpath, filename=a.original_name)

@router.get("/{slug}/thumb/{asset_id}")
def get_thumb(slug: str, asset_id: int, db: Session = Depends(get_db)):
    sl = load_share(db, slug)
    a = db.get(models.Asset, asset_id)
    if not a or a.album_id != sl.album_id:
        raise HTTPException(404)

    if getattr(settings, "USE_GDRIVE", False) and getattr(a, "gdrive_thumb_id", None):
        gen = gdrive.stream_via_requests(a.gdrive_thumb_id, chunk_size=256 * 1024)
        return StreamingResponse(gen, media_type="image/jpeg")

    # محلي من المشتقات الجاهزة
    stem = Path(str(a.filename).replace("\\", "/")).stem
    base = Path(settings.STORAGE_DIR) / "albums" / str(a.album_id) / "thumb" / "400"
    jpg = base / f"{stem}.jpg"; webp = base / f"{stem}.webp"
    if jpg.exists():  return FileResponse(jpg, media_type="image/jpeg")
    if webp.exists(): return FileResponse(webp, media_type="image/webp")

    # fallback
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="260">'
           '<rect width="100%" height="100%" fill="#e2e8f0"/>'
           '<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" '
           'font-family="Segoe UI, Roboto, sans-serif" font-size="16" fill="#64748b">No preview</text>'
           '</svg>')
    return Response(content=svg, media_type="image/svg+xml")


