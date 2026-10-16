"""Model ORM nhóm users: users, patient_profiles, doctors, refresh_tokens.

Cột, ràng buộc, chỉ mục theo ERD và docs mục 7.4.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin
from app.db.enums import Gender, UserRole


class User(TimestampMixin, Base):
    """Tài khoản đăng nhập chung cho bệnh nhân, bác sĩ, quản trị."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"))
    full_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    failed_login_count: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # docs mục 7.4: thời điểm đồng ý xử lý dữ liệu; thời điểm ẩn danh hóa khi xóa tài khoản
    privacy_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# Email không trùng, không phân biệt hoa thường (ERD mục 5.2).
Index("uq_users_lower_email", func.lower(User.email), unique=True)


class PatientProfile(Base):
    """Thông tin riêng của bệnh nhân (1–1 với users)."""

    __tablename__ = "patient_profiles"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    date_of_birth: Mapped[date] = mapped_column(Date)
    gender: Mapped[Gender] = mapped_column(Enum(Gender, name="gender"))


class Doctor(Base):
    """Thông tin riêng của bác sĩ; tài khoản do quản trị tạo (FR-AUTH-05)."""

    __tablename__ = "doctors"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    specialty_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("specialties.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(50))  # ví dụ "ThS. BS.", "BS.CKI"
    bio: Mapped[str | None] = mapped_column(Text)
    gender: Mapped[Gender] = mapped_column(Enum(Gender, name="gender"))


class RefreshToken(CreatedAtMixin, Base):
    """Refresh token xoay vòng; chỉ lưu SHA-256 của token (docs mục 4.6, 7.4)."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(INET)
