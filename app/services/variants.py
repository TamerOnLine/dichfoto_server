from __future__ import annotations
from pathlib import Path
from typing import Iterable, Literal
from PIL import Image, ImageOps

VariantName = Literal["thumb", "disp", "big"]

# أحجامنا القياسية
SIZES: dict[VariantName, int] = {
    "thumb": 400,   # للغريد
    "disp": 1600,   # للعرض داخل اللايت بوكس
    "big":  2048,   # اختيارية للشاشات الكبيرة
}

def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)

def _save_jpeg(im: Image.Image, path: Path) -> None:
    _ensure_dir(path)
    im.save(path, format="JPEG", quality=80, optimize=True, progressive=True)

def _save_webp(im: Image.Image, path: Path) -> None:
    _ensure_dir(path)
    im.save(path, format="WEBP", quality=80, method=6)

def _resize_fit(im: Image.Image, target_w: int) -> Image.Image:
    w, h = im.size
    if w <= target_w:
        return im
    new_h = round(h * (target_w / w))
    return im.resize((target_w, new_h), Image.LANCZOS)

def make_variants(
    original_path: Path,
    out_root: Path,
    album_id: int,
    filename_stem: str,
    create: Iterable[VariantName] = ("thumb", "disp", "big"),
) -> dict[str, str]:
    """
    ينشئ JPG + WebP لكل حجم ويعيد مسارات نسبية يمكن استعمالها لاحقًا في القوالب.
    out_root = settings.STORAGE_DIR
    """
    results: dict[str, str] = {}

    with Image.open(original_path) as im0:
        # احترام اتجاه EXIF وتوحيد القناة
        im0 = ImageOps.exif_transpose(im0).convert("RGB")

        for kind in create:
            width = SIZES[kind]
            im = _resize_fit(im0, width)

            subdir = {"thumb": "thumb/400", "disp": "disp/1600", "big": "big/2048"}[kind]
            jpg_rel  = Path(f"albums/{album_id}/{subdir}/{filename_stem}.jpg")
            webp_rel = Path(f"albums/{album_id}/{subdir}/{filename_stem}.webp")

            _save_jpeg(im, out_root / jpg_rel)
            _save_webp(im, out_root / webp_rel)

            results[f"{kind}_jpg"]  = jpg_rel.as_posix()
            results[f"{kind}_webp"] = webp_rel.as_posix()

    return results
