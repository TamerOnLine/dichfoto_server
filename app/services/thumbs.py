from PIL import Image
from pathlib import Path
from ..config import settings

def is_image(path: Path) -> bool:
    return path.suffix.lower() in {".jpg",".jpeg",".png",".webp",".gif"}

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
        w, h = img.size
        max_w = settings.THUMB_MAX_WIDTH
        if w > max_w:
            ratio = max_w / float(w)
            new_size = (max_w, int(h * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        img.save(tpath)
    return tpath
