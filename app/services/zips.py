from pathlib import Path
from typing import Iterable
import zipfile
import io


from zipstream import ZipStream
from typing import Iterable

def make_zip_in_memory(files: Iterable[Path], base_prefix: str = "") -> bytes:
    # For moderate album sizes. For massive collections, switch to streaming ZIP.
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fpath in files:
            arcname = f"{base_prefix}/{fpath.name}" if base_prefix else fpath.name
            zf.write(fpath, arcname=arcname)
    mem.seek(0)
    return mem.read()



def stream_zip(pairs: Iterable[tuple[str, bytes]]):
    # pairs: (arcname, bytes_chunk_generator)
    z = ZipStream(mode='w', compression='deflated')
    for arcname, gen in pairs:
        z.add(arcname, gen)
    return z
