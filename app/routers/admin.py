from fastapi import (
    APIRouter, Depends, Request,
    UploadFile, File, Form, HTTPException
)
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from slugify import slugify
import shutil

from ..database import SessionLocal
from .. import models
from ..config import settings
from ..utils import gen_slug, hash_password
from ..services import storage, thumbs, gdrive

templates = Jinja2Templates(directory="templates")

# راوتر واحد فقط (لا تكرر التعريف)
router = APIRouter(prefix="/admin", tags=["admin"])


# ---------- Helpers ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_admin(request: Request) -> bool:
    return bool(request.session.get("admin"))


def require_admin(request: Request):
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="Not authorized")


# ---------- Routes ----------

# ✅ alias: يدعم /admin و /admin/
@router.get("", include_in_schema=False)
def admin_no_slash():
    """Redirect /admin → /admin/ (301 Moved Permanently)."""
    return RedirectResponse(url="/admin/", status_code=301)


@router.get("/", response_class=HTMLResponse)
def admin_home(request: Request):
    """
    لو المستخدم مش مسجل → اعرض صفحة الدخول.
    لو مسجل → حوّله مباشرة لصفحة إنشاء الألبوم (أو اعرض dashboard لاحقاً).
    """
    if not is_admin(request):
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "site_title": settings.SITE_TITLE}
        )
    return RedirectResponse(url="/admin/albums/new", status_code=302)


@router.get("/albums/new", response_class=HTMLResponse)
def album_new_form(request: Request):
    require_admin(request)
    return templates.TemplateResponse(
        "admin_album_new.html",
        {"request": request, "site_title": settings.SITE_TITLE}
    )


@router.post("/albums/new")
def create_album(
    request: Request,
    title: str = Form(...),
    photographer: Optional[str] = Form(None),
    event_date: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
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

    assets = []
    for a in album.assets:
        if settings.USE_GDRIVE and a.gdrive_thumb_id:
            # thumbnail عبر Proxy من Drive
            t_rel = f"/admin/thumb/{a.id}"
        else:
            # Local fallback
            album_path = storage.album_dir(album.id)
            full_path = album_path / a.filename
            tpath = thumbs.ensure_thumb(full_path)
            if tpath:
                try:
                    t_rel = "/static/thumbs/" + str(
                        tpath.relative_to(settings.THUMBS_DIR)
                    ).replace("\\", "/")
                except Exception:
                    t_rel = None
            else:
                t_rel = None
        assets.append({"id": a.id, "name": a.original_name, "thumb": t_rel})

    return templates.TemplateResponse(
        "admin_album_view.html",
        {
            "request": request,
            "site_title": settings.SITE_TITLE,
            "album": album,
            "assets": assets
        }
    )


@router.post("/albums/{album_id}/upload")
async def upload_files(
    request: Request,
    album_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    require_admin(request)
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(404)

    # =============== Google Drive ===============
    if settings.USE_GDRIVE:
        if not settings.GDRIVE_ROOT_FOLDER_ID:
            raise HTTPException(500, "Google Drive storage not configured")

        service = gdrive._service()
        album_folder_id = gdrive.ensure_subfolder(
            service, settings.GDRIVE_ROOT_FOLDER_ID, f"album_{album.id:06d}"
        )
        thumbs_folder_id = gdrive.ensure_subfolder(service, album_folder_id, "_thumbs")

        for uf in files:
            data = await uf.read()
            file_id = gdrive.upload_bytes(
                service, album_folder_id, uf.filename, uf.content_type, data
            )
            tbytes = thumbs.make_thumb_bytes(data, settings.THUMB_MAX_WIDTH)
            tname = f"thumb_{uf.filename.rsplit('.',1)[0]}.jpg"
            t_id = gdrive.upload_bytes(service, thumbs_folder_id, tname, "image/jpeg", tbytes)

            asset = models.Asset(
                album_id=album.id,
                filename=uf.filename,
                original_name=uf.filename,
                mime_type=uf.content_type or "application/octet-stream",
                size=len(data),
                gdrive_file_id=file_id,
                gdrive_thumb_id=t_id,
            )
            db.add(asset)

        db.commit()
        return RedirectResponse(url=f"/admin/albums/{album.id}", status_code=302)

    # =============== Local storage ===============
    for uf in files:
        dst_folder = storage.album_dir(album.id)
        dst_folder.mkdir(parents=True, exist_ok=True)
        dst_path = dst_folder / uf.filename
        i = 1
        while dst_path.exists():
            stem, suffix = dst_path.stem, dst_path.suffix
            dst_path = dst_folder / f"{stem} ({i}){suffix}"
            i += 1
        with open(dst_path, "wb") as f:
            shutil.copyfileobj(uf.file, f)
        size = dst_path.stat().st_size
        asset = models.Asset(
            album_id=album.id,
            filename=dst_path.name,
            original_name=uf.filename,
            mime_type=uf.content_type or "application/octet-stream",
            size=size
        )
        db.add(asset)

    db.commit()
    return RedirectResponse(url=f"/admin/albums/{album.id}", status_code=302)


@router.get("/thumb/{asset_id}")
def admin_thumb(asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(models.Asset, asset_id)
    if not asset:
        raise HTTPException(404)
    if settings.USE_GDRIVE and asset.gdrive_thumb_id:
        service = gdrive._service()
        gen = gdrive.download_to_generator(service, asset.gdrive_thumb_id)
        return StreamingResponse(gen, media_type="image/jpeg")
    raise HTTPException(404)


@router.get("/login", response_class=HTMLResponse)
def admin_login_form(request: Request):
    # لو أصلاً مسجّل، ودِّيه مباشرة
    if is_admin(request):
        return RedirectResponse(url="/admin/albums/new", status_code=302)
    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request, "site_title": settings.SITE_TITLE}
    )


@router.post("/login")
def admin_login(request: Request, password: str = Form(...)):
    if password == settings.ADMIN_PASSWORD:
        request.session["admin"] = True
        return RedirectResponse(url="/admin/albums/new", status_code=302)
    # فشل: ارجع لنفس صفحة الدخول
    return RedirectResponse(url="/admin", status_code=302)

# ✅ يدعم POST بشكل صريح، ويعالج GET بتحويل واضح
@router.api_route("/albums/{album_id}/share", methods=["POST"])
def create_share(
    request: Request,
    album_id: int,
    expires_at: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    allow_zip: Optional[bool] = Form(True),
    db: Session = Depends(get_db)
):
    require_admin(request)
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(404, "Album not found")

    exp = None
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at)
        except Exception:
            exp = None

    slug = slugify(album.title)[:20] + "-" + gen_slug(4)
    pwd_hash = hash_password(password) if password else None

    sl = models.ShareLink(
        album_id=album.id,
        slug=slug,
        expires_at=exp,
        password_hash=pwd_hash,
        allow_zip=bool(allow_zip),
    )
    db.add(sl)
    db.commit()
    db.refresh(sl)
    return RedirectResponse(url=f"/s/{sl.slug}", status_code=302)


# (اختياري) لو أحد فتح الرابط مباشرة GET /admin/albums/{id}/share
@router.get("/albums/{album_id}/share", include_in_schema=False)
def create_share_get(album_id: int):
    # وضوح أفضل من 404 الغامض
    return RedirectResponse(url=f"/admin/albums/{album_id}", status_code=302)
