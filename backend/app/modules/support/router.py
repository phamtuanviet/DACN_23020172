"""HTTP của module support: khai báo endpoint, nhận DTO, tạo Actor, gọi service.

Không chứa nghiệp vụ, không truy vấn database (docs mục 4.2). Bệnh nhân tạo yêu cầu qua tool
`handoff_to_staff` của Agent, không qua HTTP; ở đây chỉ có hàng chờ của quản trị (FR-ADM-04).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.core.db import SessionDep
from app.core.security import AdminActorDep, ClockDep
from app.core.validation import MAX_ID
from app.db.enums import SupportStatus
from app.modules.support.schemas import SupportRequestAdminOut, SupportRequestUpdate
from app.modules.support.service import SupportService


def get_support_service(session: SessionDep, clock: ClockDep) -> SupportService:
    return SupportService(session, clock)


SupportServiceDep = Annotated[SupportService, Depends(get_support_service)]
IdPath = Annotated[int, Path(ge=1, le=MAX_ID)]

router = APIRouter(prefix="/admin/support-requests", tags=["admin-support"])


@router.get("")
async def list_support_requests(
    actor: AdminActorDep, service: SupportServiceDep, status: SupportStatus | None = None
) -> list[SupportRequestAdminOut]:
    """Yêu cầu chuyển nhân viên từ trợ lý (UC11, UC16): đang mở cũ nhất trước."""
    return await service.admin_list(actor, status)


@router.patch("/{request_id}")
async def update_support_request(
    request_id: IdPath,
    body: SupportRequestUpdate,
    actor: AdminActorDep,
    service: SupportServiceDep,
) -> SupportRequestAdminOut:
    """Đánh dấu đã xử lý hoặc mở lại (FR-ADM-04)."""
    return await service.update(actor, request_id, body)
