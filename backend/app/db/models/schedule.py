"""Model ORM nhóm schedule: shifts, time_offs.

Cột, ràng buộc, chỉ mục theo ERD và docs mục 7.4.
"""

from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Shift(Base):
    """Ca làm lặp hằng tuần, giờ địa phương của phòng khám (docs mục 7.6)."""

    __tablename__ = "shifts"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 1 AND 7", name="weekday"),
        CheckConstraint("end_time > start_time", name="time_order"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="valid_range"),
        Index("ix_shifts_doctor_id_weekday", "doctor_id", "weekday"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    doctor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("doctors.user_id", ondelete="CASCADE")
    )
    weekday: Mapped[int] = mapped_column(SmallInteger)  # 1 = thứ Hai … 7 = Chủ nhật
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)


class TimeOff(Base):
    """Khoảng nghỉ của bác sĩ, ghi đè lên ca làm."""

    __tablename__ = "time_offs"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="time_order"),
        Index("ix_time_offs_doctor_id_start_at", "doctor_id", "start_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    doctor_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("doctors.user_id", ondelete="CASCADE")
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
