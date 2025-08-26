# app/services/gdrive.py
from __future__ import annotations

import io
import time
from typing import Any, Dict, Iterator, Optional

from app.config import settings

# ======================================================
# Google Drive client bootstrap (lazy init)
# ======================================================

_SCOPES = ["https://www.googleapis.com/auth/drive"]  # غيّرها إلى readonly لو تحتاج

# Globals (تُملأ عند أول استخدام)
_creds = None
_service_obj = None
_sess = None


def _init_gdrive() -> None:
    """
    تهيئة عميل Google Drive عند الحاجة فقط.
    ترفع استثناءات واضحة إن كانت الإعدادات غير مكتملة.
    """
    global _creds, _service_obj, _sess
    if _service_obj is not None:
        return

    if not settings.USE_GDRIVE:
        raise RuntimeError("Google Drive is disabled (USE_GDRIVE=False)")

    if not settings.GOOGLE_APPLICATION_CREDENTIALS:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS is not set")

    # استيراد المكتبات هنا (lazy) حتى لا ينهار الاستيراد عند تعطيل Drive
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    from googleapiclient.discovery import build

    _creds = service_account.Credentials.from_service_account_file(
        str(settings.GOOGLE_APPLICATION_CREDENTIALS),
        scopes=_SCOPES,
    )
    _service_obj = build("drive", "v3", credentials=_creds, cache_discovery=False)
    _sess = AuthorizedSession(_creds)


def _service():
    """احصل على كائن الخدمة بعد التأكد من تهيئته."""
    _init_gdrive()
    return _service_obj


# ======================================================
# Utilities
# ======================================================

def ensure_subfolder(service, parent_id: str, name: str) -> str:
    """
    يتأكد من وجود مجلد فرعي داخل parent، ويُنشئه إن لم يوجد.
    """
    if service is None:
        service = _service()

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
    رفع ملف إلى Google Drive من بايتات.
    """
    if service is None:
        service = _service()

    # استيراد هنا حتى نتجنب الاستيراد عند تعطيل Drive
    from googleapiclient.http import MediaIoBaseUpload

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


def get_meta(file_id: str) -> Dict[str, Any]:
    """
    جلب ميتاداتا باستخدام الخدمة العالمية.
    """
    service = _service()
    return service.files().get(
        fileId=file_id,
        fields="id,name,mimeType,size,md5Checksum,modifiedTime",
        supportsAllDrives=True,
    ).execute()


def get_metadata(service, file_id: str, fields: str = "id,name,mimeType,size") -> Dict[str, Any]:
    """
    جلب ميتاداتا باستخدام خدمة معيّنة.
    """
    if service is None:
        service = _service()
    return service.files().get(
        fileId=file_id,
        fields=fields,
        supportsAllDrives=True,
    ).execute()


# ======================================================
# Download / Streaming (MediaIoBaseDownload)
# ======================================================

def download_to_generator(file_id: str, chunk_size: int = 1 * 1024 * 1024) -> Iterator[bytes]:
    """
    تنزيل ملف على دفعات باستخدام MediaIoBaseDownload.
    """
    service = _service()
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)

    from googleapiclient.http import MediaIoBaseDownload

    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request, chunksize=chunk_size)

    done = False
    backoff = 1.0
    while not done:
        try:
            _, done = downloader.next_chunk(num_retries=3)
            if buffer.tell():
                buffer.seek(0)
                yield buffer.read()
                buffer.seek(0)
                buffer.truncate(0)
            backoff = 1.0
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2, 10.0)


def download_to_generator_with_service(
    service, file_id: str, chunk_size: int = 1_048_576
) -> Iterator[bytes]:
    """
    تنزيل ملف باستخدام خدمة صريحة (بدل الخدمة العالمية).
    """
    if service is None:
        service = _service()
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)

    from googleapiclient.http import MediaIoBaseDownload

    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request, chunksize=chunk_size)
    done = False
    backoff = 1.0

    while not done:
        try:
            _, done = downloader.next_chunk(num_retries=3)
            if buffer.tell():
                buffer.seek(0)
                yield buffer.read()
                buffer.seek(0)
                buffer.truncate(0)
            backoff = 1.0
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2, 10.0)


def stream_file(file_id: str, chunk_size: int = 1_048_576) -> Iterator[bytes]:
    """واجهة باسم أبسط."""
    yield from download_to_generator(file_id, chunk_size=chunk_size)


# ======================================================
# Direct HTTP streaming via AuthorizedSession (Range requests)
# ======================================================

def stream_via_requests(file_id: str, chunk_size: int = 256 * 1024) -> Iterator[bytes]:
    """
    بث مباشر باستخدام AuthorizedSession وRange.
    """
    _init_gdrive()
    # استيراد هنا لتكوين AuthorizedSession وقت الحاجة
    from google.auth.transport.requests import AuthorizedSession as _AuthorizedSession  # noqa: F401

    # نستخدم _sess الذي تم إنشاؤه في _init_gdrive
    global _sess
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
    params = {"alt": "media", "supportsAllDrives": "true"}

    start = 0
    backoff = 1.0
    while True:
        headers = {"Range": f"bytes={start}-{start + chunk_size - 1}"}
        r = _sess.get(url, params=params, headers=headers, timeout=30)

        if r.status_code in (200, 206):
            data = r.content
            if not data:
                break
            yield data
            start += len(data)
            backoff = 1.0
            if r.status_code == 200:
                break
        elif r.status_code in (429, 500, 502, 503, 504):
            time.sleep(backoff)
            backoff = min(backoff * 2, 10.0)
            continue
        else:
            break


# ======================================================
# Permissions
# ======================================================

def make_public(file_id: str) -> None:
    """
    جعل الملف متاحًا لأي شخص معه الرابط.
    """
    service = _service()
    try:
        service.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"},
            supportsAllDrives=True,
        ).execute()
    except Exception:
        # يمكن إضافة logging هنا إذا رغبت
        pass
