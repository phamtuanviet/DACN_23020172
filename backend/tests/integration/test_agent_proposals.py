"""Đề xuất và xác nhận của Agent (docs mục 6.4, BR-06, AC-12, AC-13).

LLM chỉ tạo được đề xuất; lịch hẹn chỉ đổi khi bệnh nhân gọi endpoint confirm bằng JWT của mình,
và lúc đó đi đúng service của web với kênh AGENT.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import date, time
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.config import Settings
from app.core.db import get_sessionmaker
from app.core.errors import AppError
from app.db.enums import (
    AppointmentStatus,
    Channel,
    HistoryAction,
    ProposalStatus,
    UserRole,
)
from app.db.models.agent import AgentProposal
from app.db.models.appointments import Appointment, AppointmentHistory
from app.modules.agent import repository as agent_repo
from app.modules.agent.proposals import ProposalService, ProposeArgs
from app.modules.support.service import SupportService
from tests.integration.agent_support import (
    ScriptedModel,
    agent_settings,
    call,
    parse_sse,
    say,
    use_agent,
)
from tests.integration.conftest import MutableClock
from tests.integration.factories import (
    MONDAY,
    Clinic,
    add_appointment,
    at,
    bearer,
    build_clinic,
    fetch,
)

pytestmark = pytest.mark.integration

SATURDAY = date(2026, 10, 17)
SATURDAY_8 = at(SATURDAY, 8)


@pytest.fixture
async def settings() -> AsyncIterator[Settings]:
    settings = agent_settings()
    valkey = Redis.from_url(settings.valkey_url.get_secret_value())
    await valkey.flushdb()
    yield settings
    await valkey.flushdb()
    await valkey.aclose()


@pytest.fixture
async def clinic(app_client: AsyncClient, db: AsyncSession) -> Clinic:
    return await build_clinic(db)


async def propose(
    app: FastAPI,
    client: AsyncClient,
    settings: Settings,
    patient_id: int,
    conversation_id: str | None = None,
    **args: Any,
) -> tuple[list[tuple[str, Any]], str]:
    """Một lượt chat mà LLM gọi propose_booking; trả các sự kiện và conversation_id."""
    model = ScriptedModel(script=[call("propose_booking", **args), say("Bạn bấm Xác nhận nhé.")])
    use_agent(app, model, settings)
    response = await client.post(
        "/api/v1/agent/chat",
        json={"message": "Đặt khung đó giúp tôi", "conversation_id": conversation_id},
        headers=bearer(patient_id, UserRole.PATIENT),
    )
    assert response.status_code == 200, response.text
    events = parse_sse(response.text)
    meta = next(data for name, data in events if name == "meta")
    return events, meta["conversation_id"]


def proposal_of(events: list[tuple[str, Any]]) -> dict[str, Any]:
    return next(data for name, data in events if name == "proposal")


def tool_error(events: list[tuple[str, Any]]) -> dict[str, Any]:
    return next(data for name, data in events if name == "tool" and data["status"] == "end")


async def count_appointments(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(Appointment))
    await db.commit()
    return result.scalar_one()


async def confirm(client: AsyncClient, proposal_id: str, patient_id: int, **kwargs: Any) -> Any:
    return await client.post(
        f"/api/v1/agent/proposals/{proposal_id}/confirm",
        headers=bearer(patient_id, UserRole.PATIENT, **kwargs),
    )


async def test_confirmed_proposal_books_like_the_web(
    app: FastAPI, app_client: AsyncClient, db: AsyncSession, clinic: Clinic, settings: Settings
) -> None:
    """AC-12, AC-13: trước khi bấm Xác nhận không có lịch nào; bấm rồi thì lịch giống hệt web,
    kênh AGENT; bấm lại nhận kết quả cũ, không đặt thêm."""
    patient, doctor = clinic.patient_ids[0], clinic.doctor_ids[0]
    events, conversation_id = await propose(
        app,
        app_client,
        settings,
        patient,
        action="BOOK",
        service_id=clinic.service_id,
        doctor_id=doctor,
        start_at=SATURDAY_8,
        reason="Nổi mẩn đỏ ở tay",
    )
    card = proposal_of(events)
    assert card["status"] == "PENDING" and card["type"] == "BOOK"
    assert card["display"] == {
        "service": "Khám da liễu tổng quát",
        "doctor": "BS. Bác Sĩ 0",
        "when": "Thứ Bảy, 17/10/2026 · 08:00–08:20",
        "reason": "Nổi mẩn đỏ ở tay",
        "code": None,
        "old_when": None,
        "old_doctor": None,
    }
    assert card["expires_at"] == "2026-10-10T09:10:00+07:00"
    assert await count_appointments(db) == 0

    response = await confirm(app_client, card["id"], patient)
    assert response.status_code == 200, response.text
    body = response.json()
    appointment = body["appointment"]
    assert appointment["channel"] == "AGENT" and appointment["status"] == "BOOKED"
    assert appointment["start_at"] == SATURDAY_8 and appointment["doctor"]["id"] == doctor
    assert body["proposal"]["status"] == "CONFIRMED"
    assert body["proposal"]["appointment_code"] == appointment["code"]

    mine = await app_client.get(
        "/api/v1/appointments/me", headers=bearer(patient, UserRole.PATIENT)
    )
    assert [a["code"] for a in mine.json()["items"]] == [appointment["code"]]
    history = (
        (await db.execute(select(AppointmentHistory).order_by(AppointmentHistory.id)))
        .scalars()
        .all()
    )
    assert [(h.action, h.channel, h.actor_id) for h in history] == [
        (HistoryAction.CREATE, Channel.AGENT, patient)
    ]

    again = await confirm(app_client, card["id"], patient)
    assert again.status_code == 200
    assert again.json()["appointment"]["id"] == appointment["id"]
    assert await count_appointments(db) == 1

    conversation = await app_client.get(
        f"/api/v1/agent/conversations/{conversation_id}/messages",
        headers=bearer(patient, UserRole.PATIENT),
    )
    items = conversation.json()["items"]
    assert [i["kind"] for i in items] == ["user", "tool", "assistant"]
    assert items[1]["proposal"]["status"] == "CONFIRMED"
    assert items[1]["proposal"]["appointment_code"] == appointment["code"]


async def test_expired_proposal_changes_nothing(
    app: FastAPI,
    app_client: AsyncClient,
    db: AsyncSession,
    clinic: Clinic,
    settings: Settings,
    clock: MutableClock,
) -> None:
    """AC-13, BR-06: quá 10 phút thì xác nhận bị từ chối, database không đổi."""
    patient = clinic.patient_ids[0]
    events, _ = await propose(
        app,
        app_client,
        settings,
        patient,
        action="BOOK",
        service_id=clinic.service_id,
        doctor_id=clinic.doctor_ids[0],
        start_at=SATURDAY_8,
    )
    clock.advance(minutes=10)

    response = await confirm(app_client, proposal_of(events)["id"], patient, issued_at=clock.at)
    assert response.status_code == 409
    assert response.json()["code"] == "PROPOSAL_EXPIRED"
    assert response.json()["details"]["proposal_status"] == "EXPIRED"
    assert await count_appointments(db) == 0
    stored = (await db.execute(select(AgentProposal))).scalar_one()
    assert stored.status is ProposalStatus.EXPIRED


async def test_slot_taken_before_confirm_marks_proposal_failed(
    app: FastAPI, app_client: AsyncClient, db: AsyncSession, clinic: Clinic, settings: Settings
) -> None:
    """UC09 8a: khung bị người khác đặt trong lúc chờ → SLOT_TAKEN kèm khung thay thế, đề xuất
    FAILED, bệnh nhân không có lịch nào."""
    patient, rival = clinic.patient_ids
    doctor = clinic.doctor_ids[0]
    events, conversation_id = await propose(
        app,
        app_client,
        settings,
        patient,
        action="BOOK",
        service_id=clinic.service_id,
        doctor_id=doctor,
        start_at=SATURDAY_8,
    )
    taken = await app_client.post(
        "/api/v1/appointments",
        json={"service_id": clinic.service_id, "doctor_id": doctor, "start_at": SATURDAY_8},
        headers=bearer(rival, UserRole.PATIENT),
    )
    assert taken.status_code == 201

    response = await confirm(app_client, proposal_of(events)["id"], patient)
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "SLOT_TAKEN"
    assert body["details"]["proposal_status"] == "FAILED"
    assert body["details"]["alternatives"]
    owners = (await db.execute(select(Appointment.patient_id))).scalars().all()
    assert owners == [rival]

    conversation = await app_client.get(
        f"/api/v1/agent/conversations/{conversation_id}/messages",
        headers=bearer(patient, UserRole.PATIENT),
    )
    items = conversation.json()["items"]
    assert items[1]["proposal"]["status"] == "FAILED"
    assert items[1]["proposal"]["error"].startswith("Khung giờ vừa được người khác đặt")
    # Thông báo cho LLM ở lượt sau vẫn nằm trong hội thoại, giao diện hiện kết quả trên thẻ.
    assert [i["kind"] for i in items] == ["user", "tool", "assistant"]
    assert items[2]["text"] == "Bạn bấm Xác nhận nhé."


async def test_new_proposal_replaces_pending_one_and_reject_writes_nothing(
    app: FastAPI, app_client: AsyncClient, db: AsyncSession, clinic: Clinic, settings: Settings
) -> None:
    """Mỗi hội thoại một đề xuất đang chờ; bấm Hủy trên thẻ thì không ghi gì (UC09 7a)."""
    patient, doctor = clinic.patient_ids[0], clinic.doctor_ids[0]
    first, conversation_id = await propose(
        app,
        app_client,
        settings,
        patient,
        action="BOOK",
        service_id=clinic.service_id,
        doctor_id=doctor,
        start_at=SATURDAY_8,
    )
    second, _ = await propose(
        app,
        app_client,
        settings,
        patient,
        conversation_id,
        action="BOOK",
        service_id=clinic.service_id,
        doctor_id=doctor,
        start_at=at(SATURDAY, 8, 20),
    )
    old, new = proposal_of(first)["id"], proposal_of(second)["id"]
    stale = await confirm(app_client, old, patient)
    assert stale.status_code == 409 and stale.json()["code"] == "PROPOSAL_EXPIRED"

    rejected = await app_client.post(
        f"/api/v1/agent/proposals/{new}/reject", headers=bearer(patient, UserRole.PATIENT)
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "REJECTED"
    late = await confirm(app_client, new, patient)
    assert late.status_code == 409 and late.json()["code"] == "PROPOSAL_NOT_PENDING"
    assert await count_appointments(db) == 0


async def test_only_the_owner_can_confirm_or_reject(
    app: FastAPI, app_client: AsyncClient, db: AsyncSession, clinic: Clinic, settings: Settings
) -> None:
    """AC-05 cho đề xuất: bệnh nhân khác nhận 403; id không tồn tại nhận 404."""
    owner, other = clinic.patient_ids
    events, _ = await propose(
        app,
        app_client,
        settings,
        owner,
        action="BOOK",
        service_id=clinic.service_id,
        doctor_id=clinic.doctor_ids[0],
        start_at=SATURDAY_8,
    )
    proposal_id = proposal_of(events)["id"]
    assert (await confirm(app_client, proposal_id, other)).status_code == 403
    rejected = await app_client.post(
        f"/api/v1/agent/proposals/{proposal_id}/reject", headers=bearer(other, UserRole.PATIENT)
    )
    assert rejected.status_code == 403
    assert (await confirm(app_client, str(uuid.uuid4()), owner)).status_code == 404
    assert await count_appointments(db) == 0


async def test_invented_slot_never_becomes_a_card(
    app: FastAPI, app_client: AsyncClient, db: AsyncSession, clinic: Clinic, settings: Settings
) -> None:
    """Docs mục 6.6: LLM bịa giờ (08:05 không có trên lưới) → tool trả lỗi, không có thẻ."""
    events, _ = await propose(
        app,
        app_client,
        settings,
        clinic.patient_ids[0],
        action="BOOK",
        service_id=clinic.service_id,
        doctor_id=clinic.doctor_ids[0],
        start_at=at(SATURDAY, 8, 5),
    )
    assert not [name for name, _ in events if name == "proposal"]
    status = tool_error(events)
    assert status["ok"] is False and status["label"] == "Chưa tạo được đề xuất"
    assert (await db.execute(select(func.count()).select_from(AgentProposal))).scalar_one() == 0


async def test_reschedule_and_cancel_through_proposals(
    app: FastAPI, app_client: AsyncClient, db: AsyncSession, clinic: Clinic, settings: Settings
) -> None:
    """UC10: đổi giữ nguyên mã, hủy trả khung; lịch sử ghi kênh AGENT."""
    patient, doctor = clinic.patient_ids[0], clinic.doctor_ids[0]
    appointment_id = await add_appointment(db, clinic, day=MONDAY, start=time(8, 0))
    events, conversation_id = await propose(
        app,
        app_client,
        settings,
        patient,
        action="RESCHEDULE",
        appointment_id=appointment_id,
        doctor_id=doctor,
        start_at=at(MONDAY, 9, 0),
    )
    card = proposal_of(events)
    assert card["display"]["old_when"] == "Thứ Hai, 12/10/2026 · 08:00–08:20"
    assert card["display"]["when"] == "Thứ Hai, 12/10/2026 · 09:00–09:20"
    assert card["display"]["code"] == "LH-TEST-120800" + "00"
    moved = await confirm(app_client, card["id"], patient)
    assert moved.status_code == 200, moved.text
    assert moved.json()["appointment"]["start_at"] == at(MONDAY, 9, 0)

    events, _ = await propose(
        app,
        app_client,
        settings,
        patient,
        conversation_id,
        action="CANCEL",
        appointment_id=appointment_id,
        cancel_reason="Bận việc đột xuất",
    )
    cancelled = await confirm(app_client, proposal_of(events)["id"], patient)
    assert cancelled.status_code == 200
    stored = await fetch(db, appointment_id)
    assert stored.status is AppointmentStatus.CANCELLED
    assert stored.cancel_reason == "Bận việc đột xuất"
    channels = (
        await db.execute(
            select(AppointmentHistory.action, AppointmentHistory.channel).order_by(
                AppointmentHistory.id
            )
        )
    ).all()
    assert [tuple(row) for row in channels] == [
        (HistoryAction.RESCHEDULE, Channel.AGENT),
        (HistoryAction.CANCEL, Channel.AGENT),
    ]


async def test_change_deadline_is_checked_again_at_confirm(
    app: FastAPI,
    app_client: AsyncClient,
    db: AsyncSession,
    clinic: Clinic,
    settings: Settings,
    clock: MutableClock,
) -> None:
    """BR-08 kiểm lại lúc xác nhận: đề xuất tạo lúc còn đủ 2 giờ, bấm Xác nhận khi đã quá mốc."""
    patient = clinic.patient_ids[0]
    appointment_id = await add_appointment(db, clinic, day=date(2026, 10, 10), start=time(11, 5))
    events, _ = await propose(
        app, app_client, settings, patient, action="CANCEL", appointment_id=appointment_id
    )
    clock.advance(minutes=6)

    response = await confirm(app_client, proposal_of(events)["id"], patient, issued_at=clock.at)
    assert response.status_code == 409
    assert response.json()["code"] == "CHANGE_DEADLINE_PASSED"
    assert response.json()["details"]["clinic_phone"] == "028 3822 0000"
    assert (await fetch(db, appointment_id)).status is AppointmentStatus.BOOKED


async def test_double_click_confirms_once(
    wide_pool: None,
    app: FastAPI,
    app_client: AsyncClient,
    db: AsyncSession,
    clinic: Clinic,
    settings: Settings,
) -> None:
    """Hai lần bấm Xác nhận cùng lúc: lần sau chờ khóa đề xuất rồi nhận lại kết quả cũ."""
    patient = clinic.patient_ids[0]
    events, _ = await propose(
        app,
        app_client,
        settings,
        patient,
        action="BOOK",
        service_id=clinic.service_id,
        doctor_id=clinic.doctor_ids[0],
        start_at=SATURDAY_8,
    )
    proposal_id = proposal_of(events)["id"]

    first, second = await asyncio.gather(
        confirm(app_client, proposal_id, patient), confirm(app_client, proposal_id, patient)
    )
    assert (first.status_code, second.status_code) == (200, 200)
    assert first.json()["appointment"]["id"] == second.json()["appointment"]["id"]
    assert await count_appointments(db) == 1


async def test_expire_job_closes_overdue_proposals(
    app: FastAPI,
    app_client: AsyncClient,
    db: AsyncSession,
    clinic: Clinic,
    settings: Settings,
    clock: MutableClock,
) -> None:
    patient = clinic.patient_ids[0]
    await propose(
        app,
        app_client,
        settings,
        patient,
        action="BOOK",
        service_id=clinic.service_id,
        doctor_id=clinic.doctor_ids[0],
        start_at=SATURDAY_8,
    )
    async with db.begin():
        assert await agent_repo.expire_due(db, clock.now()) == 0
    clock.advance(minutes=10)
    async with db.begin():
        assert await agent_repo.expire_due(db, clock.now()) == 1
    stored = (await db.execute(select(AgentProposal))).scalar_one()
    assert stored.status is ProposalStatus.EXPIRED and stored.decided_at is not None


async def test_services_check_ownership_themselves(
    app: FastAPI,
    app_client: AsyncClient,
    db: AsyncSession,
    clinic: Clinic,
    settings: Settings,
    clock: MutableClock,
) -> None:
    """Phân quyền lớp 2 (docs mục 4.6): ProposalService, SupportService tự kiểm vai trò và chủ
    hội thoại, không dựa vào người gọi — kể cả khi sau này có nơi khác gọi chúng."""
    owner, other = clinic.patient_ids
    events, conversation_id = await propose(
        app,
        app_client,
        settings,
        owner,
        action="BOOK",
        service_id=clinic.service_id,
        doctor_id=clinic.doctor_ids[0],
        start_at=SATURDAY_8,
    )
    conversation = uuid.UUID(conversation_id)
    args = ProposeArgs(
        action="BOOK",
        service_id=clinic.service_id,
        doctor_id=clinic.doctor_ids[0],
        start_at=SATURDAY_8,
    )
    intruder = Actor(user_id=other, role=UserRole.PATIENT, channel=Channel.AGENT)
    admin = Actor(user_id=clinic.admin_id, role=UserRole.ADMIN, channel=Channel.ADMIN)
    for actor in (intruder, admin):
        async with get_sessionmaker()() as session:
            with pytest.raises(AppError) as denied:
                await ProposalService(session, clock, settings).create(actor, conversation, args)
            assert denied.value.status == 403
    async with get_sessionmaker()() as session:
        with pytest.raises(AppError) as denied:
            await SupportService(session, clock).create(
                intruder, summary="Gắn vào hội thoại người khác", conversation_id=conversation
            )
        assert denied.value.status == 403
    # Đề xuất đang chờ của chủ hội thoại không bị ai khác thay thế.
    stored = (await db.execute(select(AgentProposal.status))).scalars().all()
    assert stored == [ProposalStatus.PENDING]
    assert proposal_of(events)["status"] == "PENDING"
