"""Mật khẩu, JWT, refresh token và dependency phân quyền (docs mục 4.6).

- Mật khẩu: Argon2id (TD-08).
- Access token: JWT HS256, header có `kid` để xoay khóa; hạn so với `Clock` của ứng dụng.
- Refresh token: chuỗi ngẫu nhiên 256 bit, database chỉ lưu SHA-256 (bảng refresh_tokens).
- Phân quyền lớp 1 ở router: `require_roles(...)`; lớp 2 nằm ở service của từng module.
"""

import asyncio
import hashlib
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Annotated

import jwt
import structlog
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.actor import Actor
from app.core.clock import Clock, get_clock
from app.core.config import Settings, get_settings
from app.core.db import get_sessionmaker
from app.core.errors import AppError, forbidden
from app.db.enums import Channel, UserRole
from app.db.models.users import User

_hasher = PasswordHasher()  # Argon2id với tham số mặc định của argon2-cffi (TD-08)
JWT_ALGORITHM = "HS256"
REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"  # cookie chỉ đi tới endpoint /auth/* (docs mục 4.6)


# ---------------------------------------------------------------------------- mật khẩu
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False


@lru_cache
def _dummy_hash() -> str:
    return _hasher.hash("mat-khau-gia-de-can-bang-thoi-gian")


async def hash_password_async(password: str) -> str:
    """Băm trong thread riêng: Argon2 tốn CPU, không được chặn event loop."""
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password_hash: str | None, password: str) -> bool:
    """Email không tồn tại vẫn băm thử một lần, để thời gian phản hồi không lộ email nào có thật."""
    target = password_hash or _dummy_hash()
    ok = await asyncio.to_thread(verify_password, target, password)
    return ok and password_hash is not None


# ---------------------------------------------------------------------------- access token
@dataclass(frozen=True, slots=True)
class AccessClaims:
    user_id: int
    role: UserRole
    expires_at: datetime


def _signing_keys(settings: Settings) -> list[tuple[str, str]]:
    """`kid:secret[,kid_cũ:secret_cũ]` → [(kid, secret)]; khóa đầu tiên dùng để ký."""
    keys: list[tuple[str, str]] = []
    for item in settings.jwt_keys.get_secret_value().split(","):
        kid, sep, secret = item.strip().partition(":")
        if not sep or not kid or not secret:
            raise RuntimeError("jwt_keys phải có dạng kid:secret[,kid:secret]")
        keys.append((kid, secret))
    return keys


def create_access_token(user: User, now: datetime, settings: Settings) -> tuple[str, datetime]:
    kid, secret = _signing_keys(settings)[0]
    expires_at = now + timedelta(minutes=settings.access_token_ttl_min)
    claims = {
        "sub": str(user.id),
        "role": user.role.value,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(claims, secret, algorithm=JWT_ALGORITHM, headers={"kid": kid})
    return token, expires_at


def decode_access_token(token: str, now: datetime, settings: Settings) -> AccessClaims:
    """Kiểm tra chữ ký theo `kid` (chấp nhận cả khóa cũ khi đang xoay khóa) và hạn theo `now`."""
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        secret = dict(_signing_keys(settings)).get(str(kid))
        if secret is None:
            raise _unauthenticated()
        claims = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            options={"verify_exp": False, "require": ["sub", "exp", "iat", "type"]},
        )
        expires_at = datetime.fromtimestamp(int(claims["exp"]), tz=now.tzinfo)
        if claims["type"] != "access" or expires_at <= now:
            raise _unauthenticated()
        return AccessClaims(int(claims["sub"]), UserRole(claims["role"]), expires_at)
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise _unauthenticated() from exc


def _unauthenticated() -> AppError:
    return AppError(
        "UNAUTHENTICATED", "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.", status=401
    )


# ---------------------------------------------------------------------------- refresh token
def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bit ngẫu nhiên


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------------------- dependency
def get_app_settings(request: Request) -> Settings:
    """Settings của app đang chạy (create_app lưu vào app.state), để test truyền Settings riêng."""
    settings: Settings | None = getattr(request.app.state, "settings", None)
    return settings or get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
ClockDep = Annotated[Clock, Depends(get_clock)]
_bearer = HTTPBearer(auto_error=False, description="Access token lấy từ /auth/login")


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: int
    role: UserRole
    full_name: str


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    clock: ClockDep,
    settings: SettingsDep,
) -> CurrentUser:
    """Giải mã access token rồi đọc lại dòng users để tài khoản bị khóa mất quyền ngay (docs 4.6).

    Dùng session riêng, ngắn, để không mở sẵn transaction trên session của request
    (service tự `begin()` transaction của mình).
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthenticated()
    claims = decode_access_token(credentials.credentials, clock.now(), settings)
    async with get_sessionmaker()() as session:
        user = await session.get(User, claims.user_id)
    if user is None or not user.is_active or user.anonymized_at is not None:
        raise _unauthenticated()
    structlog.contextvars.bind_contextvars(user_id=user.id)
    return CurrentUser(id=user.id, role=user.role, full_name=user.full_name)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[CurrentUser], Awaitable[CurrentUser]]:
    """Phân quyền lớp 1: chặn sai vai trò ở router, trả 403 FORBIDDEN."""

    async def checker(user: CurrentUserDep) -> CurrentUser:
        if user.role not in roles:
            raise forbidden()
        return user

    return checker


def actor_of(user: CurrentUser) -> Actor:
    """Quản trị thao tác với kênh ADMIN, người dùng khác với kênh WEB (ERD mục 4)."""
    channel = Channel.ADMIN if user.role is UserRole.ADMIN else Channel.WEB
    return Actor(user_id=user.id, role=user.role, channel=channel)


async def get_actor(user: CurrentUserDep) -> Actor:
    return actor_of(user)


def actor_with_roles(*roles: UserRole) -> Callable[[CurrentUser], Awaitable[Actor]]:
    """Như `require_roles` nhưng trả luôn `Actor` để router truyền vào service."""
    checker = require_roles(*roles)

    async def dependency(user: Annotated[CurrentUser, Depends(checker)]) -> Actor:
        return actor_of(user)

    return dependency


ActorDep = Annotated[Actor, Depends(get_actor)]
AdminActorDep = Annotated[Actor, Depends(actor_with_roles(UserRole.ADMIN))]
PatientActorDep = Annotated[Actor, Depends(actor_with_roles(UserRole.PATIENT))]
