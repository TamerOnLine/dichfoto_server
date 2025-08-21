# scripts/test_gdrive.py
from __future__ import annotations
import io
from app.config import settings
from app.services import gdrive

def main():
    svc = gdrive._service()

    root_id = settings.GDRIVE_ROOT_FOLDER_ID
    if not root_id:
        print("[test] ERROR: GDRIVE_ROOT_FOLDER_ID is missing in .env")
        return
    print("[test] root id:", root_id)

    # 1) تأكيد أن الـ ID يشير لمجلد يمكن رؤيته بواسطة الـ Service Account
    meta = svc.files().get(
        fileId=root_id,
        fields="id,name,mimeType,driveId",
        supportsAllDrives=True
    ).execute()
    print("[test] root meta:", meta)
    if meta.get("mimeType") != "application/vnd.google-apps.folder":
        print("[test] ERROR: root id is not a folder")
        return

    # 2) إنشاء مجلد ألبوم تجريبي + _thumbs (إن لم يوجدا)
    album_name = "test_album_000000"
    album_id = gdrive.ensure_subfolder(svc, root_id, album_name)  # يجب أن تستخدم supportsAllDrives داخليًا
    thumbs_id = gdrive.ensure_subfolder(svc, album_id, "_thumbs")
    print("[test] created/located folders:", album_id, thumbs_id)

    # 3) رفع ملف نصي بسيط
    txt_id = gdrive.upload_bytes(
        svc, album_id, "hello.txt", "text/plain", b"hello from dichfoto"
    )
    print("[test] uploaded text id:", txt_id)

    # 4) تنزيله للتأكد (stream)
    data = b""
    for chunk in gdrive.download_to_generator(svc, txt_id):
        data += chunk
        if len(data) > 64:
            break
    print("[test] first bytes:", data[:32])

    print("\n[test] OK — Drive access & upload working.")

if __name__ == "__main__":
    main()
