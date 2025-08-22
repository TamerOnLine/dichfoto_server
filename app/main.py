from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import FileResponse

from .config import settings
from .database import engine, Base
from .routers import admin, public

# سجل أنواع الـ MIME التي قد لا تكون مضافة افتراضيًا
import mimetypes
mimetypes.add_type("image/avif", ".avif")
mimetypes.add_type("image/webp", ".webp")


# ✅ كلاس يضيف Cache-Control مناسب للصور وملفات CSS/JS
class StaticFilesCached(StaticFiles):
    def file_response(self, *args, **kwargs):
        resp: FileResponse = super().file_response(*args, **kwargs)
        content_type = resp.headers.get("content-type", "")
        if content_type.startswith("image/"):
            # كاش سنة كاملة + immutable للصور
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif content_type in ("text/css", "application/javascript"):
            # كاش يوم واحد لـ CSS/JS
            resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp


# ===== FastAPI setup =====
app = FastAPI(title=settings.SITE_TITLE)

# إنشاء الجداول (إن لم تكن موجودة)
Base.metadata.create_all(bind=engine)

# الجلسات (مطلوبة للدخول/القفل)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# ✅ ركّب مجلد الثمبنيلز مع نفس كلاس الكاش
thumbs_dir = str(settings.THUMBS_DIR)  # تأكد أنها string
app.mount("/static/thumbs", StaticFilesCached(directory=thumbs_dir), name="thumbs")

# ✅ ركّب مجلد الأصول العامة مع كاش محسّن
app.mount("/static", StaticFilesCached(directory="static"), name="static")

# الروترات
app.include_router(admin.router)
app.include_router(public.router)


@app.get("/")
def root():
    """Root endpoint to confirm service is running."""
    return {"ok": True, "message": "Client Gallery running", "admin": "/admin"}
