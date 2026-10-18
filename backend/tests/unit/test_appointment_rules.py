import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.actor import Actor
from app.core.errors import AppError
from app.db.enums import AppointmentStatus as S
from app.db.enums import Channel, UserRole
from app.db.models.appointments import Appointment
from app.modules.appointments.codes import new_appointment_code
from app.modules.appointments.policy import (
    ensure_can_book,
    ensure_can_change,
    ensure_can_manage_schedule,
    ensure_can_view,
)
from app.modules.appointments.state_machine import can_transition


def test_allowed_transitions() -> None:
    assert can_transition(S.BOOKED, S.ARRIVED)
    assert can_transition(S.ARRIVED, S.COMPLETED)
    assert can_transition(S.BOOKED, S.CANCELLED)


def test_rejected_transitions() -> None:
    assert not can_transition(S.CANCELLED, S.BOOKED)
    assert not can_transition(S.COMPLETED, S.CANCELLED)
    assert not can_transition(S.BOOKED, S.COMPLETED)


def test_appointment_code_format() -> None:
    code = new_appointment_code(date(2026, 10, 10))
    assert re.fullmatch(r"LH-261010-[0-9A-HJKMNP-TV-Z]{4}", code)


def test_only_patients_book_and_only_for_themselves() -> None:
    assert ensure_can_book(Actor(7, UserRole.PATIENT, Channel.AGENT)) == 7
    for actor in (Actor(1, UserRole.ADMIN, Channel.ADMIN), Actor(2, UserRole.DOCTOR, Channel.WEB)):
        with pytest.raises(AppError) as error:
            ensure_can_book(actor)
        assert error.value.code == "FORBIDDEN"


def test_only_admin_or_system_manage_doctor_schedules() -> None:
    ensure_can_manage_schedule(Actor(1, UserRole.ADMIN, Channel.ADMIN))
    ensure_can_manage_schedule(Actor(None, None, Channel.SYSTEM))
    for actor in (
        Actor(2, UserRole.PATIENT, Channel.WEB),
        Actor(2, UserRole.PATIENT, Channel.AGENT),
        Actor(3, UserRole.DOCTOR, Channel.WEB),
        Actor(None, None, Channel.WEB),
    ):
        with pytest.raises(AppError) as error:
            ensure_can_manage_schedule(actor)
        assert error.value.code == "FORBIDDEN"


def _appointment(status: S = S.BOOKED, *, patient_id: int = 7, doctor_id: int = 3) -> Appointment:
    start = datetime(2026, 10, 12, 8, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    return Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        status=status,
        start_at=start,
        end_at=start + timedelta(minutes=20),
    )


def test_change_deadline_error_tells_the_patient_whom_to_call() -> None:
    now = datetime(2026, 10, 12, 6, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    with pytest.raises(AppError) as error:
        ensure_can_change(
            _appointment(),
            Actor(7, UserRole.PATIENT, Channel.AGENT),  # tool của Agent cũng bị chặn như web
            now,
            deadline_hours=2,
            clinic_phone="028 3822 0000",
        )
    assert error.value.code == "CHANGE_DEADLINE_PASSED"
    assert error.value.status == 409
    assert "028 3822 0000" in error.value.message
    assert error.value.details == {"clinic_phone": "028 3822 0000"}


def test_only_owner_or_admin_change_and_doctors_only_view_their_own() -> None:
    now = datetime(2026, 10, 10, 9, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    appointment = _appointment()
    for actor in (
        Actor(8, UserRole.PATIENT, Channel.AGENT),
        Actor(3, UserRole.DOCTOR, Channel.WEB),
        Actor(None, None, Channel.SYSTEM),
    ):
        with pytest.raises(AppError) as error:
            ensure_can_change(appointment, actor, now, deadline_hours=2, clinic_phone="")
        assert error.value.code == "FORBIDDEN"
    ensure_can_view(appointment, Actor(3, UserRole.DOCTOR, Channel.WEB))
    with pytest.raises(AppError):
        ensure_can_view(appointment, Actor(4, UserRole.DOCTOR, Channel.WEB))


def test_finished_appointments_cannot_change() -> None:
    now = datetime(2026, 10, 10, 9, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
    with pytest.raises(AppError) as error:
        ensure_can_change(
            _appointment(S.COMPLETED),
            Actor(1, UserRole.ADMIN, Channel.ADMIN),
            now,
            deadline_hours=2,
            clinic_phone="",
        )
    assert error.value.code == "INVALID_TRANSITION"
    assert error.value.details == {"status": "COMPLETED"}
