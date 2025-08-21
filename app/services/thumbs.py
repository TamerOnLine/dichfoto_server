from PIL import Image, ImageOps
from pathlib import Path
from ..config import settings
from io import BytesIO

def is_image(path: Path) -> bool:
    return path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}

def thumb_path(original: Path) -> Path:
    rel = original.relative_to(settings.STORAGE_DIR)
    return settings.THUMBS_DIR / rel

def ensure_thumb(original: Path) -> Path | None:
    if not is_image(original):
        return None

    tpath = thumb_path(original)
    tpath.parent.mkdir(parents=True, exist_ok=True)
    if tpath.exists():
        return tpath

    with Image.open(original) as img:
        # ✅ احترم اتجاه الصورة من EXIF لتفادي انقلاب الطولية/العرضية
        img = ImageOps.exif_transpose(img)

        # (اختياري) توحيد النمط لتفادي مشاكل الشفافية عند حفظ JPG
        if img.mode in ("P", "RGBA"):
            img = img.convert("RGB")

        w, h = img.size
        max_w = settings.THUMB_MAX_WIDTH  # افتراضيًا 800
        if w > max_w:
            ratio = max_w / float(w)
            new_size = (max_w, int(h * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        # يحافظ على النسبة الأصلية؛ لا نغيّر الارتفاع يدويًا
        img.save(tpath)

    return tpath

def make_thumb_bytes(original_bytes: bytes, max_w: int) -> bytes:
    img = Image.open(BytesIO(original_bytes))
    img = ImageOps.exif_transpose(img)
    if img.mode in ("P", "RGBA"):
        img = img.convert("RGB")
    w, h = img.size
    if w > max_w:
        ratio = max_w / float(w)
        img = img.resize((max_w, int(h*ratio)), Image.Resampling.LANCZOS)
    out = BytesIO()
    img.save(out, format="JPEG", quality=88)
    return out.getvalue()
