from __future__ import annotations
from pathlib import Path
from io import BytesIO
from typing import Dict
from PIL import Image, ImageOps
import base64
from ..config import settings

# ✅ فعّل كوديك AVIF إذا كانت الحزمة موجودة
try:
    import pillow_avif  # noqa: F401
except Exception as e:
    print("[avif] pillow-avif-plugin not available:", e)

# ✅ فلاغات من .env
ENABLE_WEBP = getattr(settings, "ENABLE_WEBP", True)
ENABLE_AVIF = getattr(settings, "ENABLE_AVIF", False)

# ✅ الامتدادات المقبولة (يشمل avif لو تحب ترفع أصل .avif)
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}

TARGET_WIDTHS = [480, 960, 1280, 1920]
THUMB_QUALITY = 88
VARIANT_QUALITY = 78

def is_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTS

def thumb_path(original: Path) -> Path:
    rel = Path(original).relative_to(Path(settings.STORAGE_DIR))
    out = Path(settings.THUMBS_DIR) / rel
    # إن FORCE_JPEG مفعّل: خزّن thumb كـ jpg
    return out.with_suffix(".jpg") if settings.FORCE_JPEG else out

def _variant_out_path(original: Path, suffix: str, ext: str) -> Path:
    rel = Path(original).relative_to(Path(settings.STORAGE_DIR))
    out_dir = Path(settings.THUMBS_DIR) / rel.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{rel.stem}{suffix}.{ext}"

def _normalize(img: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(img)
    if im.mode in ("P", "RGBA"):
        im = im.convert("RGB")
    return im

def ensure_thumb(original: Path) -> Path | None:
    if not is_image(original):
        return None
    tpath = thumb_path(original)
    tpath.parent.mkdir(parents=True, exist_ok=True)
    if tpath.exists():
        return tpath

    with Image.open(original) as img:
        img = _normalize(img)
        w, h = img.size
        max_w = int(getattr(settings, "THUMB_MAX_WIDTH", 800))
        if w > max_w:
            ratio = max_w / float(w)
            img = img.resize((max_w, int(h * ratio)), Image.Resampling.LANCZOS)

        if settings.FORCE_JPEG:
            img.save(tpath.with_suffix(".jpg"), "JPEG",
                     quality=THUMB_QUALITY, optimize=True, progressive=True)
            tpath = tpath.with_suffix(".jpg")
        else:
            ext = tpath.suffix.lower()
            if ext in (".jpg", ".jpeg"):
                img.save(tpath, "JPEG", quality=THUMB_QUALITY, optimize=True, progressive=True)
            elif ext == ".png":
                img.save(tpath, "PNG", optimize=True)
            elif ext == ".webp":
                img.save(tpath, "WEBP", quality=THUMB_QUALITY, method=6)
            else:
                tpath = tpath.with_suffix(".jpg")
                img.save(tpath, "JPEG", quality=THUMB_QUALITY, optimize=True, progressive=True)
    return tpath

def make_thumb_bytes(original_bytes: bytes, max_w: int) -> bytes:
    img = Image.open(BytesIO(original_bytes))
    img = _normalize(img)
    w, h = img.size
    if w > max_w:
        ratio = max_w / float(w)
        img = img.resize((max_w, int(h * ratio)), Image.Resampling.LANCZOS)
    out = BytesIO()
    img.save(out, format="JPEG", quality=THUMB_QUALITY, optimize=True, progressive=True)
    return out.getvalue()

def ensure_variants(original: Path) -> Dict:
    out: Dict[str, Dict[int, str] | int] = {"jpg": {}, "webp": {}, "avif": {}}
    with Image.open(original) as im0:
        im0 = _normalize(im0)
        w0, h0 = im0.size
        out["width"], out["height"] = w0, h0

        for tw in TARGET_WIDTHS:
            target_w = min(tw, w0)
            target_h = int(h0 * (target_w / w0)) if w0 else h0
            im = im0.resize((target_w, target_h), Image.Resampling.LANCZOS)

            # JPG (دائمًا)
            jpg_path = _variant_out_path(original, f"-{target_w}", "jpg")
            if not jpg_path.exists():
                im.save(jpg_path, "JPEG", quality=VARIANT_QUALITY, optimize=True, progressive=True)
            rel = str(jpg_path.relative_to(Path(settings.THUMBS_DIR))).replace("\\", "/")
            out["jpg"][target_w] = f"/static/thumbs/{rel}"

            # WEBP (حسب الفلاغ)
            if ENABLE_WEBP:
                webp_path = _variant_out_path(original, f"-{target_w}", "webp")
                if not webp_path.exists():
                    im.save(webp_path, "WEBP", quality=VARIANT_QUALITY, method=6)
                rel = str(webp_path.relative_to(Path(settings.THUMBS_DIR))).replace("\\", "/")
                out["webp"][target_w] = f"/static/thumbs/{rel}"

            # AVIF (حسب الفلاغ + توافر الكوديك)
            if ENABLE_AVIF:
                try:
                    avif_path = _variant_out_path(original, f"-{target_w}", "avif")
                    if not avif_path.exists():
                        im.save(avif_path, "AVIF", quality=VARIANT_QUALITY)
                    rel = str(avif_path.relative_to(Path(settings.THUMBS_DIR))).replace("\\", "/")
                    out["avif"][target_w] = f"/static/thumbs/{rel}"
                except Exception:
                    pass

    return out

def tiny_placeholder_base64(original: Path, size: int = 24) -> str:
    with Image.open(original) as im:
        im = _normalize(im)
        w, h = im.size
        ratio = h / w if w else 1.0
        im_small = im.resize((size, max(1, int(size * ratio))), Image.Resampling.LANCZOS)
        buf = BytesIO()
        im_small.save(buf, format="JPEG", quality=30)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
