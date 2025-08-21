# app/services/gdrive.py
from __future__ import annotations
import os, io
from typing import Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive"]

def _service():
    creds = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"], scopes=SCOPES
    )
    # cache_discovery=False لمنع تحذيرات Local
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def get_metadata(service, file_id: str, fields: str = "id,name,mimeType,size,parents,driveId"):
    return service.files().get(
        fileId=file_id, fields=fields, supportsAllDrives=True
    ).execute()

def ensure_subfolder(service, parent_id: str, name: str) -> str:
    """أعد id لمجلد باسم name تحت parent_id. أنشئه إذا لم يوجد."""
    # ابحث عن مجلد بنفس الاسم تحت الأب
    safe_name = name.replace("'", "\\'")
    q = (
        "mimeType = 'application/vnd.google-apps.folder' "
        f"and name = '{safe_name}' "
        f"and '{parent_id}' in parents and trashed = false"
    )

    res = service.files().list(
        q=q,
        fields="files(id,name)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        pageSize=10,
    ).execute()
    found = res.get("files", [])
    if found:
        return found[0]["id"]

    # أنشئ مجلد جديد تحت Shared/My Drive parent
    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    created = service.files().create(
        body=meta, fields="id", supportsAllDrives=True
    ).execute()
    return created["id"]

def upload_bytes(service, parent_id: str, filename: str, mime: Optional[str], data: bytes) -> str:
    media = MediaInMemoryUpload(data, mimetype=mime or "application/octet-stream", resumable=False)
    meta = {"name": filename, "parents": [parent_id]}
    file = service.files().create(
        body=meta, media_body=media, fields="id", supportsAllDrives=True
    ).execute()
    return file["id"]

def download_to_generator(service, file_id: str):
    """يولّد بايتات محتوى الملف (stream)."""
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
        if buf.tell():
            buf.seek(0)
            chunk = buf.read()
            buf.seek(0); buf.truncate(0)
            if chunk:
                yield chunk
