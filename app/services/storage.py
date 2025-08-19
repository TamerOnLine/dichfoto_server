from pathlib import Path
from typing import Iterable
import shutil
from ..config import settings

def album_dir(album_id: int) -> Path:
    d = settings.STORAGE_DIR / f"album_{album_id:06d}"
    d.mkdir(parents=True, exist_ok=True)
    return d

def save_file(album_id: int, src_path: Path, original_name: str) -> Path:
    dst_folder = album_dir(album_id)
    dst_path = dst_folder / original_name
    # Ensure unique filename
    i = 1
    while dst_path.exists():
        stem = dst_path.stem
        suffix = dst_path.suffix
        dst_path = dst_folder / f"{stem} ({i}){suffix}"
        i += 1
    shutil.copy2(src_path, dst_path)
    return dst_path

def save_upload(album_id: int, file_obj, original_name: str) -> Path:
    dst_folder = album_dir(album_id)
    dst_path = dst_folder / original_name
    # Ensure unique filename
    i = 1
    while dst_path.exists():
        stem = dst_path.stem
        suffix = dst_path.suffix
        dst_path = dst_folder / f"{stem} ({i}){suffix}"
        i += 1
    with open(dst_path, "wb") as f:
        shutil.copyfileobj(file_obj, f)
    return dst_path

def iter_files(paths: Iterable[Path]):
    for p in paths:
        if p.is_file():
            yield p
