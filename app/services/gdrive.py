# app/services/gdrive.py
from __future__ import annotations

import io, time
from typing import Dict, Iterator, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from app.config import settings

_SCOPES = ["https://www.googleapis.com/auth/drive"]

# نعتمد أن settings.GOOGLE_APPLICATION_CREDENTIALS أصبح مسارًا مطلقًا في config.py
_creds = service_account.Credentials.from_service_account_file(
    settings.GOOGLE_APPLICATION_CREDENTIALS,
    scopes=_SCOPES,
)
_service_obj = build("drive", "v3", credentials=_creds, cache_discovery=False)


def _service():
    """Google Drive service object (لمناداة الدوال القديمة)."""
    return _service_obj

def download_to_generator(file_id: str, chunk_size: int = 1 * 1024 * 1024) -> Iterator[bytes]:
    """
    يولّد بايتات الملف من Google Drive على شكل chunks مع إعادة محاولات.
    """
    service = _service()
    request = service.files().get_media(fileId=file_id)

    # قلّل الـ chunk لو الشبكة بطيئة
    downloader = MediaIoBaseDownload(io.BytesIO(), request, chunksize=chunk_size)

    done = False
    backoff = 1.0
    buf = downloader._fd  # io.BytesIO الداخلي

    while not done:
        try:
            # num_retries يفعّل retry داخل googleapiclient (على أخطاء 5xx/شبكة)
            status, done = downloader.next_chunk(num_retries=3)

            data = buf.getvalue()
            if data:
                yield data
                buf.seek(0); buf.truncate(0)  # نظّف البافر

            # اختياري: لو بدك تُظهر تقدّم
            # if status:
            #     print(f"Downloaded {int(status.progress() * 100)}%")

            # نجحنا.. صفّر backoff
            backoff = 1.0

        except TimeoutError:
            # أعد المحاولة بانتظار تزايدي
            time.sleep(backoff)
            backoff = min(backoff * 2, 10.0)
            continue

def ensure_subfolder(service, parent_id: str, name: str) -> str:
    """
    تأكد من وجود مجلد فرعي داخل parent، وإن لم يوجد يتم إنشاؤه.
    يدعم Shared Drives.
    """
    query = (
        f"'{parent_id}' in parents and name='{name}' and "
        "mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    result = service.files().list(
        q=query,
        fields="files(id,name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="allDrives",
    ).execute()
    if result.get("files"):
        return result["files"][0]["id"]

    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(
        body=meta,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return folder["id"]


def upload_bytes(
    service,
    folder_id: str,
    filename: str,
    mime: Optional[str],
    data: bytes,
) -> str:
    """
    رفع ملف إلى Google Drive من bytes (يدعم Shared Drives).
    """
    meta = {"name": filename, "parents": [folder_id]}
    media = MediaIoBaseUpload(
        io.BytesIO(data),
        mimetype=mime or "application/octet-stream",
        resumable=False,
    )
    file = service.files().create(
        body=meta,
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return file["id"]


def get_meta(file_id: str) -> Dict[str, str]:
    """
    جلب الميتاداتا باستخدام الـ service العالمي (يدعم Shared Drives).
    """
    return _service_obj.files().get(
        fileId=file_id,
        fields="id,name,mimeType,size,md5Checksum,modifiedTime",
        supportsAllDrives=True,
    ).execute()


def get_metadata(service, file_id: str, fields: str = "id,name,mimeType,size") -> Dict[str, str]:
    """
    جلب الميتاداتا باستخدام service صريح (يدعم Shared Drives).
    """
    return service.files().get(
        fileId=file_id,
        fields=fields,
        supportsAllDrives=True,
    ).execute()


def stream_file(file_id: str, chunk_size: int = 1_048_576) -> Iterator[bytes]:
    """
    بثّ ملف من Google Drive على شكل chunks (يدعم Shared Drives).
    """
    request = _service_obj.files().get_media(fileId=file_id, supportsAllDrives=True)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request, chunksize=chunk_size)
    done = False

    while not done:
        _, done = downloader.next_chunk()
        if buffer.tell():
            buffer.seek(0)
            yield buffer.read()
            buffer.seek(0)
            buffer.truncate(0)


def download_to_generator(service, file_id: str, chunk_size: int = 1_048_576) -> Iterator[bytes]:
    """
    بثّ ملف من Google Drive باستخدام service صريح (يدعم Shared Drives).
    """
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request, chunksize=chunk_size)
    done = False

    while not done:
        _, done = downloader.next_chunk()
        if buffer.tell():
            buffer.seek(0)
            yield buffer.read()
            buffer.seek(0)
            buffer.truncate(0)


def make_public(file_id: str) -> None:
    """
    جعل الملف متاحًا لأيّ شخص لديه الرابط (best-effort).
    """
    try:
        _service_obj.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"},
            supportsAllDrives=True,
        ).execute()
    except Exception:
        pass
