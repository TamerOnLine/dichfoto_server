from pathlib import Path
from typing import Iterable, Generator
import shutil
from ..config import settings


def album_dir(album_id: int) -> Path:
    """Create and return the directory path for a given album.

    Args:
        album_id (int): The unique identifier of the album.

    Returns:
        Path: The path to the album directory. The directory is created
        if it does not already exist.
    """
    directory = settings.STORAGE_DIR / f"album_{album_id:06d}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_file(album_id: int, src_path: Path, original_name: str) -> Path:
    """Save a file to the album directory, ensuring a unique filename.

    Args:
        album_id (int): The album identifier.
        src_path (Path): Path to the source file.
        original_name (str): The desired filename in the album.

    Returns:
        Path: The final destination path of the saved file.
    """
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
    """Save an uploaded file-like object to the album directory.

    Args:
        album_id (int): The album identifier.
        file_obj (file-like object): The file-like object containing binary data.
        original_name (str): The desired filename in the album.

    Returns:
        Path: The final destination path of the saved file.
    """
    dst_folder = album_dir(album_id)
    dst_path = dst_folder / original_name

    # Ensure unique filename
    i = 1
    while dst_path.exists():
        stem = dst_path.stem
        suffix = dst_path.suffix
        dst_path = dst_folder / f"{stem} ({i}){suffix}"
        i += 1

    with open(dst_path, "wb") as file:
        shutil.copyfileobj(file_obj, file)

    return dst_path


def iter_files(paths: Iterable[Path]) -> Generator[Path, None, None]:
    """Yield file paths from a list of paths, skipping directories.

    Args:
        paths (Iterable[Path]): An iterable of paths to check.

    Yields:
        Path: File paths that are valid files (not directories).
    """
    for path in paths:
        if path.is_file():
            yield path
