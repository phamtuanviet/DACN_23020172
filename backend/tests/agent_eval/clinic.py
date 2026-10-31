"""Phòng khám dựng sẵn cho bộ kịch bản: 3 chuyên khoa, 4 bác sĩ, 2 bệnh nhân giả.

Bác sĩ làm Thứ Hai–Thứ Bảy 08:00–11:30, Thứ Hai–Thứ Sáu thêm 13:30–17:00; Chủ nhật nghỉ.
Kịch bản tham chiếu bằng khóa (`@derm`, `@derm_minh`, `@lan`…), id thật gán lúc chạy.
"""

from datetime import date, time

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import Gender, UserRole
from app.db.models.catalog import DoctorService, Service, Specialty
from app.db.models.schedule import Shift
from app.db.models.users import Doctor, PatientProfile, User

CATALOG = {
    "Da liễu": [
        (
            "derm",
            "Khám da liễu tổng quát",
            "Các vấn đề về da, tóc, móng: nổi mẩn, ngứa, dị ứng da, mụn, nấm da.",
            20,
        ),
        ("acne", "Tư vấn trị mụn", "Mụn trứng cá, mụn viêm, thâm sau mụn.", 30),
    ],
    "Tai Mũi Họng": [
        ("ent", "Khám tai mũi họng", "Đau họng, viêm họng, nghẹt mũi, ù tai, viêm xoang.", 15),
    ],
    "Nội tổng quát": [
        (
            "internal",
            "Khám nội tổng quát",
            "Triệu chứng thường gặp ở người lớn: sốt, ho, đau đầu, mệt mỏi, đau bụng.",
            20,
        ),
    ],
}
DOCTORS = [  # khóa, họ tên, học hàm, chuyên khoa, dịch vụ
    ("derm_minh", "Trần Minh", "ThS. BS.", "Da liễu", ["derm", "acne"]),
    ("derm_ha", "Nguyễn Thu Hà", "BS.CKI", "Da liễu", ["derm", "acne"]),
    ("ent_tuan", "Lê Anh Tuấn", "BS.", "Tai Mũi Họng", ["ent"]),
    ("internal_nam", "Phạm Hoàng Nam", "BS.", "Nội tổng quát", ["internal"]),
]
PATIENTS = [("lan", "Nguyễn Thị Lan"), ("other", "Trần Văn Bình")]


async def build_eval_clinic(db: AsyncSession) -> dict[str, int]:
    """Trả bảng khóa → id dùng để thay các tham chiếu `@khóa` trong kịch bản."""
    ids: dict[str, int] = {}
    async with db.begin():
        specialties: dict[str, int] = {}
        for name, services in CATALOG.items():
            specialty = Specialty(name=name, description=name)
            db.add(specialty)
            await db.flush()
            specialties[name] = specialty.id
            for key, service_name, scope, minutes in services:
                service = Service(
                    specialty_id=specialty.id,
                    name=service_name,
                    scope_description=scope,
                    duration_min=minutes,
                    ref_price_vnd=250_000,
                )
                db.add(service)
                await db.flush()
                ids[key] = service.id
        for key, full_name, title, specialty_name, services in DOCTORS:
            user = User(
                email=f"{key}@example.com",
                password_hash="x",
                role=UserRole.DOCTOR,
                full_name=f"{title} {full_name}",
            )
            db.add(user)
            await db.flush()
            db.add(
                Doctor(
                    user_id=user.id,
                    specialty_id=specialties[specialty_name],
                    title=title,
                    gender=Gender.FEMALE,
                )
            )
            await db.flush()
            db.add_all(DoctorService(doctor_id=user.id, service_id=ids[s]) for s in services)
            for weekday in range(1, 7):
                db.add(
                    Shift(
                        doctor_id=user.id,
                        weekday=weekday,
                        start_time=time(8, 0),
                        end_time=time(11, 30),
                        valid_from=date(2026, 1, 1),
                    )
                )
                if weekday <= 5:
                    db.add(
                        Shift(
                            doctor_id=user.id,
                            weekday=weekday,
                            start_time=time(13, 30),
                            end_time=time(17, 0),
                            valid_from=date(2026, 1, 1),
                        )
                    )
            ids[key] = user.id
        for key, full_name in PATIENTS:
            user = User(
                email=f"{key}@example.com",
                password_hash="x",
                role=UserRole.PATIENT,
                full_name=full_name,
                phone="0912345678",
            )
            db.add(user)
            await db.flush()
            db.add(
                PatientProfile(
                    user_id=user.id, date_of_birth=date(1990, 5, 1), gender=Gender.FEMALE
                )
            )
            ids[key] = user.id
    return ids
