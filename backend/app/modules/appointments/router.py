"""HTTP của module appointments: khai báo endpoint, nhận DTO, tạo Actor, gọi service.

Không chứa nghiệp vụ, không truy vấn database (docs mục 4.2). Lớp 1 chặn sai vai trò; quyền trên
từng lịch (chủ lịch, bác sĩ của lịch) kiểm ở service (docs mục 4.6).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status

from app.core.db import SessionDep
from app.core.ratelimit import APPOINTMENT_WRITE_LIMIT, limiter, user_or_ip
from app.core.security import (
    ActorDep,
    ClockDep,
    DoctorOrAdminActorDep,
    PatientActorDep,
    PatientOrAdminActorDep,
    SettingsDep,
)
from app.core.validation import MAX_ID
from app.db.enums import AppointmentStatus
from app.modules.appointments.schemas import (
    AppointmentDetail,
    AppointmentOut,
    AppointmentPage,
    BookRequest,
    CancelRequest,
    RescheduleRequest,
    Scope,
    StatusChangeRequest,
)
from app.modules.appointments.service import MAX_PAGE_SIZE, AppointmentService


def get_appointment_service(
    session: SessionDep, clock: ClockDep, settings: SettingsDep
) -> AppointmentService:
    return AppointmentService(session, clock, settings)


AppointmentServiceDep = Annotated[AppointmentService, Depends(get_appointment_service)]
IdPath = Annotated[int, Path(ge=1, le=MAX_ID)]

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit(APPOINTMENT_WRITE_LIMIT, key_func=user_or_ip)
async def book_appointment(
    request: Request, body: BookRequest, actor: PatientActorDep, service: AppointmentServiceDep
) -> AppointmentOut:
    """Đặt lịch cho chính mình (UC05, FR-APT-01). `doctor_id` rỗng: bác sĩ bất kỳ.

    Lỗi: BOOKING_WINDOW, SLOT_NOT_OFFERED, DOCTOR_SERVICE_MISMATCH (400); SLOT_TAKEN kèm
    `details.alternatives`, PATIENT_OVERLAP, MAX_ACTIVE_APPOINTMENTS (409); RATE_LIMITED (429)
    khi đặt, đổi, hủy quá 10 lần/phút.
    """
    return await service.book(actor, body)


@router.get("/me")
async def my_appointments(
    actor: PatientActorDep,
    service: AppointmentServiceDep,
    scope: Annotated[Scope, Query(description="upcoming: sắp tới; history: lịch sử")] = (
        Scope.UPCOMING
    ),
    status: AppointmentStatus | None = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> AppointmentPage:
    """Lịch sắp tới (gần nhất trước) và lịch sử (mới nhất trước), lọc theo trạng thái (UC08)."""
    return await service.list_mine(
        actor, scope=scope, status=status, page=page, page_size=page_size
    )


@router.get("/{appointment_id}")
async def get_appointment(
    appointment_id: IdPath, actor: ActorDep, service: AppointmentServiceDep
) -> AppointmentDetail:
    """Chi tiết, ghi chú bác sĩ, lịch sử thay đổi. Chủ lịch, bác sĩ của lịch, quản trị; người khác
    nhận 403 (AC-05)."""
    return await service.get(actor, appointment_id)


@router.patch("/{appointment_id}/reschedule")
@limiter.limit(APPOINTMENT_WRITE_LIMIT, key_func=user_or_ip)
async def reschedule_appointment(
    request: Request,
    appointment_id: IdPath,
    body: RescheduleRequest,
    actor: PatientOrAdminActorDep,
    service: AppointmentServiceDep,
) -> AppointmentOut:
    """Đổi lịch, giữ nguyên mã và dịch vụ (UC06, FR-APT-02, FR-ADM-03).

    Lỗi: như đặt lịch; thêm CHANGE_DEADLINE_PASSED kèm `details.clinic_phone` khi bệnh nhân còn
    dưới 2 giờ, INVALID_TRANSITION khi lịch không còn ở trạng thái Đã đặt (409). Thất bại thì lịch
    cũ giữ nguyên (AC-04).
    """
    return await service.reschedule(actor, appointment_id, body)


@router.post("/{appointment_id}/cancel")
@limiter.limit(APPOINTMENT_WRITE_LIMIT, key_func=user_or_ip)
async def cancel_appointment(
    request: Request,
    appointment_id: IdPath,
    body: CancelRequest,
    actor: PatientOrAdminActorDep,
    service: AppointmentServiceDep,
) -> AppointmentOut:
    """Hủy lịch kèm lý do tùy chọn (UC07, FR-APT-03). Lỗi: CHANGE_DEADLINE_PASSED,
    INVALID_TRANSITION (409)."""
    return await service.cancel(actor, appointment_id, body)


@router.patch("/{appointment_id}/status")
async def change_appointment_status(
    appointment_id: IdPath,
    body: StatusChangeRequest,
    actor: DoctorOrAdminActorDep,
    service: AppointmentServiceDep,
) -> AppointmentOut:
    """Đã đến, Đã khám, Vắng mặt theo sơ đồ trạng thái (FR-APT-06, FR-DOC-02). Bác sĩ chỉ cập
    nhật lịch của mình trong ngày; chuyển sai sơ đồ trả 409 INVALID_TRANSITION."""
    return await service.change_status(actor, appointment_id, body)
