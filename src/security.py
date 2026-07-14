import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.db import get_db
from src.models import Admin

ADMIN_COOKIE_NAME = "zito_admin_session"
PASSWORD_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS)
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${encoded}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
        actual = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _b64_json(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64_json(value: str) -> dict:
    padding = "=" * (-len(value) % 4)
    return json.loads(base64.urlsafe_b64decode((value + padding).encode("ascii")).decode("utf-8"))


def _sign(payload: str) -> str:
    settings = get_settings()
    digest = hmac.new(settings.admin_session_secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def create_admin_session(admin: Admin) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.admin_session_days)
    payload = _b64_json({"admin_id": admin.id, "username": admin.username, "exp": int(expires_at.timestamp())})
    return f"{payload}.{_sign(payload)}"


def set_admin_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        ADMIN_COOKIE_NAME,
        token,
        max_age=settings.admin_session_days * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=False,
    )


def clear_admin_cookie(response: Response) -> None:
    response.delete_cookie(ADMIN_COOKIE_NAME)


def get_admin_from_request(request: Request, db: Session) -> Admin | None:
    token = request.cookies.get(ADMIN_COOKIE_NAME)
    if not token or "." not in token:
        return None
    payload, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(payload), signature):
        return None
    try:
        data = _unb64_json(payload)
    except (ValueError, json.JSONDecodeError):
        return None
    if int(data.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
        return None
    admin = db.get(Admin, int(data.get("admin_id", 0)))
    if not admin or not admin.is_active:
        return None
    return admin


def require_admin(request: Request, db: Session = Depends(get_db)) -> Admin:
    admin = get_admin_from_request(request, db)
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin login required.")
    return admin


def authenticate_admin(db: Session, username: str, password: str) -> Admin | None:
    admin = db.scalars(select(Admin).where(Admin.username == username, Admin.is_active.is_(True))).first()
    if not admin or not verify_password(password, admin.password_hash):
        return None
    return admin
