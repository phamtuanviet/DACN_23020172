"""Nghiệp vụ của module schedule: quy tắc, phân quyền theo bản ghi, ranh giới transaction.

Không biết về HTTP; nhận `Actor` thay vì request để web và Agent dùng chung.
- Ca không chồng ca: cùng bác sĩ, cùng thứ, khoảng hiệu lực giao nhau và khoảng giờ giao nhau
  thì trả 409 SHIFT_OVERLAP (UC15 bước 3, docs mục 5.7).
- BR-10: thêm ngày nghỉ, sửa hoặc xóa ca làm không bao giờ tự hủy lịch; lịch BOOKED sắp tới bị
  ảnh hưởng được gắn cờ "cần xử lý" qua module appointments. `dry_run` chỉ liệt kê, không ghi.
"""

from dataclasses import asdict
from datetime import date, datetime, time

import structlog
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.clock import Clock
from app.core.errors import AppError, forbidden, not_found, validation_error
from app.core.timeutil import local_datetime, to_local
from app.db.enums import UserRole
from app.db.models.schedule import Shift, TimeOff
from app.modules.appointments.service import (
    AffectedAppointment,
    booked_for_doctor,
    flag_for_attention,
)
from app.modules.schedule import repository as repo
from app.modules.schedule.schemas import (
    AffectedOut,
    ShiftChangeOut,
    ShiftIn,
    ShiftOut,
    ShiftUpdate,
    TimeOffChangeOut,
    TimeOffIn,
    TimeOffOut,
)
from app.modules.scheduling.engine import Interval, ShiftRule, within_shifts

log = structlog.get_logger(__name__)


def shift_overlap(other: Shift) -> AppError:
    valid_to = f"{other.valid_to:%d/%m/%Y}" if other.valid_to else "không thời hạn"
    return AppError(
        "SHIFT_OVERLAP",
        f"Ca này chồng lên ca {other.start_time:%H:%M}–{other.end_time:%H:%M} đã có "
        f"(hiệu lực {other.valid_from:%d/%m/%Y} – {valid_to}).",
        status=409,
        details={"shift_id": other.id},
    )


def _overlaps(data: ShiftIn, other: Shift) -> bool:
    if data.weekday != other.weekday:
        return False
    data_to, other_to = data.valid_to or date.max, other.valid_to or date.max
    if data.valid_from > other_to or other.valid_from > data_to:
        return False
    return data.start_time < other.end_time and other.start_time < data.end_time


def _rule(doctor_id: int, data: ShiftIn | Shift) -> ShiftRule:
    return ShiftRule(
        doctor_id, data.weekday, data.start_time, data.end_time, data.valid_from, data.valid_to
    )


def _shift_out(shift: Shift) -> ShiftOut:
    return ShiftOut(
        id=shift.id,
        doctor_id=shift.doctor_id,
        weekday=shift.weekday,
        start_time=shift.start_time,
        end_time=shift.end_time,
        valid_from=shift.valid_from,
        valid_to=shift.valid_to,
    )


def _time_off_out(time_off: TimeOff) -> TimeOffOut:
    return TimeOffOut(
        id=time_off.id,
        doctor_id=time_off.doctor_id,
        start_at=to_local(time_off.start_at),
        end_at=to_local(time_off.end_at),
        reason=time_off.reason,
    )


def _affected_out(item: AffectedAppointment) -> AffectedOut:
    data = asdict(item)
    data["start_at"], data["end_at"] = to_local(item.start_at), to_local(item.end_at)
    return AffectedOut(**data)


class ScheduleService:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    # ------------------------------------------------------------ ca làm
    async def list_shifts(self, actor: Actor, doctor_id: int) -> list[ShiftOut]:
        _require_admin(actor)
        async with self._session.begin():
            await self._ensure_doctor(doctor_id)
            return [_shift_out(s) for s in await repo.shifts_of(self._session, doctor_id)]

    async def create_shift(self, actor: Actor, doctor_id: int, data: ShiftIn) -> ShiftOut:
        """Thêm ca: chỉ mở thêm giờ khám nên không ảnh hưởng lịch đã đặt."""
        _require_admin(actor)
        async with self._session.begin():
            await self._lock_doctor(doctor_id)
            for other in await repo.shifts_of(self._session, doctor_id):
                if _overlaps(data, other):
                    raise shift_overlap(other)
            shift = Shift(doctor_id=doctor_id, **data.model_dump())
            self._session.add(shift)
            await self._session.flush()
            result = _shift_out(shift)
        log.info("schedule.shift_created", shift_id=result.id, doctor_id=doctor_id)
        return result

    async def update_shift(
        self, actor: Actor, doctor_id: int, shift_id: int, data: ShiftUpdate, *, dry_run: bool
    ) -> ShiftChangeOut:
        """Sửa ca; thu hẹp ca thì lịch không còn nằm trong ca nào bị gắn cờ (docs mục 5.7)."""
        _require_admin(actor)
        async with self._session.begin():
            await self._lock_doctor(doctor_id)
            shift = await self._get_shift(doctor_id, shift_id)
            current = ShiftIn.model_validate(_shift_out(shift).model_dump())
            try:
                merged = ShiftIn.model_validate(
                    {**current.model_dump(), **data.model_dump(exclude_unset=True)}
                )
            except ValidationError as exc:
                raise validation_error(exc) from exc
            others = [s for s in await repo.shifts_of(self._session, doctor_id) if s.id != shift_id]
            for other in others:
                if _overlaps(merged, other):
                    raise shift_overlap(other)
            before = [_rule(doctor_id, s) for s in others] + [_rule(doctor_id, current)]
            after = [_rule(doctor_id, s) for s in others] + [_rule(doctor_id, merged)]
            affected = await self._uncovered(actor, doctor_id, before, after)
            if not dry_run:
                for field, value in merged.model_dump().items():
                    setattr(shift, field, value)
                await self._session.flush()
                await self._flag(actor, affected, source="SHIFT_CHANGE", ref_id=shift_id)
            result = ShiftChangeOut(
                dry_run=dry_run,
                shift=ShiftOut(id=shift_id, doctor_id=doctor_id, **merged.model_dump()),
                affected=[_affected_out(a) for a in affected],
            )
        if not dry_run:
            log.info("schedule.shift_updated", shift_id=shift_id, flagged=len(affected))
        return result

    async def delete_shift(
        self, actor: Actor, doctor_id: int, shift_id: int, *, dry_run: bool
    ) -> ShiftChangeOut:
        _require_admin(actor)
        async with self._session.begin():
            await self._lock_doctor(doctor_id)
            shift = await self._get_shift(doctor_id, shift_id)
            others = [s for s in await repo.shifts_of(self._session, doctor_id) if s.id != shift_id]
            before = [_rule(doctor_id, s) for s in [*others, shift]]
            after = [_rule(doctor_id, s) for s in others]
            affected = await self._uncovered(actor, doctor_id, before, after)
            if not dry_run:
                await self._session.delete(shift)
                await self._session.flush()
                await self._flag(actor, affected, source="SHIFT_DELETE", ref_id=shift_id)
        if not dry_run:
            log.info("schedule.shift_deleted", shift_id=shift_id, flagged=len(affected))
        return ShiftChangeOut(
            dry_run=dry_run, shift=None, affected=[_affected_out(a) for a in affected]
        )

    # ------------------------------------------------------------ ngày nghỉ
    async def list_time_offs(
        self, actor: Actor, doctor_id: int, since: date | None
    ) -> list[TimeOffOut]:
        """Ngày nghỉ còn hiệu lực từ `since` (mặc định hôm nay)."""
        _require_admin(actor)
        since = since or to_local(self._clock.now()).date()
        async with self._session.begin():
            await self._ensure_doctor(doctor_id)
            items = await repo.time_offs_of(
                self._session, doctor_id, local_datetime(since, time(0))
            )
        return [_time_off_out(t) for t in items]

    async def create_time_off(
        self, actor: Actor, doctor_id: int, data: TimeOffIn, *, dry_run: bool
    ) -> TimeOffChangeOut:
        """UC15 bước 4–6: `dry_run` liệt kê lịch bị ảnh hưởng; ghi thật thì gắn cờ các lịch đó."""
        _require_admin(actor)
        now = self._clock.now()
        async with self._session.begin():
            await self._lock_doctor(doctor_id)
            affected = [
                a
                for a in await booked_for_doctor(
                    self._session, actor, doctor_id, start=data.start_at, end=data.end_at
                )
                if a.start_at > now
            ]
            time_off: TimeOffOut | None = None
            if not dry_run:
                row = TimeOff(doctor_id=doctor_id, created_by=actor.user_id, **data.model_dump())
                self._session.add(row)
                await self._session.flush()
                await self._flag(actor, affected, source="TIME_OFF", ref_id=row.id)
                time_off = _time_off_out(row)
        if time_off is not None:
            log.info("schedule.time_off_created", time_off_id=time_off.id, flagged=len(affected))
        return TimeOffChangeOut(
            dry_run=dry_run, time_off=time_off, affected=[_affected_out(a) for a in affected]
        )

    async def delete_time_off(self, actor: Actor, doctor_id: int, time_off_id: int) -> None:
        """Xóa ngày nghỉ chỉ trả lại giờ khám; cờ đã gắn giữ nguyên để quản trị tự gỡ."""
        _require_admin(actor)
        async with self._session.begin():
            await self._lock_doctor(doctor_id)
            row = await repo.get_time_off(self._session, doctor_id, time_off_id)
            if row is None:
                raise not_found("Không tìm thấy ngày nghỉ.")
            await self._session.delete(row)
        log.info("schedule.time_off_deleted", time_off_id=time_off_id)

    # ------------------------------------------------------------ nội bộ
    async def _ensure_doctor(self, doctor_id: int) -> None:
        if not await repo.doctor_exists(self._session, doctor_id):
            raise not_found("Không tìm thấy bác sĩ.")

    async def _lock_doctor(self, doctor_id: int) -> None:
        if await repo.lock_doctor(self._session, doctor_id) is None:
            raise not_found("Không tìm thấy bác sĩ.")

    async def _get_shift(self, doctor_id: int, shift_id: int) -> Shift:
        shift = await repo.get_shift(self._session, doctor_id, shift_id)
        if shift is None:
            raise not_found("Không tìm thấy ca làm.")
        return shift

    async def _uncovered(
        self, actor: Actor, doctor_id: int, before: list[ShiftRule], after: list[ShiftRule]
    ) -> list[AffectedAppointment]:
        """Lịch BOOKED sắp tới đang nằm trong ca, nhưng sau thay đổi không còn nằm trong ca nào."""
        now: datetime = self._clock.now()
        upcoming = await booked_for_doctor(self._session, actor, doctor_id, start=now)
        result: list[AffectedAppointment] = []
        for item in upcoming:
            interval = Interval(item.start_at, item.end_at)
            if (
                item.start_at > now
                and within_shifts(before, doctor_id, interval)
                and not within_shifts(after, doctor_id, interval)
            ):
                result.append(item)
        return result

    async def _flag(
        self, actor: Actor, affected: list[AffectedAppointment], *, source: str, ref_id: int
    ) -> None:
        await flag_for_attention(
            self._session,
            actor,
            [a.id for a in affected],
            source={"source": source, "ref_id": ref_id},
        )


def _require_admin(actor: Actor) -> None:
    if actor.role is not UserRole.ADMIN:
        raise forbidden()
