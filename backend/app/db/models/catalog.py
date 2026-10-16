"""Model ORM nhóm catalog: specialties, services, doctor_services.

Cột, ràng buộc, chỉ mục theo ERD và docs mục 7.4.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Specialty(Base):
    __tablename__ = "specialties"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Service(Base):
    """Dịch vụ khám; `scope_description` là phạm vi khám mà Agent dùng để giải thích (US-10)."""

    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("specialty_id", "name"),
        CheckConstraint(
            "duration_min BETWEEN 10 AND 120 AND duration_min % 5 = 0", name="duration"
        ),
        CheckConstraint("ref_price_vnd >= 0", name="price"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    specialty_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("specialties.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(150))
    scope_description: Mapped[str] = mapped_column(Text)
    duration_min: Mapped[int] = mapped_column(SmallInteger)
    ref_price_vnd: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class DoctorService(Base):
    """Bác sĩ nào thực hiện dịch vụ nào (N–N)."""

    __tablename__ = "doctor_services"

    doctor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("doctors.user_id", ondelete="CASCADE"), primary_key=True
    )
    service_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("services.id", ondelete="CASCADE"), primary_key=True
    )
