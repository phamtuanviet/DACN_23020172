"""HTTP của module reports: khai báo endpoint, nhận DTO, tạo Actor, gọi service.

Không chứa nghiệp vụ, không truy vấn database (docs mục 4.2).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status

from app.core.db import SessionDep
from app.core.ratelimit import appointment_write_limit
from app.core.security import AdminActorDep, ClockDep, PatientActorDep
from app.core.validation import MAX_ID, ReasonableDate
from app.modules.appointments.schemas import ReviewOut
from app.modules.reports.schemas import ReviewCreate, StatsOut
from app.modules.reports.service import ReportService


def get_report_service(session: SessionDep, clock: ClockDep) -> ReportService:
    return ReportService(session, clock)


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]
IdPath = Annotated[int, Path(ge=1, le=MAX_ID)]

reviews_router = APIRouter(prefix="/appointments", tags=["reports"])
admin_router = APIRouter(prefix="/admin", tags=["admin-reports"])


@reviews_router.post("/{appointment_id}/review", status_code=status.HTTP_201_CREATED)
@appointment_write_limit
async def create_review(
    request: Request,
    appointment_id: IdPath,
    body: ReviewCreate,
    actor: PatientActorDep,
    service: ReportServiceDep,
) -> ReviewOut:
    """Đánh giá bác sĩ 1–5 sao kèm nhận xét tùy chọn, cho lịch Đã khám của chính mình, mỗi lịch
    một lần (UC20, FR-RPT-02). Lỗi: FORBIDDEN (403), INVALID_TRANSITION khi lịch chưa Đã khám,
    ALREADY_REVIEWED (409); RATE_LIMITED (429) như các thao tác ghi lịch hẹn."""
    return await service.create_review(actor, appointment_id, body)


@admin_router.get("/stats")
async def admin_stats(
    actor: AdminActorDep,
    service: ReportServiceDep,
    date_from: Annotated[
        ReasonableDate | None, Query(description="Ngày đầu, giờ Việt Nam; mặc định 13 ngày trước")
    ] = None,
    date_to: Annotated[
        ReasonableDate | None, Query(description="Ngày cuối, tối đa 31 ngày; mặc định hôm nay")
    ] = None,
) -> StatsOut:
    """Số liệu dashboard: số lịch theo ngày, tỷ lệ hủy, tỷ lệ vắng mặt, số lịch theo bác sĩ, tỷ lệ
    đặt qua web và Agent (UC19, FR-RPT-01)."""
    return await service.stats(actor, date_from, date_to)


router = APIRouter()
router.include_router(reviews_router)
router.include_router(admin_router)
