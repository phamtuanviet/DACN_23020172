"""Truy vấn của module auth: users, patient_profiles, refresh_tokens.

Không ra quyết định nghiệp vụ (docs mục 4.2).
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.users import PatientProfile, RefreshToken, User

# Thứ tự khóa của module auth: dòng users trước, refresh_tokens sau, ở mọi luồng (đăng nhập,
# refresh, đăng xuất, đổi mật khẩu, khóa tài khoản). Nhờ vậy luồng thu hồi token chờ lượt refresh
# đang chạy commit xong rồi mới quét, nên thấy cả token vừa cấp. Dòng users khóa bằng FOR NO KEY
# UPDATE (`key_share=True`): không luồng nào đổi khóa chính của users, nên không cần chặn khóa KEY
# SHARE mà khóa ngoại lấy khi INSERT refresh_tokens; các luồng trên vẫn tuần tự với nhau vì NO KEY
# UPDATE xung đột với chính nó.


async def get_user(session: AsyncSession, user_id: int, *, for_update: bool = False) -> User | None:
    stmt = select(User).where(User.id == user_id)
    if for_update:
        stmt = stmt.with_for_update(key_share=True)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_user_by_email(
    session: AsyncSession, email: str, *, for_update: bool = False
) -> User | None:
    stmt = select(User).where(func.lower(User.email) == email.strip().lower())
    if for_update:
        stmt = stmt.with_for_update(key_share=True)
    return (await session.execute(stmt)).scalar_one_or_none()


async def email_exists(session: AsyncSession, email: str) -> bool:
    stmt = select(User.id).where(func.lower(User.email) == email.strip().lower())
    return (await session.execute(stmt)).first() is not None


async def get_patient_profile(session: AsyncSession, user_id: int) -> PatientProfile | None:
    return await session.get(PatientProfile, user_id)


async def refresh_token_owner(session: AsyncSession, token_hash: str) -> int | None:
    """Chủ của refresh token, đọc không khóa: để khóa dòng users trước rồi mới khóa token."""
    stmt = select(RefreshToken.user_id).where(RefreshToken.token_hash == token_hash)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_refresh_token_for_update(
    session: AsyncSession, token_hash: str
) -> RefreshToken | None:
    """Khóa dòng để hai lần refresh cùng một token chạy lần lượt, không cùng lúc."""
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def family_has_live_token(
    session: AsyncSession, user_id: int, family_id: uuid.UUID, now: datetime
) -> bool:
    """Family còn token chưa thu hồi, chưa hết hạn (lọc theo user để dùng chỉ mục user_id)."""
    stmt = (
        select(RefreshToken.id)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .limit(1)
    )
    return (await session.execute(stmt)).first() is not None


async def revoke_family(session: AsyncSession, family_id: uuid.UUID, now: datetime) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def revoke_all_of_user(session: AsyncSession, user_id: int, now: datetime) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
