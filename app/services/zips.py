from pathlib import Path
from typing import Iterable
import zipfile
import io
from zipstream import ZipStream


def make_zip_in_memory(files: Iterable[Path], base_prefix: str = "") -> bytes:
    """
    Create a ZIP archive in memory containing the specified files.

    Args:
        files (Iterable[Path]): Collection of file paths to include in the ZIP.
        base_prefix (str, optional): Optional prefix to prepend to file paths inside the archive.
            Defaults to an empty string.

    Returns:
        bytes: The in-memory ZIP file as a byte string.

    Notes:
        This method is suitable for moderate file collections. For very large
        collections, consider using streaming ZIP to avoid memory issues.
    """
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fpath in files:
            arcname = f"{base_prefix}/{fpath.name}" if base_prefix else fpath.name
            zf.write(fpath, arcname=arcname)
    mem.seek(0)
    return mem.read()


def stream_zip(pairs: Iterable[tuple[str, bytes]]):
    """
    Create a streaming ZIP archive from pairs of archive names and content generators.

    Args:
        pairs (Iterable[tuple[str, bytes]]): Iterable of tuples, where each tuple contains:
            - arcname (str): Name of the file inside the ZIP.
            - gen (bytes): Byte content or generator yielding chunks of data for the file.

    Returns:
        ZipStream: A ZipStream object representing the streaming ZIP archive.
    """
    z = ZipStream(mode="w", compression="deflated")
    for arcname, gen in pairs:
        z.add(arcname, gen)
    return z
