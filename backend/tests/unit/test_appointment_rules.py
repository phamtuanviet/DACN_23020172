import re
from datetime import date

from app.db.enums import AppointmentStatus as S
from app.modules.appointments.codes import new_appointment_code
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
