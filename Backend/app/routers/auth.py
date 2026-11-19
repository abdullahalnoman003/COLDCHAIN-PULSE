from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import AuditLog, User, utcnow
from ..schemas import LoginIn, TokenOut, UserOut
from ..security import client_ip, create_token, current_user, hash_secret, verify_secret

router = APIRouter(prefix="/auth", tags=["auth"])

# verified against when the email does not exist, so response time doesn't reveal valid emails
_DUMMY_HASH = hash_secret("not-a-real-password")


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    email, ip = data.email.lower(), client_ip(request)
    since = utcnow() - timedelta(minutes=settings.login_lock_minutes)
    fails = db.scalar(select(func.count()).select_from(AuditLog).where(
        AuditLog.event == "login_failed", AuditLog.email == email, AuditLog.created_at >= since))
    if fails >= settings.login_max_failures:
        db.add(AuditLog(event="login_blocked", email=email, ip=ip, detail="too many failed attempts"))
        db.commit()
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts. Try again later.")

    user = db.scalar(select(User).where(User.email == email))
    ok = verify_secret(data.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok or not user.is_active:
        db.add(AuditLog(event="login_failed", email=email, ip=ip, user_id=user.id if user else None,
                        detail="bad credentials" if user else "unknown email"))
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    db.add(AuditLog(event="login_ok", email=email, ip=ip, user_id=user.id))
    db.commit()
    return TokenOut(access_token=create_token(user), role=user.role, name=user.name)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
