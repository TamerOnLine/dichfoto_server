from pathlib import Path
from typing import Iterable
import zipfile
import io

def make_zip_in_memory(files: Iterable[Path], base_prefix: str = "") -> bytes:
    # For moderate album sizes. For massive collections, switch to streaming ZIP.
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fpath in files:
            arcname = f"{base_prefix}/{fpath.name}" if base_prefix else fpath.name
            zf.write(fpath, arcname=arcname)
    mem.seek(0)
    return mem.read()
