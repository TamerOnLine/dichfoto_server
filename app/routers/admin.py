from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from slugify import slugify

from ..database import SessionLocal
from .. import models, schemas
from ..config import settings
from ..utils import gen_slug, hash_password
from ..services import storage, thumbs

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/admin", tags=["admin"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def require_admin(request: Request):
    if not request.session.get("admin"):
        raise HTTPException(status_code=403, detail="Not authorized")


@router.get("/", response_class=HTMLResponse)
def admin_home(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request, "site_title": settings.SITE_TITLE})


@router.post("/login")
def admin_login(request: Request, password: str = Form(...)):
    if password == settings.ADMIN_PASSWORD:
        request.session["admin"] = True
        return RedirectResponse(url="/admin/albums/new", status_code=302)
    return RedirectResponse(url="/admin", status_code=302)


@router.get("/albums/new", response_class=HTMLResponse)
def album_new_form(request: Request):
    require_admin(request)
    return templates.TemplateResponse("admin_album_new.html", {"request": request, "site_title": settings.SITE_TITLE})


@router.post("/albums/new")
def create_album(request: Request, title: str = Form(...), photographer: Optional[str] = Form(None), event_date: Optional[str] = Form(None), db: Session = Depends(get_db)):
    require_admin(request)
    ed = None
    if event_date:
        try:
            ed = datetime.fromisoformat(event_date)
        except Exception:
            ed = None
    album = models.Album(title=title, photographer=photographer, event_date=ed)
    db.add(album)
    db.commit()
    db.refresh(album)
    return RedirectResponse(url=f"/admin/albums/{album.id}", status_code=302)


@router.get("/albums/{album_id}", response_class=HTMLResponse)
def view_album(request: Request, album_id: int, db: Session = Depends(get_db)):
    require_admin(request)
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(404)
    # Prepare asset info + thumbs
    assets = []
    for a in album.assets:
        album_path = storage.album_dir(album.id)
        full_path = album_path / a.filename
        tpath = thumbs.ensure_thumb(full_path)
        t_rel = None
        if tpath:
            try:
                t_rel = "/static/thumbs/" + str(tpath.relative_to(settings.THUMBS_DIR)).replace("\\", "/")
            except Exception:
                t_rel = None
        assets.append({"id": a.id, "name": a.original_name, "thumb": t_rel})
    return templates.TemplateResponse("admin_album_view.html", {"request": request, "site_title": settings.SITE_TITLE, "album": album, "assets": assets})


@router.post("/albums/{album_id}/upload")
async def upload_files(request: Request, album_id: int, files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    require_admin(request)
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(404)
    import os, shutil, pathlib
    for uf in files:
        # Save to storage
        dst_folder = storage.album_dir(album.id)
        dst_folder.mkdir(parents=True, exist_ok=True)
        dst_path = dst_folder / uf.filename
        # Ensure unique filename
        i = 1
        while dst_path.exists():
            stem = dst_path.stem
            suffix = dst_path.suffix
            dst_path = dst_folder / f"{stem} ({i}){suffix}"
            i += 1
        with open(dst_path, "wb") as f:
            shutil.copyfileobj(uf.file, f)
        size = dst_path.stat().st_size
        asset = models.Asset(album_id=album.id, filename=dst_path.name, original_name=uf.filename, mime_type=uf.content_type, size=size)
        db.add(asset)
    db.commit()
    return RedirectResponse(url=f"/admin/albums/{album.id}", status_code=302)


@router.post("/albums/{album_id}/share")
def create_share(request: Request, album_id: int, expires_at: Optional[str] = Form(None), password: Optional[str] = Form(None), allow_zip: Optional[bool] = Form(True), db: Session = Depends(get_db)):
    require_admin(request)
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(404)
    exp = None
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
        except Exception:
            exp = None
    slug = slugify(album.title)[:20] + "-" + gen_slug(4)
    pwd_hash = hash_password(password) if password else None
    sl = models.ShareLink(album_id=album.id, slug=slug, expires_at=exp, password_hash=pwd_hash, allow_zip=bool(allow_zip))
    db.add(sl)
    db.commit()
    db.refresh(sl)
    return RedirectResponse(url=f"/s/{sl.slug}", status_code=302)
