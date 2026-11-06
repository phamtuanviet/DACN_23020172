"""Nghiệp vụ của module catalog: quy tắc, phân quyền theo bản ghi, ranh giới transaction.

Không biết về HTTP; nhận `Actor` thay vì request để web và Agent dùng chung.
Danh mục không bao giờ bị xóa cứng: quản trị ẩn bằng `is_active` (FR-CAT-05). Chuyên khoa bị ẩn
thì dịch vụ và bác sĩ của nó cũng không hiện ở trang công khai và không đặt được.
"""

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.clock import Clock
from app.core.errors import AppError, field_error, forbidden, not_found, violated_constraint
from app.core.timeutil import to_local
from app.db.enums import UserRole
from app.db.models.catalog import Service, Specialty
from app.db.models.users import Doctor
from app.modules.auth.service import create_user, update_staff_account
from app.modules.catalog import repository as repo
from app.modules.catalog.schemas import (
    DoctorAdminOut,
    DoctorCreate,
    DoctorDetail,
    DoctorOut,
    DoctorRef,
    DoctorUpdate,
    ServiceAdminOut,
    ServiceBrief,
    ServiceCreate,
    ServiceOut,
    ServiceUpdate,
    SpecialtyAdminOut,
    SpecialtyCreate,
    SpecialtyOut,
    SpecialtyRef,
    SpecialtyUpdate,
    WorkingHours,
)

log = structlog.get_logger(__name__)

MAX_SEARCH_TOKENS = 8
SPECIALTY_NAME_UNIQUE = "uq_specialties_name"
SERVICE_NAME_UNIQUE = "uq_services_specialty_id_name"


def search_tokens(q: str | None) -> list[str]:
    """Tách từ khóa; chuẩn hóa NFC để chữ có dấu gõ kiểu tổ hợp vẫn khớp (FR-CAT-04)."""
    if not q:
        return []
    return unicodedata.normalize("NFC", q).split()[:MAX_SEARCH_TOKENS]


# ---------------------------------------------------------------------------- dùng chung
@dataclass(frozen=True, slots=True)
class ServiceInfo:
    id: int
    name: str
    duration_min: int


async def get_bookable_service(session: AsyncSession, service_id: int) -> ServiceInfo | None:
    """Dịch vụ đặt được (dịch vụ và chuyên khoa đang hoạt động); scheduling, appointments dùng.

    Chạy trong transaction của người gọi.
    """
    services = await get_bookable_services(session, [service_id])
    return services[0] if services else None


async def get_bookable_services(
    session: AsyncSession, service_ids: Sequence[int]
) -> list[ServiceInfo]:
    rows = await repo.bookable_services(session, service_ids)
    return [ServiceInfo(s.id, s.name, s.duration_min) for s in rows]


async def service_exists(session: AsyncSession, service_id: int) -> bool:
    return await repo.get_service_row(session, service_id) is not None


async def active_doctor_ids(session: AsyncSession, service_id: int) -> list[int]:
    """Bác sĩ đang hoạt động thực hiện dịch vụ, theo id tăng dần ("Bác sĩ bất kỳ", UC05 2a)."""
    doctors = await repo.doctors_by_service(session, [service_id])
    return [doctor_id for doctor_id, _ in doctors.get(service_id, [])]


# ---------------------------------------------------------------------------- chuyển đổi
def _service_out(row: repo.ServiceRow, doctors: list[tuple[int, str]]) -> ServiceOut:
    service = row.service
    return ServiceOut(
        id=service.id,
        name=service.name,
        specialty=SpecialtyRef(id=service.specialty_id, name=row.specialty_name),
        scope_description=service.scope_description,
        duration_min=service.duration_min,
        ref_price_vnd=service.ref_price_vnd,
        doctors=[DoctorRef(id=doctor_id, name=name) for doctor_id, name in doctors],
    )


def _service_brief(service: Service) -> ServiceBrief:
    return ServiceBrief(
        id=service.id,
        name=service.name,
        duration_min=service.duration_min,
        ref_price_vnd=service.ref_price_vnd,
    )


def _doctor_out(row: repo.DoctorRow, services: list[Service]) -> DoctorOut:
    return DoctorOut(
        id=row.doctor.user_id,
        name=row.name,
        title=row.doctor.title,
        gender=row.doctor.gender,
        specialty=SpecialtyRef(id=row.doctor.specialty_id, name=row.specialty_name),
        services=[_service_brief(s) for s in services],
    )


def _specialty_out(row: repo.SpecialtyRow) -> SpecialtyOut:
    return SpecialtyOut(
        id=row.specialty.id,
        name=row.specialty.name,
        description=row.specialty.description,
        service_count=row.service_count,
        doctor_count=row.doctor_count,
        min_price_vnd=row.min_price_vnd,
    )


def _specialty_admin(row: repo.SpecialtyRow) -> SpecialtyAdminOut:
    return SpecialtyAdminOut(**_specialty_out(row).model_dump(), is_active=row.specialty.is_active)


MAX_DISPLAY_NAME = 100  # cột users.full_name


def display_name(title: str, full_name: str) -> str:
    """Tên hiển thị của bác sĩ là chức danh + họ tên ("BS.CKI Nguyễn Thu Hà"), lưu ở users."""
    name = f"{title} {full_name}"
    if len(name) > MAX_DISPLAY_NAME:
        raise field_error(
            "full_name", f"Chức danh và họ tên cộng lại tối đa {MAX_DISPLAY_NAME} ký tự."
        )
    return name


def _plain_name(name: str, title: str) -> str:
    prefix = f"{title} "
    return name[len(prefix) :] if name.startswith(prefix) else name


def _doctor_admin(
    row: repo.DoctorAccountRow, service_ids: list[int], upcoming: int
) -> DoctorAdminOut:
    doctor = row.doctor
    return DoctorAdminOut(
        id=doctor.user_id,
        name=row.name,
        title=doctor.title,
        full_name=_plain_name(row.name, doctor.title),
        email=row.email,
        gender=doctor.gender,
        bio=doctor.bio,
        specialty=SpecialtyRef(id=doctor.specialty_id, name=row.specialty_name),
        service_ids=service_ids,
        is_active=row.is_active,
        upcoming_count=upcoming,
    )


# ---------------------------------------------------------------------------- service
class CatalogService:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    # ------------------------------------------------------------ đọc công khai (FR-CAT-04)
    async def list_specialties(self) -> list[SpecialtyOut]:
        async with self._session.begin():
            rows = await repo.list_specialties(self._session, include_hidden=False)
        return [_specialty_out(row) for row in rows]

    async def search_services(self, q: str | None, specialty_id: int | None) -> list[ServiceOut]:
        async with self._session.begin():
            rows = await repo.search_services(
                self._session,
                tokens=search_tokens(q),
                specialty_id=specialty_id,
                include_hidden=False,
            )
            doctors = await repo.doctors_by_service(self._session, [r.service.id for r in rows])
        return [_service_out(row, doctors.get(row.service.id, [])) for row in rows]

    async def search_doctors(
        self, q: str | None, specialty_id: int | None, service_id: int | None
    ) -> list[DoctorOut]:
        async with self._session.begin():
            rows = await repo.search_doctors(
                self._session,
                tokens=search_tokens(q),
                specialty_id=specialty_id,
                service_id=service_id,
            )
            services = await repo.services_by_doctor(
                self._session, [r.doctor.user_id for r in rows]
            )
        return [_doctor_out(row, services.get(row.doctor.user_id, [])) for row in rows]

    async def get_doctor(self, doctor_id: int) -> DoctorDetail:
        """Hồ sơ bác sĩ (UC03). Bác sĩ bị khóa hoặc thuộc chuyên khoa đã ẩn: 404."""
        today = to_local(self._clock.now()).date()
        async with self._session.begin():
            row = await repo.get_active_doctor(self._session, doctor_id)
            if row is None:
                raise not_found("Không tìm thấy bác sĩ.")
            services = await repo.services_by_doctor(self._session, [doctor_id])
            shifts = await repo.current_shifts(self._session, doctor_id, today)
        base = _doctor_out(row, services.get(doctor_id, []))
        return DoctorDetail(
            **base.model_dump(),
            bio=row.doctor.bio,
            working_hours=[
                WorkingHours(weekday=s.weekday, start_time=s.start_time, end_time=s.end_time)
                for s in shifts
            ],
        )

    # ------------------------------------------------------------ quản trị (FR-CAT-01, 02, 05)
    async def admin_list_specialties(self, actor: Actor) -> list[SpecialtyAdminOut]:
        _require_admin(actor)
        async with self._session.begin():
            rows = await repo.list_specialties(self._session, include_hidden=True)
        return [_specialty_admin(row) for row in rows]

    async def create_specialty(self, actor: Actor, data: SpecialtyCreate) -> SpecialtyAdminOut:
        _require_admin(actor)
        async with self._session.begin():
            if await repo.specialty_name_taken(self._session, data.name):
                raise _specialty_name_taken()
            specialty = Specialty(name=data.name, description=data.description)
            self._session.add(specialty)
            await self._flush_specialty()
            result = await self._specialty_admin_out(specialty.id)
        log.info("catalog.specialty_created", specialty_id=result.id, actor_id=actor.user_id)
        return result

    async def update_specialty(
        self, actor: Actor, specialty_id: int, data: SpecialtyUpdate
    ) -> SpecialtyAdminOut:
        _require_admin(actor)
        changes = data.model_dump(exclude_unset=True)
        async with self._session.begin():
            specialty = await repo.get_specialty(self._session, specialty_id)
            if specialty is None:
                raise not_found("Không tìm thấy chuyên khoa.")
            if changes.get("name") is None:
                changes.pop("name", None)
            if changes.get("is_active") is None:
                changes.pop("is_active", None)
            if "name" in changes and await repo.specialty_name_taken(
                self._session, changes["name"], exclude_id=specialty_id
            ):
                raise _specialty_name_taken()
            for field, value in changes.items():
                setattr(specialty, field, value)
            await self._flush_specialty()
            result = await self._specialty_admin_out(specialty_id)
        log.info("catalog.specialty_updated", specialty_id=specialty_id, actor_id=actor.user_id)
        return result

    async def admin_list_services(
        self, actor: Actor, q: str | None, specialty_id: int | None
    ) -> list[ServiceAdminOut]:
        _require_admin(actor)
        async with self._session.begin():
            rows = await repo.search_services(
                self._session,
                tokens=search_tokens(q),
                specialty_id=specialty_id,
                include_hidden=True,
            )
            return await self._services_admin_out(rows)

    async def create_service(self, actor: Actor, data: ServiceCreate) -> ServiceAdminOut:
        _require_admin(actor)
        async with self._session.begin():
            if await repo.get_specialty(self._session, data.specialty_id) is None:
                raise field_error("specialty_id", "Chuyên khoa không tồn tại.")
            if await repo.service_name_taken(self._session, data.specialty_id, data.name):
                raise _service_name_taken()
            service = Service(**data.model_dump())
            self._session.add(service)
            await self._flush_service()
            result = await self._service_admin_out(service.id)
        log.info("catalog.service_created", service_id=result.id, actor_id=actor.user_id)
        return result

    async def update_service(
        self, actor: Actor, service_id: int, data: ServiceUpdate
    ) -> ServiceAdminOut:
        """Sửa hoặc ẩn dịch vụ. Lịch đã đặt giữ nguyên thời lượng cũ vì đã lưu `end_at`."""
        _require_admin(actor)
        changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
        async with self._session.begin():
            row = await repo.get_service_row(self._session, service_id)
            if row is None:
                raise not_found("Không tìm thấy dịch vụ.")
            service = row.service
            specialty_id = changes.get("specialty_id", service.specialty_id)
            if "specialty_id" in changes and (
                await repo.get_specialty(self._session, specialty_id) is None
            ):
                raise field_error("specialty_id", "Chuyên khoa không tồn tại.")
            name = changes.get("name", service.name)
            if ("name" in changes or "specialty_id" in changes) and (
                await repo.service_name_taken(
                    self._session, specialty_id, name, exclude_id=service_id
                )
            ):
                raise _service_name_taken()
            for field, value in changes.items():
                setattr(service, field, value)
            await self._flush_service()
            result = await self._service_admin_out(service_id)
        log.info("catalog.service_updated", service_id=service_id, actor_id=actor.user_id)
        return result

    # ------------------------------------------------------------ bác sĩ (FR-ADM-01, FR-CAT-03)
    async def admin_list_doctors(
        self, actor: Actor, q: str | None, specialty_id: int | None
    ) -> list[DoctorAdminOut]:
        _require_admin(actor)
        now = self._clock.now()
        async with self._session.begin():
            rows = await repo.list_doctor_accounts(
                self._session, tokens=search_tokens(q), specialty_id=specialty_id
            )
            return await self._doctors_admin_out(rows, now)

    async def create_doctor(self, actor: Actor, data: DoctorCreate) -> DoctorAdminOut:
        """Tạo tài khoản bác sĩ qua `create_user` của auth (docs mục 4.3), gán chuyên khoa và dịch
        vụ trong cùng một transaction. Email trùng → 409 EMAIL_TAKEN."""
        _require_admin(actor)
        now = self._clock.now()
        async with self._session.begin():
            if await repo.get_specialty(self._session, data.specialty_id) is None:
                raise field_error("specialty_id", "Chuyên khoa không tồn tại.")
            await self._check_services(data.service_ids, data.specialty_id)
            user = await create_user(
                self._session,
                email=data.email,
                password=data.password,
                role=UserRole.DOCTOR,
                full_name=display_name(data.title, data.full_name),
            )
            self._session.add(
                Doctor(
                    user_id=user.id,
                    specialty_id=data.specialty_id,
                    title=data.title,
                    bio=data.bio,
                    gender=data.gender,
                )
            )
            await self._session.flush()  # bảng không khai báo relationship: ghi bác sĩ trước
            await repo.replace_doctor_services(self._session, user.id, data.service_ids)
            result = await self._doctor_admin_out(user.id, now)
        log.info("catalog.doctor_created", doctor_id=result.id, actor_id=actor.user_id)
        return result

    async def update_doctor(
        self, actor: Actor, doctor_id: int, data: DoctorUpdate
    ) -> DoctorAdminOut:
        """Sửa hồ sơ, gán lại dịch vụ, khóa hoặc mở khóa tài khoản (UC14).

        Khóa không hủy lịch đã đặt (giống BR-10): bác sĩ biến khỏi trang công khai, không nhận
        lịch mới, còn lịch sắp tới (`upcoming_count`) chờ quản trị đổi sang bác sĩ khác hoặc hủy.
        """
        _require_admin(actor)
        now = self._clock.now()
        changes = data.model_dump(exclude_unset=True)
        async with self._session.begin():
            doctor = await repo.lock_doctor(self._session, doctor_id)
            rows = await repo.list_doctor_accounts(
                self._session, tokens=[], specialty_id=None, doctor_id=doctor_id
            )
            if doctor is None or not rows:
                raise not_found("Không tìm thấy bác sĩ.")
            title = changes.get("title") or doctor.title
            full_name = changes.get("full_name") or _plain_name(rows[0].name, doctor.title)
            specialty_id = changes.get("specialty_id") or doctor.specialty_id
            if specialty_id != doctor.specialty_id and (
                await repo.get_specialty(self._session, specialty_id) is None
            ):
                raise field_error("specialty_id", "Chuyên khoa không tồn tại.")
            assigned = (await repo.all_service_ids_by_doctor(self._session, [doctor_id])).get(
                doctor_id, []
            )
            service_ids: list[int] | None = changes.get("service_ids")
            if service_ids is None and specialty_id != doctor.specialty_id:
                specialties = await repo.service_specialties(self._session, assigned)
                service_ids = [s for s in assigned if specialties.get(s) == specialty_id]
            if service_ids is not None:
                await self._check_services(service_ids, specialty_id)

            doctor.title, doctor.specialty_id = title, specialty_id
            if changes.get("gender") is not None:
                doctor.gender = changes["gender"]
            if "bio" in changes:
                doctor.bio = changes["bio"]
            renamed = changes.get("title") is not None or changes.get("full_name") is not None
            await update_staff_account(
                self._session,
                actor,
                doctor_id,
                full_name=display_name(title, full_name) if renamed else None,
                is_active=changes.get("is_active"),
                now=now,
            )
            if service_ids is not None and service_ids != assigned:
                await repo.replace_doctor_services(self._session, doctor_id, service_ids)
            await self._session.flush()
            result = await self._doctor_admin_out(doctor_id, now)
        log.info(
            "catalog.doctor_updated",
            doctor_id=doctor_id,
            actor_id=actor.user_id,
            is_active=result.is_active,
        )
        return result

    # ------------------------------------------------------------ nội bộ
    async def _check_services(self, service_ids: Sequence[int], specialty_id: int) -> None:
        """Dịch vụ phải có thật và thuộc chuyên khoa của bác sĩ (FR-CAT-03); dịch vụ đang ẩn vẫn
        gán được nhưng chưa ai đặt được cho tới khi hiện lại."""
        specialties = await repo.service_specialties(self._session, service_ids)
        if len(specialties) != len(service_ids):
            raise field_error("service_ids", "Có dịch vụ không tồn tại.")
        if any(value != specialty_id for value in specialties.values()):
            raise field_error("service_ids", "Chỉ gán dịch vụ thuộc chuyên khoa của bác sĩ.")

    async def _doctors_admin_out(
        self, rows: list[repo.DoctorAccountRow], now: datetime
    ) -> list[DoctorAdminOut]:
        ids = [row.doctor.user_id for row in rows]
        services = await repo.all_service_ids_by_doctor(self._session, ids)
        upcoming = await repo.upcoming_counts(self._session, ids, now)
        return [
            _doctor_admin(
                row, services.get(row.doctor.user_id, []), upcoming.get(row.doctor.user_id, 0)
            )
            for row in rows
        ]

    async def _doctor_admin_out(self, doctor_id: int, now: datetime) -> DoctorAdminOut:
        rows = await repo.list_doctor_accounts(
            self._session, tokens=[], specialty_id=None, doctor_id=doctor_id
        )
        return (await self._doctors_admin_out(rows, now))[0]

    async def _flush_specialty(self) -> None:
        """Hai quản trị cùng tạo một tên: UNIQUE chặn, trả lỗi tại ô nhập thay vì lỗi 500."""
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if violated_constraint(exc) == SPECIALTY_NAME_UNIQUE:
                raise _specialty_name_taken() from exc
            raise

    async def _flush_service(self) -> None:
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if violated_constraint(exc) == SERVICE_NAME_UNIQUE:
                raise _service_name_taken() from exc
            raise

    async def _specialty_admin_out(self, specialty_id: int) -> SpecialtyAdminOut:
        rows = await repo.list_specialties(self._session, include_hidden=True)
        return next(_specialty_admin(r) for r in rows if r.specialty.id == specialty_id)

    async def _service_admin_out(self, service_id: int) -> ServiceAdminOut:
        row = await repo.get_service_row(self._session, service_id)
        assert row is not None
        return (await self._services_admin_out([row]))[0]

    async def _services_admin_out(self, rows: list[repo.ServiceRow]) -> list[ServiceAdminOut]:
        ids = [r.service.id for r in rows]
        doctors = await repo.doctors_by_service(self._session, ids)
        counts = await repo.appointment_counts(self._session, ids)
        return [
            ServiceAdminOut(
                **_service_out(row, doctors.get(row.service.id, [])).model_dump(),
                is_active=row.service.is_active,
                appointment_count=counts.get(row.service.id, 0),
            )
            for row in rows
        ]


def _require_admin(actor: Actor) -> None:
    """Phân quyền lớp 2: router đã chặn, service vẫn kiểm tra vì có thể được gọi trực tiếp."""
    if actor.role is not UserRole.ADMIN:
        raise forbidden()


def _specialty_name_taken() -> AppError:
    return field_error("name", "Tên chuyên khoa này đã có.")


def _service_name_taken() -> AppError:
    return field_error("name", "Chuyên khoa này đã có dịch vụ cùng tên.")
