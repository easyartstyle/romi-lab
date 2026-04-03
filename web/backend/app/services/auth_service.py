import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User


class AuthError(Exception):
    pass


class UserAlreadyExistsError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


class InvalidTokenError(AuthError):
    pass


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(payload_part: str) -> str:
    signature = hmac.new(settings.secret_key.encode("utf-8"), payload_part.encode("ascii"), hashlib.sha256).digest()
    return _b64url_encode(signature)


def _encode_token(payload: dict) -> str:
    payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    payload_part = _b64url_encode(payload_json)
    signature_part = _sign(payload_part)
    return f"{payload_part}.{signature_part}"


def _decode_token(token: str) -> dict | None:
    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError:
        return None

    expected_signature = _sign(payload_part)
    if not hmac.compare_digest(signature_part, expected_signature):
        return None

    try:
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int):
        return None

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if expires_at < now_ts:
        return None

    return payload


def register_user(
    db: Session,
    email: str,
    password: str,
    full_name: str,
    role: str = "admin",
    is_active: bool = True,
) -> User:
    existing = db.scalar(select(User).where(User.email == email.lower().strip()))
    if existing is not None:
        raise UserAlreadyExistsError("User with this email already exists")

    user = User(
        email=email.lower().strip(),
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not user.is_active:
        raise InvalidCredentialsError("Invalid email or password")
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid email or password")
    return user


def issue_access_token(user: User) -> tuple[str, datetime]:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(days=settings.access_token_expire_days)
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = _encode_token(payload)
    return token, issued_at


def issue_invite_token(user: User) -> str:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(days=settings.invite_token_expire_days)
    payload = {
        "sub": user.id,
        "email": user.email,
        "purpose": "invite",
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return _encode_token(payload)


def get_user_by_invite_token(db: Session, token: str) -> User | None:
    payload = _decode_token(token)
    if payload is None or payload.get("purpose") != "invite":
        return None

    user_id = payload.get("sub")
    if not isinstance(user_id, int):
        return None

    return db.scalar(select(User).where(User.id == user_id))


def accept_invite(db: Session, token: str, password: str) -> User:
    user = get_user_by_invite_token(db, token)
    if user is None:
        raise InvalidTokenError("Invite link is invalid or expired")

    user.password_hash = hash_password(password)
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


def get_user_by_token(db: Session, token: str) -> User | None:
    payload = _decode_token(token)
    if payload is None:
        return None

    user_id = payload.get("sub")
    if not isinstance(user_id, int):
        return None

    return db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))