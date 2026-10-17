"""HTTP của module schedule: khai báo endpoint, nhận DTO, tạo Actor, gọi service.

Không chứa nghiệp vụ, không truy vấn database (docs mục 4.2). Mọi endpoint cần vai trò ADMIN.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.core.db import SessionDep
from app.core.security import AdminActorDep, ClockDep
from app.core.validation import MAX_ID, ReasonableDate
from app.modules.schedule.schemas import (
    ShiftChangeOut,
    ShiftIn,
    ShiftOut,
    ShiftUpdate,
    TimeOffChangeOut,
    TimeOffIn,
    TimeOffOut,
)
from app.modules.schedule.service import ScheduleService


def get_schedule_service(session: SessionDep, clock: ClockDep) -> ScheduleService:
    return ScheduleService(session, clock)


ScheduleServiceDep = Annotated[ScheduleService, Depends(get_schedule_service)]
DryRun = Annotated[
    bool, Query(description="true: chỉ liệt kê lịch bị ảnh hưởng, không ghi gì (UC15 bước 5)")
]

IdPath = Annotated[int, Path(ge=1, le=MAX_ID)]

router = APIRouter(prefix="/admin/doctors/{doctor_id}", tags=["admin-schedule"])


# ---------------------------------------------------------------------------- ca làm
@router.get("/shifts")
async def list_shifts(
    doctor_id: IdPath, actor: AdminActorDep, service: ScheduleServiceDep
) -> list[ShiftOut]:
    return await service.list_shifts(actor, doctor_id)


@router.post("/shifts", status_code=status.HTTP_201_CREATED)
async def create_shift(
    doctor_id: IdPath, body: ShiftIn, actor: AdminActorDep, service: ScheduleServiceDep
) -> ShiftOut:
    """Thêm ca lặp hằng tuần; chồng ca đã có thì 409 SHIFT_OVERLAP (FR-ADM-02)."""
    return await service.create_shift(actor, doctor_id, body)


@router.patch("/shifts/{shift_id}")
async def update_shift(
    doctor_id: IdPath,
    shift_id: IdPath,
    body: ShiftUpdate,
    actor: AdminActorDep,
    service: ScheduleServiceDep,
    dry_run: DryRun = False,
) -> ShiftChangeOut:
    """Sửa ca; lịch BOOKED không còn nằm trong ca nào được gắn cờ cần xử lý (BR-10)."""
    return await service.update_shift(actor, doctor_id, shift_id, body, dry_run=dry_run)


@router.delete("/shifts/{shift_id}")
async def delete_shift(
    doctor_id: IdPath,
    shift_id: IdPath,
    actor: AdminActorDep,
    service: ScheduleServiceDep,
    dry_run: DryRun = False,
) -> ShiftChangeOut:
    """Xóa ca; lịch BOOKED trong ca được gắn cờ cần xử lý, không bị hủy (BR-10)."""
    return await service.delete_shift(actor, doctor_id, shift_id, dry_run=dry_run)


# ---------------------------------------------------------------------------- ngày nghỉ
@router.get("/time-offs")
async def list_time_offs(
    doctor_id: IdPath,
    actor: AdminActorDep,
    service: ScheduleServiceDep,
    since: Annotated[ReasonableDate | None, Query(description="Mặc định: hôm nay")] = None,
) -> list[TimeOffOut]:
    return await service.list_time_offs(actor, doctor_id, since)


@router.post("/time-offs", status_code=status.HTTP_201_CREATED)
async def create_time_off(
    doctor_id: IdPath,
    body: TimeOffIn,
    response: Response,
    actor: AdminActorDep,
    service: ScheduleServiceDep,
    dry_run: DryRun = False,
) -> TimeOffChangeOut:
    """Thêm ngày nghỉ (UC15 bước 4–6). `dry_run=true` trả 200 và danh sách lịch bị ảnh hưởng;
    ghi thật trả 201 và gắn cờ các lịch đó (BR-10)."""
    if dry_run:
        response.status_code = status.HTTP_200_OK
    return await service.create_time_off(actor, doctor_id, body, dry_run=dry_run)


@router.delete("/time-offs/{time_off_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_time_off(
    doctor_id: IdPath, time_off_id: IdPath, actor: AdminActorDep, service: ScheduleServiceDep
) -> None:
    await service.delete_time_off(actor, doctor_id, time_off_id)
