import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import bcrypt
import jwt
from fastapi import HTTPException
from sqlmodel import Session, select

from infrastructure.models import User, UserRole

logger = logging.getLogger(__name__)

JWT_ALG = "HS256"
JWT_EXPIRE_HOURS_DEFAULT = 72


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if not secret:
        logger.warning(
            "JWT_SECRET is not set; using insecure development default — set JWT_SECRET in production"
        )
        return "dev-insecure-jwt-secret-change-me"
    return secret


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except ValueError:
        return False


def _role_value(role: UserRole | str) -> str:
    return role.value if isinstance(role, UserRole) else str(role)


def create_access_token(*, user_id: UUID, email: str, role: UserRole | str) -> str:
    now = datetime.now(timezone.utc)
    exp_hours = int(os.getenv("JWT_EXPIRE_HOURS", str(JWT_EXPIRE_HOURS_DEFAULT)))
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": _role_value(role),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=exp_hours)).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALG)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALG])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_user_by_email(session: Session, email: str) -> Optional[User]:
    normalized = email.strip().lower()
    return session.exec(select(User).where(User.email == normalized)).first()


def get_user_by_id(session: Session, user_id: UUID) -> Optional[User]:
    return session.get(User, user_id)


def authenticate(session: Session, email: str, password: str) -> User:
    user = get_user_by_email(session, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return user


def user_from_token_payload(session: Session, payload: dict[str, Any]) -> User:
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        uid = UUID(sub)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = get_user_by_id(session, uid)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def seed_bootstrap_users(session: Session) -> None:
    """Create dev users from env if they do not exist yet."""
    pairs = [
        (
            os.getenv("BOOTSTRAP_EMPLOYEE_EMAIL", "").strip(),
            os.getenv("BOOTSTRAP_EMPLOYEE_PASSWORD", "").strip(),
            UserRole.EMPLOYEE,
        ),
        (
            os.getenv("BOOTSTRAP_RECEPTION_EMAIL", "").strip(),
            os.getenv("BOOTSTRAP_RECEPTION_PASSWORD", "").strip(),
            UserRole.RECEPTION,
        ),
    ]
    for email, password, role in pairs:
        if not email or not password:
            continue
        normalized = email.lower()
        if get_user_by_email(session, normalized):
            continue
        u = User(
            email=normalized,
            password_hash=hash_password(password),
            role=role,
        )
        session.add(u)
        session.commit()
        logger.info("Bootstrap user created email=%s role=%s", normalized, role.value)
