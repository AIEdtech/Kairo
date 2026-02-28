"""Auth routes — register, login, profile, password reset"""

import random
import time
from fastapi import APIRouter, Depends, HTTPException, status
from services.auth import (
    RegisterRequest, LoginRequest, TokenResponse, UserResponse,
    ForgotPasswordRequest, ResetPasswordRequest,
    hash_password, verify_password, create_access_token, get_current_user_id,
)
from models.database import User, get_engine, create_session_factory
from config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()
engine = get_engine(settings.database_url)
SessionLocal = create_session_factory(engine)

# In-memory reset codes: {email: {"code": str, "expires": float}}
_reset_codes: dict[str, dict] = {}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db=Depends(get_db)):
    # Check existing
    existing = db.query(User).filter(
        (User.email == req.email) | (User.username == req.username)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email or username already registered")

    user = User(
        email=req.email,
        username=req.username,
        hashed_password=hash_password(req.password),
        full_name=req.full_name,
        preferred_language=req.preferred_language,
        timezone=req.timezone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user=_user_to_dict(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db=Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user=_user_to_dict(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(user_id: str = Depends(get_current_user_id), db=Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_dict(user)


@router.put("/me")
def update_me(
    updates: dict,
    user_id: str = Depends(get_current_user_id),
    db=Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    allowed_fields = ["full_name", "preferred_language", "timezone", "avatar_url"]
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return _user_to_dict(user)


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db=Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found with that email")
    code = f"{random.randint(100000, 999999)}"
    _reset_codes[req.email] = {"code": code, "expires": time.time() + 900}  # 15 min
    return {"message": "Reset code generated", "code": code}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db=Depends(get_db)):
    entry = _reset_codes.get(req.email)
    if not entry:
        raise HTTPException(status_code=400, detail="No reset code found. Request a new one.")
    if time.time() > entry["expires"]:
        del _reset_codes[req.email]
        raise HTTPException(status_code=400, detail="Reset code expired. Request a new one.")
    if entry["code"] != req.code:
        raise HTTPException(status_code=400, detail="Invalid reset code")
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = hash_password(req.new_password)
    db.commit()
    del _reset_codes[req.email]
    return {"message": "Password reset successfully"}


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name or "",
        "avatar_url": user.avatar_url or "",
        "preferred_language": user.preferred_language or "en",
        "timezone": user.timezone or "Asia/Kolkata",
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else "",
    }
