from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from .config import settings
from .database import engine, Base
from .routers import admin, public
import os

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.SITE_TITLE)

# Sessions (for admin login + share unlock)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# Static files (CSS + thumbs proxy)
app.mount("/static", StaticFiles(directory="static"), name="static")
# Serve thumbnails under /static/thumbs/... from storage/_thumbs
thumbs_mount = os.path.join(settings.THUMBS_DIR)
app.mount("/static/thumbs", StaticFiles(directory=thumbs_mount), name="thumbs")  # type: ignore

# Routers
app.include_router(admin.router)
app.include_router(public.router)

@app.get("/")
def root():
    return {"ok": True, "message": "Client Gallery running", "admin": "/admin"}
