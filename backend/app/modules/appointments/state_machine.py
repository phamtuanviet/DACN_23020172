"""Sơ đồ trạng thái lịch hẹn (BR-11, FR-APT-06, docs mục 5.5)."""

from app.db.enums import AppointmentStatus

ALLOWED_TRANSITIONS: dict[AppointmentStatus, frozenset[AppointmentStatus]] = {
    AppointmentStatus.BOOKED: frozenset(
        {AppointmentStatus.ARRIVED, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW}
    ),
    AppointmentStatus.ARRIVED: frozenset({AppointmentStatus.COMPLETED}),
}


def can_transition(current: AppointmentStatus, target: AppointmentStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())
