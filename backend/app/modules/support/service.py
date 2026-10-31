"""Nghiệp vụ của module support: quy tắc, phân quyền theo bản ghi, ranh giới transaction.

Không biết về HTTP; nhận `Actor` thay vì request để web và Agent dùng chung.
"""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.clock import Clock
from app.core.errors import field_error, forbidden
from app.core.timeutil import to_local
from app.db.enums import SupportStatus, UserRole
from app.db.models.agent import SupportRequest
from app.modules.support import repository as repo
from app.modules.support.schemas import MAX_SUMMARY_LENGTH, SupportRequestOut

log = structlog.get_logger(__name__)


class SupportService:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    async def create(
        self, actor: Actor, *, summary: str, conversation_id: uuid.UUID | None
    ) -> SupportRequestOut:
        """Yêu cầu chuyển nhân viên từ Agent, vào hàng chờ của quản trị (FR-AGT-07, UC11).

        Chỉ bệnh nhân, cho chính mình, trong hội thoại của chính mình (kiểm lại ở đây dù module
        agent đã kiểm). Hội thoại đã có yêu cầu đang mở thì cập nhật tóm tắt mới vào yêu cầu đó
        thay vì tạo thêm, để hàng chờ không bị trùng.
        """
        if actor.role is not UserRole.PATIENT or actor.user_id is None:
            raise forbidden()
        text = summary.strip()
        if not text or len(text) > MAX_SUMMARY_LENGTH:
            raise field_error("summary", f"Tóm tắt dài 1–{MAX_SUMMARY_LENGTH} ký tự.")
        now = self._clock.now()
        async with self._session.begin():
            if conversation_id is not None:
                owner = await repo.conversation_owner(self._session, conversation_id)
                if owner != actor.user_id:
                    raise forbidden()
            request = await repo.open_request(self._session, actor.user_id, conversation_id)
            if request is None:
                request = SupportRequest(
                    patient_id=actor.user_id,
                    conversation_id=conversation_id,
                    summary=text,
                    status=SupportStatus.OPEN,
                    created_at=now,
                )
                self._session.add(request)
            else:
                request.summary = text
            await self._session.flush()
        log.info("support.requested", support_request_id=request.id, channel=actor.channel.value)
        return SupportRequestOut(
            id=request.id, status=request.status, created_at=to_local(request.created_at)
        )
