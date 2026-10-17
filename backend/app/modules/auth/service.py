"""Nghiệp vụ của module auth: quy tắc, phân quyền theo bản ghi, ranh giới transaction.

Không biết về HTTP; nhận `Actor` thay vì request để web và Agent dùng chung.
Lỗi xác thực không bao giờ cho biết sai email hay sai mật khẩu (docs mục 4.6).
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import AppError, field_error, violated_constraint
from app.core.security import (
    create_access_token,
    hash_password_async,
    hash_refresh_token,
    new_refresh_token,
    verify_password_async,
)
from app.core.timeutil import to_local
from app.db.enums import UserRole
from app.db.models.users import PatientProfile, RefreshToken, User
from app.modules.auth import repository as repo
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    MeResponse,
    RegisterRequest,
    UpdateMeRequest,
)

log = structlog.get_logger(__name__)

MAX_FAILED_LOGINS = 5  # FR-AUTH-03
LOCK_DURATION = timedelta(minutes=15)
# Hai tab mở cùng lúc có thể cùng gửi một refresh token: tab đến sau dùng lại token vừa bị xoay
# trong vài giây là chuyện bình thường, chưa phải dấu hiệu bị đánh cắp (docs mục 4.6).
REUSE_GRACE = timedelta(seconds=30)
MIN_BIRTH_DATE = date(1900, 1, 1)
EMAIL_UNIQUE_INDEX = "uq_users_lower_email"


@dataclass(frozen=True, slots=True)
class ClientInfo:
    """Thông tin thiết bị lưu kèm refresh token, để người dùng nhận ra phiên đăng nhập của mình."""

    user_agent: str | None
    ip: str | None


@dataclass(frozen=True, slots=True)
class IssuedSession:
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime
    refresh_id: uuid.UUID
    me: MeResponse


# ---------------------------------------------------------------------------- lỗi
def invalid_credentials() -> AppError:
    return AppError("UNAUTHENTICATED", "Email hoặc mật khẩu không đúng.", status=401)


def session_expired() -> AppError:
    return AppError(
        "UNAUTHENTICATED", "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại.", status=401
    )


def account_locked(until: datetime) -> AppError:
    return AppError(
        "ACCOUNT_LOCKED",
        f"Tài khoản tạm khóa do nhập sai nhiều lần. Thử lại sau {to_local(until):%H:%M}.",
        status=429,
        details={"locked_until": until.isoformat()},
    )


def email_taken() -> AppError:
    return AppError("EMAIL_TAKEN", "Email này đã có tài khoản.", status=409)


# ---------------------------------------------------------------------------- dùng chung
async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    role: UserRole,
    full_name: str,
    phone: str | None = None,
) -> User:
    """Tạo tài khoản: đăng ký, quản trị tạo bác sĩ (catalog), lệnh create-admin, dữ liệu mẫu.

    Chạy trong transaction của người gọi. Email trùng (kể cả hai request cùng lúc) → EMAIL_TAKEN.
    """
    if await repo.email_exists(session, email):
        raise email_taken()
    user = User(
        email=email.strip().lower(),
        password_hash=await hash_password_async(password),
        role=role,
        full_name=full_name,
        phone=phone,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        if violated_constraint(exc) == EMAIL_UNIQUE_INDEX:
            raise email_taken() from exc
        raise
    return user


def to_me(user: User, profile: PatientProfile | None) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role,
        date_of_birth=profile.date_of_birth if profile else None,
        gender=profile.gender if profile else None,
    )


# ---------------------------------------------------------------------------- service
class AuthService:
    def __init__(self, session: AsyncSession, clock: Clock, settings: Settings) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings

    async def register(self, data: RegisterRequest, client: ClientInfo) -> IssuedSession:
        """UC01: tạo bệnh nhân, lưu thời điểm đồng ý xử lý dữ liệu, đăng nhập luôn."""
        now = self._clock.now()
        self._check_birth_date(data.date_of_birth, now)
        async with self._session.begin():
            user = await create_user(
                self._session,
                email=data.email,
                password=data.password,
                role=UserRole.PATIENT,
                full_name=data.full_name,
                phone=data.phone,
            )
            user.privacy_consent_at = now
            profile = PatientProfile(
                user_id=user.id, date_of_birth=data.date_of_birth, gender=data.gender
            )
            self._session.add(profile)
            issued = await self._issue(user, profile, client, now)
        log.info("auth.registered", user_id=user.id)
        return issued

    async def login(self, email: str, password: str, client: ClientInfo) -> IssuedSession:
        """UC02, FR-AUTH-03: sai 5 lần liên tiếp thì khóa 15 phút; đúng thì đặt lại bộ đếm."""
        now = self._clock.now()
        error: AppError | None = None
        issued: IssuedSession | None = None
        async with self._session.begin():
            user = await repo.get_user_by_email(self._session, email, for_update=True)
            if user is None or not user.is_active or user.anonymized_at is not None:
                await verify_password_async(None, password)  # cân bằng thời gian phản hồi
                error = invalid_credentials()
            elif user.locked_until is not None and user.locked_until > now:
                error = account_locked(user.locked_until)
            elif not await verify_password_async(user.password_hash, password):
                error = self._count_failure(user, now) or invalid_credentials()
            else:
                user.failed_login_count = 0
                user.locked_until = None
                issued = await self._issue(user, await self._profile_of(user), client, now)
        # Raise sau khi transaction đã commit, để bộ đếm lần sai được lưu lại.
        if error is not None:
            log.info("auth.login_failed", code=error.code)
            raise error
        assert issued is not None
        log.info("auth.logged_in", user_id=issued.me.id)
        return issued

    async def refresh(self, raw_token: str | None, client: ClientInfo) -> IssuedSession:
        """Xoay vòng refresh token. Dùng lại token đã thu hồi → thu hồi cả family (docs 4.6)."""
        if not raw_token:
            raise session_expired()
        now = self._clock.now()
        error: AppError | None = None
        issued: IssuedSession | None = None
        async with self._session.begin():
            token = await repo.get_refresh_token_for_update(
                self._session, hash_refresh_token(raw_token)
            )
            if token is None or token.expires_at <= now:
                error = session_expired()
            elif token.revoked_at is not None:
                rotated_moments_ago = (
                    token.replaced_by is not None and now - token.revoked_at <= REUSE_GRACE
                )
                if rotated_moments_ago:
                    issued = await self._issue_for_family(token, client, now)
                else:
                    await repo.revoke_family(self._session, token.family_id, now)
                    log.warning("auth.refresh_token_reused", user_id=token.user_id)
                if issued is None:
                    error = session_expired()
            else:
                issued = await self._issue_for_family(token, client, now)
                token.revoked_at = now
                if issued is None:
                    error = session_expired()
                else:
                    token.replaced_by = issued.refresh_id
        if error is not None:
            raise error
        assert issued is not None
        return issued

    async def logout(self, raw_token: str | None) -> None:
        """Thu hồi refresh token hiện tại; gọi nhiều lần vẫn an toàn."""
        if not raw_token:
            return
        now = self._clock.now()
        async with self._session.begin():
            token = await repo.get_refresh_token_for_update(
                self._session, hash_refresh_token(raw_token)
            )
            if token is not None and token.revoked_at is None:
                token.revoked_at = now

    async def get_me(self, actor: Actor) -> MeResponse:
        async with self._session.begin():
            user = await self._load_user(actor)
            profile = await self._profile_of(user)
        return to_me(user, profile)

    async def update_me(self, actor: Actor, data: UpdateMeRequest) -> MeResponse:
        """FR-AUTH-06: sửa họ tên, số điện thoại; bệnh nhân sửa thêm ngày sinh, giới tính."""
        if data.date_of_birth is not None:
            self._check_birth_date(data.date_of_birth, self._clock.now())
        async with self._session.begin():
            user = await self._load_user(actor, for_update=True)
            profile = await self._profile_of(user)
            if profile is None and data.date_of_birth is not None:
                raise field_error("date_of_birth", "Chỉ hồ sơ bệnh nhân có ngày sinh.")
            if profile is None and data.gender is not None:
                raise field_error("gender", "Chỉ hồ sơ bệnh nhân có giới tính.")
            if data.full_name is not None:
                user.full_name = data.full_name
            if data.phone is not None:
                user.phone = data.phone
            if profile is not None and data.date_of_birth is not None:
                profile.date_of_birth = data.date_of_birth
            if profile is not None and data.gender is not None:
                profile.gender = data.gender
        return to_me(user, profile)

    async def change_password(
        self, actor: Actor, data: ChangePasswordRequest, client: ClientInfo
    ) -> IssuedSession:
        """Đổi mật khẩu thu hồi mọi phiên, rồi cấp phiên mới cho chính thiết bị này (docs 4.6).

        Nhập sai mật khẩu hiện tại cũng tính vào bộ đếm khóa như đăng nhập, để token bị lộ không
        dùng được vào việc đoán mật khẩu không giới hạn.
        """
        now = self._clock.now()
        error: AppError | None = None
        issued: IssuedSession | None = None
        async with self._session.begin():
            user = await self._load_user(actor, for_update=True)
            if user.locked_until is not None and user.locked_until > now:
                error = account_locked(user.locked_until)
            elif not await verify_password_async(user.password_hash, data.current_password):
                error = self._count_failure(user, now) or field_error(
                    "current_password", "Mật khẩu hiện tại không đúng."
                )
            else:
                user.failed_login_count = 0
                user.password_hash = await hash_password_async(data.new_password)
                await repo.revoke_all_of_user(self._session, user.id, now)
                issued = await self._issue(user, await self._profile_of(user), client, now)
        if error is not None:
            raise error
        assert issued is not None
        log.info("auth.password_changed", user_id=issued.me.id)
        return issued

    # ------------------------------------------------------------------------ nội bộ
    async def _load_user(self, actor: Actor, *, for_update: bool = False) -> User:
        if actor.user_id is None:
            raise session_expired()
        user = await repo.get_user(self._session, actor.user_id, for_update=for_update)
        if user is None or not user.is_active or user.anonymized_at is not None:
            raise session_expired()
        return user

    def _count_failure(self, user: User, now: datetime) -> AppError | None:
        """Tăng bộ đếm sai mật khẩu; lần thứ 5 khóa 15 phút và trả lỗi ACCOUNT_LOCKED."""
        user.failed_login_count += 1
        if user.failed_login_count < MAX_FAILED_LOGINS:
            return None
        locked_until = now + LOCK_DURATION
        user.locked_until = locked_until
        user.failed_login_count = 0
        return account_locked(locked_until)

    async def _profile_of(self, user: User) -> PatientProfile | None:
        if user.role is not UserRole.PATIENT:
            return None
        return await repo.get_patient_profile(self._session, user.id)

    async def _issue_for_family(
        self, token: RefreshToken, client: ClientInfo, now: datetime
    ) -> IssuedSession | None:
        """Cấp token mới cùng family; None nếu tài khoản đã bị khóa hoặc ẩn danh hóa."""
        user = await repo.get_user(self._session, token.user_id)
        if user is None or not user.is_active or user.anonymized_at is not None:
            await repo.revoke_family(self._session, token.family_id, now)
            return None
        return await self._issue(user, await self._profile_of(user), client, now, token.family_id)

    async def _issue(
        self,
        user: User,
        profile: PatientProfile | None,
        client: ClientInfo,
        now: datetime,
        family_id: uuid.UUID | None = None,
    ) -> IssuedSession:
        access_token, access_expires_at = create_access_token(user, now, self._settings)
        raw_refresh = new_refresh_token()
        token = RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            family_id=family_id or uuid.uuid4(),
            expires_at=now + timedelta(days=self._settings.refresh_token_ttl_days),
            user_agent=client.user_agent,
            ip=client.ip,
        )
        self._session.add(token)
        await self._session.flush()
        return IssuedSession(
            access_token=access_token,
            access_expires_at=access_expires_at,
            refresh_token=raw_refresh,
            refresh_expires_at=token.expires_at,
            refresh_id=token.id,
            me=to_me(user, profile),
        )

    def _check_birth_date(self, value: date, now: datetime) -> None:
        if value > to_local(now).date() or value < MIN_BIRTH_DATE:
            raise field_error("date_of_birth", "Ngày sinh không hợp lệ.")
