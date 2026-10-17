import re
from datetime import date

import pytest

from app.core.actor import Actor
from app.core.errors import AppError
from app.db.enums import AppointmentStatus as S
from app.db.enums import Channel, UserRole
from app.modules.appointments.codes import new_appointment_code
from app.modules.appointments.policy import ensure_can_book, ensure_can_manage_schedule
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
