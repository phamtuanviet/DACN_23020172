"""HTTP của module auth: khai báo endpoint, nhận DTO, tạo Actor, gọi service.

Không chứa nghiệp vụ, không truy vấn database (docs mục 4.2). Refresh token chỉ đi qua cookie
HttpOnly gắn với đường dẫn /api/v1/auth; access token trả trong body (docs mục 4.6).
"""

import ipaddress
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from app.core.config import Settings
from app.core.db import SessionDep
from app.core.ratelimit import LOGIN_LIMIT, limiter
from app.core.security import (
    REFRESH_COOKIE,
    REFRESH_COOKIE_PATH,
    ActorDep,
    ClockDep,
    SettingsDep,
)
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    TokenResponse,
    UpdateMeRequest,
)
from app.modules.auth.service import AuthService, ClientInfo, IssuedSession


def get_auth_service(session: SessionDep, clock: ClockDep, settings: SettingsDep) -> AuthService:
    return AuthService(session, clock, settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
RefreshCookieDep = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]

auth_router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(prefix="/me", tags=["me"])


def _client(request: Request) -> ClientInfo:
    user_agent = request.headers.get("user-agent")
    host = request.client.host if request.client else None
    try:
        ip = str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        ip = None
    return ClientInfo(user_agent=user_agent[:255] if user_agent else None, ip=ip)


def _session_response(
    response: Response, issued: IssuedSession, settings: Settings
) -> TokenResponse:
    response.set_cookie(
        REFRESH_COOKIE,
        issued.refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=not settings.is_development,
        samesite="strict",
    )
    return TokenResponse(
        access_token=issued.access_token, expires_at=issued.access_expires_at, user=issued.me
    )


# ---------------------------------------------------------------------------- /auth
@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
) -> TokenResponse:
    """Đăng ký bệnh nhân (FR-AUTH-01); đăng nhập luôn sau khi tạo."""
    issued = await service.register(body, _client(request))
    return _session_response(response, issued, settings)


@auth_router.post("/login")
@limiter.limit(LOGIN_LIMIT)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    service: AuthServiceDep,
    settings: SettingsDep,
) -> TokenResponse:
    """Đăng nhập (FR-AUTH-02, 03); tối đa 10 lần/phút/IP."""
    issued = await service.login(body.email, body.password, _client(request))
    return _session_response(response, issued, settings)


@auth_router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
    refresh_token: RefreshCookieDep = None,
) -> TokenResponse:
    """Cấp access token mới và xoay vòng refresh token trong cookie."""
    issued = await service.refresh(refresh_token, _client(request))
    return _session_response(response, issued, settings)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
    refresh_token: RefreshCookieDep = None,
) -> None:
    """Thu hồi refresh token hiện tại và xóa cookie; không cần access token còn hạn."""
    await service.logout(refresh_token)
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=not settings.is_development,
        samesite="strict",
    )


# ---------------------------------------------------------------------------- /me
@me_router.get("")
async def get_me(actor: ActorDep, service: AuthServiceDep) -> MeResponse:
    return await service.get_me(actor)


@me_router.patch("")
async def update_me(body: UpdateMeRequest, actor: ActorDep, service: AuthServiceDep) -> MeResponse:
    """Sửa thông tin cá nhân, trừ email (FR-AUTH-06)."""
    return await service.update_me(actor, body)


@me_router.post("/password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    actor: ActorDep,
    service: AuthServiceDep,
    settings: SettingsDep,
) -> TokenResponse:
    """Đổi mật khẩu: thu hồi mọi phiên khác, cấp phiên mới cho thiết bị đang dùng."""
    issued = await service.change_password(actor, body, _client(request))
    return _session_response(response, issued, settings)


router = APIRouter()
router.include_router(auth_router)
router.include_router(me_router)
