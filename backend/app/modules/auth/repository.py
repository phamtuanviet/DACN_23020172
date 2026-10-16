"""Truy vấn của module auth: users, patient_profiles, refresh_tokens.

Không ra quyết định nghiệp vụ (docs mục 4.2).
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.users import PatientProfile, RefreshToken, User


async def get_user(session: AsyncSession, user_id: int, *, for_update: bool = False) -> User | None:
    stmt = select(User).where(User.id == user_id)
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_user_by_email(
    session: AsyncSession, email: str, *, for_update: bool = False
) -> User | None:
    stmt = select(User).where(func.lower(User.email) == email.strip().lower())
    if for_update:
        stmt = stmt.with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def email_exists(session: AsyncSession, email: str) -> bool:
    stmt = select(User.id).where(func.lower(User.email) == email.strip().lower())
    return (await session.execute(stmt)).first() is not None


async def get_patient_profile(session: AsyncSession, user_id: int) -> PatientProfile | None:
    return await session.get(PatientProfile, user_id)


async def get_refresh_token_for_update(
    session: AsyncSession, token_hash: str
) -> RefreshToken | None:
    """Khóa dòng để hai lần refresh cùng một token chạy lần lượt, không cùng lúc."""
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


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
