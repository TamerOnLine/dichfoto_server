# app/routers/likes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import SessionLocal
from .. import models

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/api/like")
def toggle_like(data: dict, db: Session = Depends(get_db)):
    url = data.get("url")
    liked = data.get("liked", True)
    if not url:
        raise HTTPException(status_code=400, detail="url is required")
    like = models.Like(url=url, liked=liked)
    db.add(like)
    db.commit()
    return {"ok": True}
