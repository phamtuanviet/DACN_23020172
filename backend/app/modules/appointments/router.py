"""HTTP của module appointments: khai báo endpoint, nhận DTO, tạo Actor, gọi service.

Không chứa nghiệp vụ, không truy vấn database (docs mục 4.2).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.db import SessionDep
from app.core.security import ClockDep, PatientActorDep, SettingsDep
from app.modules.appointments.schemas import AppointmentOut, BookRequest
from app.modules.appointments.service import AppointmentService


def get_appointment_service(
    session: SessionDep, clock: ClockDep, settings: SettingsDep
) -> AppointmentService:
    return AppointmentService(session, clock, settings)


AppointmentServiceDep = Annotated[AppointmentService, Depends(get_appointment_service)]

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def book_appointment(
    body: BookRequest, actor: PatientActorDep, service: AppointmentServiceDep
) -> AppointmentOut:
    """Đặt lịch cho chính mình (UC05, FR-APT-01). `doctor_id` rỗng: bác sĩ bất kỳ.

    Lỗi: BOOKING_WINDOW, SLOT_NOT_OFFERED, DOCTOR_SERVICE_MISMATCH (400); SLOT_TAKEN kèm
    `details.alternatives`, PATIENT_OVERLAP, MAX_ACTIVE_APPOINTMENTS (409).
    """
    return await service.book(actor, body)
