from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import FileResponse
import os

from .config import settings
from .database import engine, Base
from .routers import admin, public


# ✅ كلاس جديد لعمل Cache-Control للصور
class StaticFilesCached(StaticFiles):
    def file_response(self, *args, **kwargs):
        resp: FileResponse = super().file_response(*args, **kwargs)
        content_type = resp.headers.get("content-type", "")
        if content_type.startswith("image/"):
            # Cache سنة كاملة + immutable
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif content_type in ("text/css", "application/javascript"):
            # كاش قصير للـ CSS/JS (مثلاً يوم واحد)
            resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp


# ===== FastAPI setup =====
app = FastAPI(title=settings.SITE_TITLE)

# Create the database tables if they do not exist
Base.metadata.create_all(bind=engine)

# Add session middleware, required for admin login and share unlock
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# Mount local thumbs directory if USE_GDRIVE is False
thumbs_mount = os.path.join(settings.THUMBS_DIR)
app.mount("/static/thumbs", StaticFiles(directory=thumbs_mount), name="thumbs")  # type: ignore

# ✅ Mount static with improved caching
app.mount("/static", StaticFilesCached(directory="static"), name="static")

# Include routers
app.include_router(admin.router)
app.include_router(public.router)


@app.get("/")
def root():
    """Root endpoint to confirm service is running."""
    return {"ok": True, "message": "Client Gallery running", "admin": "/admin"}
