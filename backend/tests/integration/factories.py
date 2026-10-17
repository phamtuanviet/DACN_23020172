"""Dựng dữ liệu giả cho test tích hợp: một chuyên khoa, dịch vụ, bác sĩ có ca làm, bệnh nhân.

Access token tạo thẳng bằng `create_access_token` (cùng khóa với app trong test), không qua
/auth/login, vì đăng nhập bị giới hạn 10 lần/phút/IP.
"""

from dataclasses import dataclass, field
from datetime import date, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Environment, Settings
from app.core.security import create_access_token
from app.core.timeutil import local_datetime
from app.db.enums import AppointmentStatus, Channel, Gender, UserRole
from app.db.models.appointments import Appointment
from app.db.models.catalog import DoctorService, Service, Specialty
from app.db.models.schedule import Shift, TimeOff
from app.db.models.users import Doctor, PatientProfile, User
from tests.conftest import TEST_NOW

MONDAY = date(2026, 10, 12)  # TEST_NOW là Thứ Bảy 10/10/2026 09:00
SHIFT_START, SHIFT_END = time(8, 0), time(11, 30)
APP_SETTINGS = Settings(_env_file=None, app_env=Environment.DEVELOPMENT)


@dataclass
class Clinic:
    specialty_id: int
    service_id: int  # Khám da liễu tổng quát, 20 phút
    acne_service_id: int  # Tư vấn trị mụn, 30 phút
    doctor_ids: list[int]
    patient_ids: list[int]
    admin_id: int
    emails: dict[int, str] = field(default_factory=dict)


def bearer(user_id: int, role: UserRole) -> dict[str, str]:
    user = User(id=user_id, role=role)
    token, _ = create_access_token(user, TEST_NOW, APP_SETTINGS)
    return {"Authorization": f"Bearer {token}"}


def at(day: date, hour: int, minute: int = 0) -> str:
    return local_datetime(day, time(hour, minute)).isoformat()


async def build_clinic(db: AsyncSession, *, doctors: int = 2, patients: int = 2) -> Clinic:
    """Mỗi bác sĩ làm Thứ Hai–Thứ Bảy 08:00–11:30, hiệu lực từ 01/10/2026, làm cả hai dịch vụ."""
    async with db.begin():
        specialty = Specialty(name="Da liễu", description="Bệnh về da, tóc, móng.")
        db.add(specialty)
        await db.flush()
        general = Service(
            specialty_id=specialty.id,
            name="Khám da liễu tổng quát",
            scope_description="Các vấn đề về da, tóc, móng: nổi mẩn, ngứa, dị ứng da.",
            duration_min=20,
            ref_price_vnd=250_000,
        )
        acne = Service(
            specialty_id=specialty.id,
            name="Tư vấn trị mụn",
            scope_description="Mụn trứng cá, mụn viêm, thâm sau mụn.",
            duration_min=30,
            ref_price_vnd=300_000,
        )
        admin = User(
            email="quantri@example.com",
            password_hash="x",
            role=UserRole.ADMIN,
            full_name="Quản trị",
        )
        db.add_all([general, acne, admin])
        await db.flush()

        doctor_ids: list[int] = []
        for i in range(doctors):
            user = User(
                email=f"bacsi{i}@example.com",
                password_hash="x",
                role=UserRole.DOCTOR,
                full_name=f"BS. Bác Sĩ {i}",
            )
            db.add(user)
            await db.flush()
            db.add(
                Doctor(user_id=user.id, specialty_id=specialty.id, title="BS.", gender=Gender.MALE)
            )
            await db.flush()
            db.add_all(
                [
                    DoctorService(doctor_id=user.id, service_id=general.id),
                    DoctorService(doctor_id=user.id, service_id=acne.id),
                ]
            )
            db.add_all(
                Shift(
                    doctor_id=user.id,
                    weekday=weekday,
                    start_time=SHIFT_START,
                    end_time=SHIFT_END,
                    valid_from=date(2026, 10, 1),
                )
                for weekday in range(1, 7)
            )
            doctor_ids.append(user.id)

        patient_ids: list[int] = []
        emails: dict[int, str] = {}
        for i in range(patients):
            user = User(
                email=f"benhnhan{i}@example.com",
                password_hash="x",
                role=UserRole.PATIENT,
                full_name=f"Bệnh Nhân {i}",
            )
            db.add(user)
            await db.flush()
            db.add(
                PatientProfile(
                    user_id=user.id, date_of_birth=date(1990, 1, 1), gender=Gender.FEMALE
                )
            )
            patient_ids.append(user.id)
            emails[user.id] = user.email
        await db.flush()
        return Clinic(specialty.id, general.id, acne.id, doctor_ids, patient_ids, admin.id, emails)


async def add_appointment(
    db: AsyncSession,
    clinic: Clinic,
    *,
    doctor_index: int = 0,
    patient_index: int = 0,
    day: date = MONDAY,
    start: time,
    minutes: int = 20,
    status: AppointmentStatus = AppointmentStatus.BOOKED,
    code: str | None = None,
) -> int:
    """Ghi thẳng một lịch hẹn (bỏ qua service) để dựng tình huống cho test."""
    start_at = local_datetime(day, start)
    async with db.begin():
        appointment = Appointment(
            code=code or f"LH-TEST-{start:%H%M}{doctor_index}{patient_index}",
            patient_id=clinic.patient_ids[patient_index],
            doctor_id=clinic.doctor_ids[doctor_index],
            service_id=clinic.service_id,
            start_at=start_at,
            end_at=start_at + timedelta(minutes=minutes),
            status=status,
            channel=Channel.WEB,
        )
        db.add(appointment)
        await db.flush()
        return appointment.id


async def add_time_off(
    db: AsyncSession, clinic: Clinic, *, doctor_index: int = 0, day: date, start: time, end: time
) -> None:
    async with db.begin():
        db.add(
            TimeOff(
                doctor_id=clinic.doctor_ids[doctor_index],
                start_at=local_datetime(day, start),
                end_at=local_datetime(day, end),
                reason="Nghỉ phép",
            )
        )
