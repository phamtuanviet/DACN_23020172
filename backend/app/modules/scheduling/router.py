"""HTTP của module scheduling: khai báo endpoint, nhận DTO, tạo Actor, gọi service.

Không chứa nghiệp vụ, không truy vấn database (docs mục 4.2). Khung trống là dữ liệu công khai và
luôn tính mới, không cache (TD-05).
"""

from datetime import time
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from app.core.db import SessionDep
from app.core.security import ClockDep, SettingsDep
from app.core.validation import MAX_ID, ReasonableDate
from app.modules.scheduling.schemas import AvailabilityOut, EarliestOut
from app.modules.scheduling.service import AvailabilityQuery, SchedulingService


def get_scheduling_service(
    session: SessionDep, clock: ClockDep, settings: SettingsDep
) -> SchedulingService:
    return SchedulingService(session, clock, settings)


SchedulingServiceDep = Annotated[SchedulingService, Depends(get_scheduling_service)]

router = APIRouter(prefix="/availability", tags=["scheduling"])


@router.get("")
async def get_availability(
    service: SchedulingServiceDep,
    service_id: Annotated[int, Query(ge=1, le=MAX_ID)],
    doctor_id: Annotated[
        int | None, Query(ge=1, le=MAX_ID, description="Bỏ trống: bác sĩ bất kỳ")
    ] = None,
    date_from: Annotated[ReasonableDate | None, Query(description="Mặc định: hôm nay")] = None,
    date_to: Annotated[ReasonableDate | None, Query(description="Mặc định: bằng date_from")] = None,
    time_from: Annotated[time | None, Query(description="Lọc buổi, ví dụ 07:00")] = None,
    time_to: Annotated[time | None, Query(description="Lọc buổi, ví dụ 12:00")] = None,
) -> AvailabilityOut:
    """Khung trống theo dịch vụ, bác sĩ, khoảng ngày, khoảng giờ (FR-SCH-01..05).

    Ngày là ngày địa phương `YYYY-MM-DD`; tối đa 31 ngày một lần.
    """
    query = AvailabilityQuery(service_id, doctor_id, date_from, date_to, time_from, time_to)
    return await service.availability(query)


@router.get("/earliest")
async def get_earliest(
    service: SchedulingServiceDep,
    service_id: Annotated[
        list[Annotated[int, Field(ge=1, le=MAX_ID)]], Query(min_length=1, max_length=50)
    ],
    by_doctor: bool = False,
) -> EarliestOut:
    """Khung trống sớm nhất trong 30 ngày của từng dịch vụ; `by_doctor=true` thì của từng bác sĩ.

    Dùng cho các dòng "Sớm nhất: …" ở trang dịch vụ, hồ sơ bác sĩ và bước chọn bác sĩ.
    """
    return await service.earliest(service_id, by_doctor=by_doctor)
