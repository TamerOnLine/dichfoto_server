# app/services/lqip.py
from pathlib import Path
from PIL import Image, ImageOps
import io, base64

def tiny_placeholder_base64(original_path: Path, width: int = 24) -> str:
    with Image.open(original_path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        w, h = im.size
        if w > width:
            im = im.resize((width, int(h * width / w)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=30, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
