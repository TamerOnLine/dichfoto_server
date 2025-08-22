from fastapi import (
    APIRouter, Depends, Request, UploadFile, File, Form,
    HTTPException, Response
)
from fastapi.responses import (
    HTMLResponse, RedirectResponse, StreamingResponse, FileResponse
)
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from slugify import slugify
from pathlib import Path
import json
from pydantic import BaseModel

from ..database import SessionLocal
from .. import models
from ..config import settings
from ..utils import gen_slug, hash_password
from ..services import thumbs, gdrive

templates = Jinja2Templates(directory="templates")

router = APIRouter(prefix="/admin", tags=["admin"])

# ===========================
# Theme config (simple JSON)
# ===========================
THEME_PATH = Path("static/theme.json")


class ThemePayload(BaseModel):
    vars: dict[str, str] = {}
    disableDark: bool = False


@router.get("/theme", response_class=HTMLResponse)
def theme_page(request: Request):
    require_admin(request)
    return templates.TemplateResponse("admin/theme.html", {"request": request})


@router.post("/theme/save")
def theme_save(payload: ThemePayload, request: Request):
    require_admin(request)
    THEME_PATH.write_text(
        json.dumps(payload.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"ok": True}


@router.post("/theme/reset")
def theme_reset(request: Request):
    require_admin(request)
    if THEME_PATH.exists():
        THEME_PATH.unlink()
    return {"ok": True}


@router.get("/theme/config")
def theme_config():
    """
    يعيد theme.json إن وُجد، وإلا يعيد إعدادات افتراضية.
    لا يتطلب صلاحية admin لأن كل الصفحات تحتاج قراءته.
    """
    if THEME_PATH.exists():
        data = json.loads(THEME_PATH.read_text(encoding="utf-8"))
    else:
        data = {
            "vars": {},          # استخدم قيم :root الافتراضية من style.css
            "disableDark": False # مثال لفلاغ إضافي
        }
    return data


# ================
# Helpers
# ================
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


# ================
# Routes
# ================
@router.get("", include_in_schema=False)
def admin_no_slash():
    """Redirect /admin → /admin/ (301 Moved Permanently)."""
    return RedirectResponse(url="/admin/", status_code=301)


@router.get("/", response_class=HTMLResponse)
def admin_home(request: Request):
    if not is_admin(request):
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "site_title": settings.SITE_TITLE},
        )
    return RedirectResponse(url="/admin/albums/new", status_code=302)


@router.get("/albums/new", response_class=HTMLResponse)
def album_new_form(request: Request):
    require_admin(request)
    return templates.TemplateResponse(
        "admin_album_new.html",
        {"request": request, "site_title": settings.SITE_TITLE},
    )


@router.post("/albums/new")
def create_album(
    request: Request,
    title: str = Form(...),
    photographer: Optional[str] = Form(None),
    event_date: Optional[str] = Form(None),
    db: Session = Depends(get_db),
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

    assets = [
        {"id": a.id, "name": a.original_name, "thumb": f"/admin/thumb/{a.id}"}
        for a in album.assets
    ]

    return templates.TemplateResponse(
        "admin_album_view.html",
        {
            "request": request,
            "site_title": settings.SITE_TITLE,
            "album": album,
            "assets": assets,
        },
    )


@router.post("/albums/{album_id}/upload")
async def upload_files(
    album_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    require_admin  # just to be explicit if you want to add it; auth already enforced on page
    album = db.get(models.Album, album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    saved_assets = []
    album_dir = Path(settings.STORAGE_DIR) / f"album_{album_id}"
    album_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        original_path = album_dir / file.filename
        with open(original_path, "wb") as f:
            f.write(await file.read())

        # thumbs + variants + lqip
        thumbs.ensure_thumb(original_path)
        variants = thumbs.ensure_variants(original_path)
        lqip = thumbs.tiny_placeholder_base64(original_path)

        asset = models.Asset(
            album_id=album.id,
            filename=str(original_path.relative_to(settings.STORAGE_DIR)),
            original_name=file.filename,
            mime_type=file.content_type,
            size=original_path.stat().st_size,
        )
        asset.set_variants(variants)
        asset.lqip = lqip
        db.add(asset)
        saved_assets.append(asset)

    db.commit()
    return {"ok": True, "uploaded": [a.id for a in saved_assets]}


@router.get("/thumb/{asset_id}")
def admin_thumb(asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(models.Asset, asset_id)
    if not asset:
        raise HTTPException(404)

    # Google Drive thumbnail (لو مفعّل وبها أعمدة في الموديل)
    if getattr(settings, "USE_GDRIVE", False) and getattr(asset, "gdrive_thumb_id", None):
        try:
            gen = gdrive.stream_via_requests(asset.gdrive_thumb_id, chunk_size=256 * 1024)
            return StreamingResponse(gen, media_type="image/jpeg")
        except Exception:
            pass

    # Local file → ensure/load thumb
    apath = Path(settings.STORAGE_DIR) / asset.filename
    tpath = thumbs.ensure_thumb(apath)
    if tpath and tpath.exists():
        return FileResponse(tpath, media_type="image/jpeg")

    # Fallback SVG
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="260">'
        '<rect width="100%" height="100%" fill="#e2e8f0"/>'
        '<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" '
        'font-family="Segoe UI, Roboto, sans-serif" font-size="16" fill="#64748b">No preview</text>'
        "</svg>"
    )
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/login", response_class=HTMLResponse)
def admin_login_form(request: Request):
    if is_admin(request):
        return RedirectResponse(url="/admin/albums/new", status_code=302)
    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request, "site_title": settings.SITE_TITLE},
    )


@router.post("/login")
def admin_login(request: Request, password: str = Form(...)):
    if password == settings.ADMIN_PASSWORD:
        request.session["admin"] = True
        return RedirectResponse(url="/admin/albums/new", status_code=302)
    return RedirectResponse(url="/admin", status_code=302)


@router.api_route("/albums/{album_id}/share", methods=["POST"])
def create_share(
    request: Request,
    album_id: int,
    expires_at: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    allow_zip: Optional[bool] = Form(True),
    db: Session = Depends(get_db),
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


@router.get("/albums/{album_id}/share", include_in_schema=False)
def create_share_get(album_id: int):
    return RedirectResponse(url=f"/admin/albums/{album_id}", status_code=302)
