from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import os

from .config import settings
from .database import engine, Base
from .routers import admin, public

# أنشئ التطبيق
app = FastAPI(title=settings.SITE_TITLE)

# أنشئ الجداول (لو ما كانت موجودة)
Base.metadata.create_all(bind=engine)

# Middleware للجلسات (ضروري للـ admin login + share unlock)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# Static: thumbs المحلية (في حال USE_GDRIVE = False)
thumbs_mount = os.path.join(settings.THUMBS_DIR)
app.mount("/static/thumbs", StaticFiles(directory=thumbs_mount), name="thumbs")  # type: ignore

# Static: CSS, JS
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(admin.router)
app.include_router(public.router)

@app.get("/")
def root():
    return {"ok": True, "message": "Client Gallery running", "admin": "/admin"}
