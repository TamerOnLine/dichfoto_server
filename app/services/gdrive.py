# app/services/gdrive.py
from __future__ import annotations

import io
import time
from typing import Any, Dict, Iterator, Optional

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from app.config import settings

# ======================================================
# Google Drive client bootstrap
# ======================================================

_SCOPES = ["https://www.googleapis.com/auth/drive"]  # قراءة/كتابة. بدّل إلى readonly إن لزم.

# Credentials & global service/session (يتم إنشاؤها مرة واحدة)
_creds = service_account.Credentials.from_service_account_file(
    settings.GOOGLE_APPLICATION_CREDENTIALS,
    scopes=_SCOPES,
)
_service_obj = build("drive", "v3", credentials=_creds, cache_discovery=False)
_sess = AuthorizedSession(_creds)  # لطلبات HTTP المباشرة (stream_via_requests)


def _service():
    """ارجع كائن خدمة Google Drive العالمي."""
    return _service_obj


# ======================================================
# Utilities
# ======================================================

def ensure_subfolder(service, parent_id: str, name: str) -> str:
    """
    يتأكد من وجود مجلد فرعي داخل parent، ويُنشئه إن لم يوجد.

    Args:
        service: Google Drive API service object.
        parent_id: ID للمجلد الأب.
        name: اسم المجلد المراد ضمانه.

    Returns:
        str: معرّف المجلد.
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
    رفع ملف إلى Google Drive من بايتات.

    Args:
        service: Google Drive API service object.
        folder_id: وجهة الرفع (ID للمجلد).
        filename: اسم الملف على Drive.
        mime: نوع المحتوى (اختياري).
        data: البايتات.

    Returns:
        str: ID للملف المرفوع.
    """
    meta = {"name": filename, "parents": [folder_id]}
    media = MediaIoBaseUpload(
        io.BytesIO(data),
        mimetype=mime or "application/octet-stream",
        resumable=False,  # اضبط True لو ملفات كبيرة أو اتصال غير مستقر
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
    return _service_obj.files().get(
        fileId=file_id,
        fields="id,name,mimeType,size,md5Checksum,modifiedTime",
        supportsAllDrives=True,
    ).execute()


def get_metadata(service, file_id: str, fields: str = "id,name,mimeType,size") -> Dict[str, Any]:
    """
    جلب ميتاداتا باستخدام خدمة معيّنة.
    """
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
    تنزيل ملف من Google Drive على دفعات باستخدام MediaIoBaseDownload (خدمة عالمية).

    ملاحظة: بدون استخدام خصائص داخلية (لا نعتمد على downloader._fd).
    """
    service = _service()
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
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
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
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
    """
    مثل download_to_generator لكن موجودة كواجهة اسمها "stream_file".
    """
    yield from download_to_generator(file_id, chunk_size=chunk_size)


# ======================================================
# Direct HTTP streaming via AuthorizedSession (Range requests)
# ======================================================

def stream_via_requests(file_id: str, chunk_size: int = 256 * 1024) -> Iterator[bytes]:
    """
    بث الملف مباشرة عبر HTTP باستخدام AuthorizedSession ورؤوس Range.
    مفيد للـ Streaming في FastAPI (StreamingResponse).
    """
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
                # السيرفر أعاد الملف كامل (بدون 206 partial)
                break
        elif r.status_code in (429, 500, 502, 503, 504):
            time.sleep(backoff)
            backoff = min(backoff * 2, 10.0)
            continue
        else:
            # بإمكانك هنا raise أو log
            break


# ======================================================
# Permissions
# ======================================================

def make_public(file_id: str) -> None:
    """
    جعل الملف متاحًا لأي شخص يحمل الرابط (reader/anyone).
    """
    try:
        _service_obj.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"},
            supportsAllDrives=True,
        ).execute()
    except Exception:
        # تجاهُل الخطأ بهدوء؛ ضع logging إن رغبت
        pass
