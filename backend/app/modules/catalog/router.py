"""HTTP của module catalog: khai báo endpoint, nhận DTO, tạo Actor, gọi service.

Không chứa nghiệp vụ, không truy vấn database (docs mục 4.2). Đọc công khai không cần đăng nhập;
mọi endpoint `/admin/*` cần vai trò ADMIN.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.db import SessionDep
from app.core.security import AdminActorDep, ClockDep
from app.core.validation import MAX_ID, SafeText
from app.modules.catalog.schemas import (
    DoctorDetail,
    DoctorOut,
    ServiceAdminOut,
    ServiceCreate,
    ServiceOut,
    ServiceUpdate,
    SpecialtyAdminOut,
    SpecialtyCreate,
    SpecialtyOut,
    SpecialtyUpdate,
)
from app.modules.catalog.service import CatalogService


def get_catalog_service(session: SessionDep, clock: ClockDep) -> CatalogService:
    return CatalogService(session, clock)


CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
SearchQuery = Annotated[
    SafeText | None, Query(max_length=100, description="Từ khóa, có dấu hoặc không dấu")
]
IdQuery = Annotated[int | None, Query(ge=1, le=MAX_ID)]
IdPath = Annotated[int, Path(ge=1, le=MAX_ID)]

public_router = APIRouter(tags=["catalog"])
admin_router = APIRouter(prefix="/admin", tags=["admin-catalog"])


# ---------------------------------------------------------------------------- công khai
@public_router.get("/specialties")
async def list_specialties(service: CatalogServiceDep) -> list[SpecialtyOut]:
    """Chuyên khoa đang hoạt động, kèm số dịch vụ, số bác sĩ, giá thấp nhất."""
    return await service.list_specialties()


@public_router.get("/services")
async def search_services(
    service: CatalogServiceDep, q: SearchQuery = None, specialty_id: IdQuery = None
) -> list[ServiceOut]:
    """Tìm dịch vụ theo tên, chuyên khoa, phạm vi khám; gõ có dấu hay không dấu (FR-CAT-04)."""
    return await service.search_services(q, specialty_id)


@public_router.get("/doctors")
async def search_doctors(
    service: CatalogServiceDep,
    q: SearchQuery = None,
    specialty_id: IdQuery = None,
    service_id: IdQuery = None,
) -> list[DoctorOut]:
    """Tìm bác sĩ theo tên hoặc chuyên khoa; lọc theo chuyên khoa, dịch vụ (FR-CAT-04)."""
    return await service.search_doctors(q, specialty_id, service_id)


@public_router.get("/doctors/{doctor_id}")
async def get_doctor(doctor_id: IdPath, service: CatalogServiceDep) -> DoctorDetail:
    """Hồ sơ bác sĩ: dịch vụ thực hiện, lịch làm việc trong tuần (UC03)."""
    return await service.get_doctor(doctor_id)


# ---------------------------------------------------------------------------- quản trị
@admin_router.get("/specialties")
async def admin_list_specialties(
    actor: AdminActorDep, service: CatalogServiceDep
) -> list[SpecialtyAdminOut]:
    return await service.admin_list_specialties(actor)


@admin_router.post("/specialties", status_code=status.HTTP_201_CREATED)
async def create_specialty(
    body: SpecialtyCreate, actor: AdminActorDep, service: CatalogServiceDep
) -> SpecialtyAdminOut:
    """Thêm chuyên khoa (FR-CAT-01)."""
    return await service.create_specialty(actor, body)


@admin_router.patch("/specialties/{specialty_id}")
async def update_specialty(
    specialty_id: IdPath, body: SpecialtyUpdate, actor: AdminActorDep, service: CatalogServiceDep
) -> SpecialtyAdminOut:
    """Sửa hoặc ẩn chuyên khoa; không có xóa cứng (FR-CAT-05)."""
    return await service.update_specialty(actor, specialty_id, body)


@admin_router.get("/services")
async def admin_list_services(
    actor: AdminActorDep,
    service: CatalogServiceDep,
    q: SearchQuery = None,
    specialty_id: IdQuery = None,
) -> list[ServiceAdminOut]:
    """Mọi dịch vụ kể cả đã ẩn, kèm số lịch hẹn đã có."""
    return await service.admin_list_services(actor, q, specialty_id)


@admin_router.post("/services", status_code=status.HTTP_201_CREATED)
async def create_service(
    body: ServiceCreate, actor: AdminActorDep, service: CatalogServiceDep
) -> ServiceAdminOut:
    """Thêm dịch vụ: thời lượng 10–120 phút, bội số 5 (FR-CAT-02)."""
    return await service.create_service(actor, body)


@admin_router.patch("/services/{service_id}")
async def update_service(
    service_id: IdPath, body: ServiceUpdate, actor: AdminActorDep, service: CatalogServiceDep
) -> ServiceAdminOut:
    """Sửa hoặc ẩn dịch vụ; dịch vụ đã có lịch hẹn chỉ ẩn được, không xóa (FR-CAT-05)."""
    return await service.update_service(actor, service_id, body)


router = APIRouter()
router.include_router(public_router)
router.include_router(admin_router)
