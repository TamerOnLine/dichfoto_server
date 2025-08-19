from fastapi import APIRouter, Depends, Request, HTTPException, Form, Response
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from ..database import SessionLocal
from .. import models
from ..config import settings
from ..utils import verify_password, is_expired
from ..services import storage, thumbs, zips

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/s", tags=["public"])

def get_db():
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

@router.get("/{slug}", response_class=HTMLResponse)
def open_share(request: Request, slug: str, db: Session = Depends(get_db)):
    sl = load_share(db, slug)
    album = sl.album
    # If password protected and not unlocked:
    if sl.password_hash and not request.session.get(f"unlocked:{slug}"):
        return templates.TemplateResponse("public_album.html", {"request": request, "album": album, "share": sl, "locked": True, "site_title": settings.SITE_TITLE, "assets": []})

    # Build assets list with thumbs
    assets_info = []
    for a in album.assets:
        apath = storage.album_dir(album.id) / a.filename
        tpath = thumbs.ensure_thumb(apath)
        t_rel = None
        if tpath:
            try:
                t_rel = "/static/thumbs/" + str(tpath.relative_to(settings.THUMBS_DIR)).replace("\\", "/")
            except Exception:
                t_rel = None
        assets_info.append({"id": a.id, "name": a.original_name, "url": f"/s/{slug}/file/{a.id}", "thumb": t_rel})

    return templates.TemplateResponse("public_album.html", {"request": request, "album": album, "share": sl, "locked": False, "site_title": settings.SITE_TITLE, "assets": assets_info})

@router.post("/{slug}/unlock")
def unlock(request: Request, slug: str, password: str = Form(...), db: Session = Depends(get_db)):
    sl = load_share(db, slug)
    if not sl.password_hash:
        return RedirectResponse(f"/s/{slug}", status_code=302)
    if verify_password(password, sl.password_hash):
        request.session[f"unlocked:{slug}"] = True
        from fastapi.responses import RedirectResponse
        return RedirectResponse(f"/s/{slug}", status_code=302)
    raise HTTPException(403, "Wrong password")


@router.get("/{slug}/file/{asset_id}")
def get_file(slug: str, asset_id: int, db: Session = Depends(get_db)):
    sl = load_share(db, slug)
    asset = db.get(models.Asset, asset_id)
    if not asset or asset.album_id != sl.album_id:
        raise HTTPException(404)
    fpath = storage.album_dir(sl.album_id) / asset.filename
    if not fpath.exists():
        raise HTTPException(404)
    return FileResponse(fpath, filename=asset.original_name)

@router.get("/{slug}/download")
def download_album(slug: str, db: Session = Depends(get_db)):
    sl = load_share(db, slug)
    if not sl.allow_zip:
        raise HTTPException(403, "ZIP not allowed")
    album = sl.album
    files = []
    folder = storage.album_dir(album.id)
    for a in album.assets:
        f = folder / a.filename
        if f.exists():
            files.append(f)
    zip_bytes = zips.make_zip_in_memory(files, base_prefix=album.title)
    headers = {"Content-Disposition": f"attachment; filename={album.title.replace(' ', '_')}.zip"}
    return Response(content=zip_bytes, media_type="application/zip", headers=headers)
