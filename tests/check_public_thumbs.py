#!/usr/bin/env python3
"""
تشخيص معرض الروابط العامة:
- يجلب آخر slug (أو slug تحدده أنت) ويستخرج album_id.
- يسحب قائمة الأصول (assets) المرتبة.
- لكل أصل:
  - يحسب اسم الثمبنيل المتوقع حسب منطق public.py:
    STORAGE_DIR/albums/<album_id>/thumb/400/<stem>.jpg|.webp
    حيث stem = Path(filename).stem
  - إن لم يجده، يجرّب fallback بلا اللاحقة -<digits> (مثال: DSC01084-17560.. → DSC01084)
  - مع --fix-copy: ينسخ الملف الموجود بالاسم القديم إلى الاسم المطلوب.
  - (اختياري) مع --http-test: يطلب GET من /s/<slug>/thumb/<asset_id> ويطبع الحالة.

تشغيل أمثلة:
    python tests/check_public_thumbs.py                  # يستخدم آخر slug تلقائيًا
    python tests/check_public_thumbs.py --slug abc123
    python tests/check_public_thumbs.py --fix-copy
    python tests/check_public_thumbs.py --http-test
"""

from __future__ import annotations
import argparse
import re
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

# حاول قراءة STORAGE_DIR من app.config.settings
STORAGE_DIR: Optional[Path] = None
try:
    import sys
    sys.path.append(str(Path(__file__).resolve().parents[1]))  # أضف جذر المشروع إلى path
    from app.config import settings  # type: ignore
    STORAGE_DIR = Path(settings.STORAGE_DIR)
except Exception:
    pass

DEFAULT_DB = Path("/home/dichfoto/app.db")
DEFAULT_STORAGE = STORAGE_DIR or Path("/home/dichfoto/storage")


def query_one(db: sqlite3.Connection, sql: str, params: Tuple = ()) -> Optional[Tuple]:
    cur = db.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    return row


def main():
    ap = argparse.ArgumentParser(description="تشخيص ثَمبنيلات المعرض العام /s/<slug>")
    ap.add_argument("--db", default=str(DEFAULT_DB), help="مسار قاعدة البيانات SQLite (افتراضي: /home/dichfoto/app.db)")
    ap.add_argument("--storage", default=str(DEFAULT_STORAGE), help="STORAGE_DIR (افتراضي: من settings أو /home/dichfoto/storage)")
    ap.add_argument("--slug", default=None, help="slug محدد للرابط العام؛ إن لم يُحدَّد يؤخذ آخر واحد")
    ap.add_argument("--limit", type=int, default=20, help="كم أصل نفحص (افتراضي 20؛ استخدم قيمة كبيرة لفحص الكل)")
    ap.add_argument("--fix-copy", action="store_true", help="إنشاء نسخة باسم الstem الكامل إذا وُجد ملف باسم fallback (بدون اللاحقة)")
    ap.add_argument("--http-test", action="store_true", help="اختبار GET فعلي نحو /s/<slug>/thumb/<asset_id>")
    args = ap.parse_args()

    db_path = Path(args.db)
    storage = Path(args.storage)

    if not db_path.exists():
        print(f"[!] قاعدة البيانات غير موجودة: {db_path}")
        return
    if not storage.exists():
        print(f"[!] STORAGE_DIR غير موجود: {storage}")
        return

    con = sqlite3.connect(str(db_path))

    # 1) slug + album_id
    if args.slug:
        slug = args.slug
        row = query_one(con, "SELECT album_id FROM share_links WHERE slug=? ORDER BY id DESC LIMIT 1;", (slug,))
        if not row:
            print(f"[!] لم أجد slug='{slug}' في share_links")
            return
        album_id = row[0]
    else:
        row = query_one(con, "SELECT slug, album_id FROM share_links ORDER BY id DESC LIMIT 1;")
        if not row:
            print("[!] لا توجد روابط مشاركة في share_links")
            return
        slug, album_id = row

    print(f"[i] SLUG={slug}  ALBUM_ID={album_id}")
    print(f"[i] STORAGE_DIR={storage}")

    # 2) اجلب الأصول المرئية مرتبة
    cur = con.execute(
        """
        SELECT id, filename, original_name
        FROM assets
        WHERE album_id = ? AND (is_hidden IS NULL OR is_hidden=0)
        ORDER BY COALESCE(sort_order,0), id
        """,
        (album_id,),
    )
    rows = cur.fetchall()
    cur.close()

    if not rows:
        print("[!] لا توجد أصول (assets) مرئية لهذا الألبوم.")
        return

    # counters
    ok_cnt = 0
    fallback_ok = 0
    missing_cnt = 0
    fixed_cnt = 0

    base = storage / "albums" / str(album_id) / "thumb" / "400"
    print(f"[i] سيتم البحث عن الملفات داخل: {base}")
    base.mkdir(parents=True, exist_ok=True)

    # 3) افحص حتى limit
    for idx, (asset_id, filename, original_name) in enumerate(rows, start=1):
        if idx > args.limit:
            break

        # الاسم الكامل المتوقع (مقتبس من منطق public.py)
        stem = Path(str(filename).replace("\\", "/")).stem
        bname = Path(filename).name
        expect_jpg = base / f"{stem}.jpg"
        expect_webp = base / f"{stem}.webp"

        # موجود بالاسم المتوقع؟
        exists = expect_jpg.exists() or expect_webp.exists()
        if exists:
            print(f"[OK] {asset_id:>5}  {bname}  -> موجود ({expect_jpg.name if expect_jpg.exists() else expect_webp.name})")
            ok_cnt += 1
            continue  # مهم جدًا حتى لا يمر إلى فحص fallback/MISS

        # جرّب fallback: إزالة لاحقة -digits الطويلة (عدّل طول الأرقام عند الحاجة)
        stem2 = re.sub(r"-\d{6,}$", "", stem)
        fb_jpg = base / f"{stem2}.jpg"
        fb_webp = base / f"{stem2}.webp"
        fb_exists = fb_jpg.exists() or fb_webp.exists()

        if fb_exists:
            print(f"[FALLBACK] {asset_id:>5}  {bname}  -> لا يوجد {stem}.jpg|webp لكن وُجد {stem2}.*")
            fallback_ok += 1

            if args.fix_copy:
                # انسخ نسخة باسم stem الكامل (لا نعيد التوليد)
                src = fb_jpg if fb_jpg.exists() else fb_webp
                dst = expect_jpg if fb_jpg.exists() else expect_webp
                if src.exists():
                    if not dst.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_bytes(src.read_bytes())
                        print(f"  [+] COPY {src.name} -> {dst.name}")
                        fixed_cnt += 1
                else:
                    print("  [!] fallback file اختفى أثناء المعالجة!")

            continue  # بعد التعامل مع fallback لا نطبع MISS

        # إذا وصلنا هنا: لا موجود ولا fallback
        print(f"[MISS] {asset_id:>5}  {bname}  -> لا يوجد: {expect_jpg.name} ولا {expect_webp.name}")
        missing_cnt += 1

    # 4) تلخيص
    total = min(args.limit, len(rows))
    print("\n=== Summary ===")
    print(f"Checked: {total}  OK: {ok_cnt}  FallbackFound: {fallback_ok}  Missing: {missing_cnt}  FixedByCopy: {fixed_cnt}")

    # 5) اختبار HTTP للثَمنبيل عبر الراوتر (إن طُلب)
    if args.http_test:
        try:
            import urllib.request
            print("\n=== HTTP test (/s/<slug>/thumb/<asset_id>) for first few assets ===")
            test_n = min(10, total)
            for (asset_id, filename, _) in rows[:test_n]:
                url = f"https://upload.dichfoto.com/s/{slug}/thumb/{asset_id}"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    ctype = resp.getheader("Content-Type", "")
                    status = resp.status
                print(f"[HTTP] {asset_id:>5}  {Path(filename).name}  -> {status} {ctype}")
        except Exception as e:
            print(f"[!] HTTP test failed: {e}")


if __name__ == "__main__":
    main()
