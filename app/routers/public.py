# app/routers/public.py  (مقتطف كامل جاهز)
from fastapi import APIRouter, Depends, Request, HTTPException, Form, Response
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from ..database import SessionLocal
from .. import models
from ..config import settings
from ..utils import verify_password, is_expired
from ..services import storage, thumbs, gdrive, zips  # zips موجودة لديك لِـ local

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

    # حماية بكلمة مرور
    if sl.password_hash and not request.session.get(f"unlocked:{slug}"):
        return templates.TemplateResponse(
            "public_album.html",
            {"request": request, "album": album, "share": sl, "locked": True, "site_title": settings.SITE_TITLE, "assets": []}
        )

    # جهّز قائمة العناصر + روابط الـthumb/file حسب المصدر
    assets_info = []
    for a in album.assets:
        if settings.USE_GDRIVE and a.gdrive_thumb_id:
            t_rel = f"/s/{slug}/thumb/{a.id}"
        else:
            # Local: توليد/تأكيد الثمبنيل على القرص
            apath = storage.album_dir(album.id) / a.filename
            tpath = thumbs.ensure_thumb(apath)
            if tpath:
                try:
                    t_rel = "/static/thumbs/" + str(tpath.relative_to(settings.THUMBS_DIR)).replace("\\", "/")
                except Exception:
                    t_rel = None
            else:
                t_rel = None

        assets_info.append({
            "id": a.id,
            "name": a.original_name,
            "url": f"/s/{slug}/file/{a.id}",
            "thumb": t_rel
        })

    return templates.TemplateResponse(
        "public_album.html",
        {"request": request, "album": album, "share": sl, "locked": False, "site_title": settings.SITE_TITLE, "assets": assets_info}
    )

@router.post("/{slug}/unlock")
def unlock(request: Request, slug: str, password: str = Form(...), db: Session = Depends(get_db)):
    sl = load_share(db, slug)
    if not sl.password_hash:
        return RedirectResponse(f"/s/{slug}", status_code=302)
    if verify_password(password, sl.password_hash):
        request.session[f"unlocked:{slug}"] = True
        return RedirectResponse(f"/s/{slug}", status_code=302)
    raise HTTPException(403, "Wrong password")

# ---------- File / Thumb with fallback ----------
@router.get("/{slug}/file/{asset_id}")
def get_file(slug: str, asset_id: int, db: Session = Depends(get_db)):
    sl = load_share(db, slug)
    asset = db.get(models.Asset, asset_id)
    if not asset or asset.album_id != sl.album_id:
        raise HTTPException(404)

    if settings.USE_GDRIVE and asset.gdrive_file_id:
        service = gdrive._service()
        meta = gdrive.get_metadata(service, asset.gdrive_file_id, fields="id,name,mimeType,size")
        gen = gdrive.download_to_generator(service, asset.gdrive_file_id)
        headers = {"Content-Disposition": f'inline; filename="{asset.original_name}"'}
        return StreamingResponse(gen, media_type=meta.get("mimeType") or "application/octet-stream", headers=headers)

    # Local
    fpath = storage.album_dir(sl.album_id) / asset.filename
    if not fpath.exists():
        raise HTTPException(404)
    return FileResponse(fpath, filename=asset.original_name)

@router.get("/{slug}/thumb/{asset_id}")
def get_thumb(slug: str, asset_id: int, db: Session = Depends(get_db)):
    sl = load_share(db, slug)
    asset = db.get(models.Asset, asset_id)
    if not asset or asset.album_id != sl.album_id:
        raise HTTPException(404)

    if settings.USE_GDRIVE and asset.gdrive_thumb_id:
        service = gdrive._service()
        gen = gdrive.download_to_generator(service, asset.gdrive_thumb_id)
        return StreamingResponse(gen, media_type="image/jpeg")

    # Local: أعطِ الثمبنيل من المجلد الثابت (بعد ما ضمنّا توليده في open_share)
    tpath = thumbs.thumb_path(storage.album_dir(sl.album_id) / asset.filename)
    if not tpath.exists():
        # محاولة توليد عند الطلب
        apath = storage.album_dir(sl.album_id) / asset.filename
        thumbs.ensure_thumb(apath)
    if not tpath.exists():
        raise HTTPException(404)
    return FileResponse(tpath, filename=f"thumb_{asset.original_name}", media_type="image/jpeg")

# ---------- ZIP download with fallback ----------
@router.get("/{slug}/download")
def download_album(slug: str, db: Session = Depends(get_db)):
    sl = load_share(db, slug)
    if not sl.allow_zip:
        raise HTTPException(403, "ZIP not allowed")
    album = sl.album

    if settings.USE_GDRIVE:
        # (اختياري) يتطلب zipstream-ng إن حبيت ستريم فعلي
        # من دون zipstream، يمكنك تجميع bytes مؤقتًا (غير محبّذ للألبومات الكبيرة)
        try:
            from zipstream import ZipStream  # pip install zipstream-ng
        except Exception:
            raise HTTPException(500, "zipstream-ng not installed on server")

        service = gdrive._service()

        def gen_for(file_id: str):
            yield from gdrive.download_to_generator(service, file_id)

        zs = ZipStream(mode='w', compression='deflated')
        for a in album.assets:
            if a.gdrive_file_id:
                arc = f"{album.title}/{a.original_name}"
                zs.add(arc, gen_for(a.gdrive_file_id))

        headers = {"Content-Disposition": f'attachment; filename="{album.title.replace(" ", "_")}.zip"'}
        return StreamingResponse(zs, media_type="application/zip", headers=headers)

    # Local: استخدم خدمة الزب القديمة لديك (in-memory)
    files = []
    folder = storage.album_dir(album.id)
    for a in album.assets:
        f = folder / a.filename
        if f.exists():
            files.append(f)
    zip_bytes = zips.make_zip_in_memory(files, base_prefix=album.title)
    headers = {"Content-Disposition": f'attachment; filename="{album.title.replace(" ", "_")}.zip"'}
    return Response(content=zip_bytes, media_type="application/zip", headers=headers)
