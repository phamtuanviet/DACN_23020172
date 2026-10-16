"""Dữ liệu giả cho development/staging (docs mục 7.5). Bị chặn khi APP_ENV=production.

Tên bác sĩ, dịch vụ, giá khớp với thiết kế giao diện để demo nhất quán. Mọi mốc thời gian tính
tương đối so với ngày chạy seed; dữ liệu ngẫu nhiên dùng seed cố định nên chạy lại ra kết quả như
cũ. Lịch hẹn mẫu sẽ được thêm khi có AppointmentService (Sprint 2–3), để đi qua đúng mọi quy tắc.
"""

import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.security import hash_password_async
from app.core.timeutil import local_datetime, to_local
from app.db.enums import Gender, UserRole
from app.db.models.catalog import DoctorService, Service, Specialty
from app.db.models.schedule import Shift, TimeOff
from app.db.models.users import Doctor, PatientProfile, User

# Mật khẩu chung của tài khoản @demo.local CHỈ ở development. Staging công khai trên Internet nên
# lệnh seed hỏi mật khẩu khi chạy, không dùng giá trị nằm trong repo (gồm cả tài khoản quản trị).
DEMO_PASSWORD = "Demo12345"
RANDOM_SEED = 20261010

SPECIALTIES: list[tuple[str, str]] = [
    ("Nội tổng quát", "Sức khỏe chung của người lớn: sốt, ho, đau đầu, huyết áp, khám định kỳ."),
    ("Da liễu", "Bệnh về da, tóc, móng: mụn, dị ứng, viêm da, nấm da."),
    ("Nhi", "Trẻ dưới 16 tuổi: sốt, ho, tiêu hóa, dinh dưỡng, tư vấn tiêm chủng."),
    ("Tai Mũi Họng", "Viêm họng, viêm xoang, nghẹt mũi, ù tai."),
    ("Răng Hàm Mặt", "Khám răng, cạo vôi, trám răng sâu."),
    ("Mắt", "Đo thị lực, khô mắt, đỏ mắt, mỏi mắt."),
]


@dataclass(frozen=True)
class ServiceSeed:
    specialty: str
    name: str
    scope: str
    duration_min: int
    price_vnd: int
    is_active: bool = True


SERVICES: list[ServiceSeed] = [
    ServiceSeed(
        "Nội tổng quát",
        "Khám nội tổng quát",
        "Triệu chứng thường gặp ở người lớn: sốt, ho, đau đầu, mệt mỏi, đau bụng, tăng huyết áp. "
        "Không gồm cấp cứu và nội soi.",
        20,
        200_000,
    ),
    ServiceSeed(
        "Nội tổng quát",
        "Khám sức khỏe định kỳ",
        "Đo huyết áp, chỉ số cơ thể, khám tổng quát và tư vấn lối sống. "
        "Xét nghiệm do bác sĩ chỉ định khi cần, tính phí riêng.",
        45,
        650_000,
    ),
    ServiceSeed(
        "Nội tổng quát",
        "Tư vấn tăng huyết áp",
        "Theo dõi huyết áp, điều chỉnh thuốc và chế độ sinh hoạt cho người đã được chẩn đoán.",
        20,
        220_000,
    ),
    ServiceSeed(
        "Nội tổng quát",
        "Tư vấn tiểu đường",
        "Theo dõi đường huyết, điều chỉnh điều trị, tư vấn ăn uống cho người đã được chẩn đoán.",
        30,
        250_000,
    ),
    ServiceSeed(
        "Da liễu",
        "Khám da liễu tổng quát",
        "Các vấn đề về da, tóc, móng: nổi mẩn, ngứa, dị ứng da, mụn, nấm da. "
        "Không gồm thủ thuật thẩm mỹ, laser.",
        20,
        250_000,
    ),
    ServiceSeed(
        "Da liễu",
        "Tư vấn trị mụn",
        "Mụn trứng cá, mụn viêm, thâm sau mụn; lên phác đồ chăm sóc da.",
        30,
        300_000,
    ),
    ServiceSeed(
        "Da liễu",
        "Khám viêm da cơ địa",
        "Chàm, viêm da cơ địa tái phát, da khô ngứa kéo dài.",
        20,
        250_000,
    ),
    ServiceSeed(
        "Da liễu",
        "Laser trị nám",
        "Điều trị nám, tàn nhang bằng laser theo liệu trình.",
        45,
        1_200_000,
        is_active=False,  # đã ẩn: minh họa dịch vụ chỉ ẩn được, không xóa (FR-CAT-05)
    ),
    ServiceSeed(
        "Nhi",
        "Khám nhi tổng quát",
        "Trẻ dưới 16 tuổi: sốt, ho, sổ mũi, tiêu chảy, phát ban; theo dõi tăng trưởng.",
        20,
        220_000,
    ),
    ServiceSeed(
        "Nhi",
        "Tư vấn dinh dưỡng trẻ em",
        "Trẻ biếng ăn, chậm tăng cân, thừa cân; xây dựng chế độ ăn theo độ tuổi.",
        30,
        250_000,
    ),
    ServiceSeed(
        "Nhi",
        "Tư vấn tiêm chủng",
        "Tư vấn lịch tiêm chủng theo độ tuổi và tiền sử của trẻ. Không gồm tiêm vắc xin.",
        15,
        220_000,
    ),
    ServiceSeed(
        "Tai Mũi Họng",
        "Khám tai mũi họng",
        "Đau họng, viêm họng, nghẹt mũi, viêm xoang, ù tai, đau tai.",
        15,
        200_000,
    ),
    ServiceSeed(
        "Tai Mũi Họng",
        "Nội soi tai mũi họng",
        "Nội soi kiểm tra tai, mũi, họng khi cần quan sát kỹ hơn khám thông thường.",
        30,
        350_000,
    ),
    ServiceSeed(
        "Tai Mũi Họng",
        "Lấy ráy tai",
        "Lấy ráy tai cứng, ráy tai gây ù tai hoặc nghe kém.",
        15,
        200_000,
    ),
    ServiceSeed(
        "Răng Hàm Mặt",
        "Khám răng tổng quát",
        "Kiểm tra răng, nướu, khớp cắn; tư vấn điều trị.",
        20,
        150_000,
    ),
    ServiceSeed(
        "Răng Hàm Mặt",
        "Cạo vôi răng",
        "Làm sạch vôi răng, mảng bám; đánh bóng răng.",
        30,
        300_000,
    ),
    ServiceSeed(
        "Răng Hàm Mặt",
        "Trám răng sâu",
        "Trám răng sâu mức độ nhẹ và vừa. Không gồm điều trị tủy.",
        45,
        400_000,
    ),
    ServiceSeed(
        "Mắt",
        "Khám mắt tổng quát",
        "Đo thị lực, khám đỏ mắt, khô mắt, mỏi mắt.",
        20,
        180_000,
    ),
    ServiceSeed(
        "Mắt",
        "Đo khúc xạ",
        "Đo cận, viễn, loạn thị; tư vấn độ kính.",
        20,
        180_000,
    ),
    ServiceSeed(
        "Mắt",
        "Khám khô mắt",
        "Khô mắt, cộm mắt, mỏi mắt khi dùng máy tính lâu.",
        20,
        220_000,
    ),
]


@dataclass(frozen=True)
class DoctorSeed:
    email: str
    title: str
    name: str
    gender: Gender
    specialty: str
    years: int
    services: tuple[str, ...] | None = None  # None = mọi dịch vụ đang hoạt động của chuyên khoa
    is_active: bool = True


M, F = Gender.MALE, Gender.FEMALE
DOCTORS: list[DoctorSeed] = [
    DoctorSeed(
        "minh.tran@demo.local",
        "ThS. BS.",
        "Trần Minh",
        M,
        "Da liễu",
        10,
        ("Khám da liễu tổng quát", "Khám viêm da cơ địa"),
    ),
    DoctorSeed(
        "ha.nguyen@demo.local",
        "BS.CKI",
        "Nguyễn Thu Hà",
        F,
        "Da liễu",
        12,
        ("Khám da liễu tổng quát", "Tư vấn trị mụn", "Khám viêm da cơ địa", "Laser trị nám"),
    ),
    DoctorSeed(
        "bao.le@demo.local",
        "BS.",
        "Lê Quốc Bảo",
        M,
        "Da liễu",
        4,
        ("Khám da liễu tổng quát", "Tư vấn trị mụn"),
    ),
    DoctorSeed("nam.pham@demo.local", "BS.", "Phạm Hoàng Nam", M, "Nội tổng quát", 8),
    DoctorSeed("mai.hoang@demo.local", "BS.CKII", "Hoàng Thị Mai", F, "Nội tổng quát", 20),
    DoctorSeed("tung.ngo@demo.local", "ThS. BS.", "Ngô Văn Tùng", M, "Nội tổng quát", 11),
    DoctorSeed("huong.bui@demo.local", "BS.", "Bùi Thanh Hương", F, "Nội tổng quát", 6),
    DoctorSeed("anh.dang@demo.local", "BS.", "Đặng Mai Anh", F, "Nhi", 7),
    DoctorSeed("trang.trinh@demo.local", "BS.CKI", "Trịnh Thu Trang", F, "Nhi", 13),
    DoctorSeed("huy.ly@demo.local", "ThS. BS.", "Lý Gia Huy", M, "Nhi", 9),
    DoctorSeed("diep.phan@demo.local", "BS.", "Phan Ngọc Diệp", F, "Nhi", 5),
    DoctorSeed("long.vo@demo.local", "BS.CKI", "Võ Thành Long", M, "Tai Mũi Họng", 14),
    DoctorSeed("hanh.dinh@demo.local", "BS.", "Đinh Thị Hạnh", F, "Tai Mũi Họng", 6),
    DoctorSeed("phuc.mai@demo.local", "ThS. BS.", "Mai Xuân Phúc", M, "Tai Mũi Họng", 10),
    DoctorSeed("khoa.cao@demo.local", "BS.", "Cao Minh Khoa", M, "Răng Hàm Mặt", 7),
    DoctorSeed("uyen.ta@demo.local", "BS.CKI", "Tạ Thu Uyên", F, "Răng Hàm Mặt", 12),
    DoctorSeed("ducanh.ha@demo.local", "BS.", "Hà Đức Anh", M, "Răng Hàm Mặt", 4),
    DoctorSeed("thinh.vu@demo.local", "BS.", "Vũ Đức Thịnh", M, "Mắt", 9),
    DoctorSeed(
        "linh.doan@demo.local", "BS.", "Đoàn Khánh Linh", F, "Mắt", 3, is_active=False
    ),  # tài khoản đã khóa, để demo màn quản trị
    DoctorSeed("ngoc.lam@demo.local", "BS.CKI", "Lâm Bảo Ngọc", F, "Mắt", 15),
]

ADMINS: list[tuple[str, str]] = [
    ("admin@demo.local", "Trần Thị Hà"),
    ("admin2@demo.local", "Phạm Quốc Việt"),
]

DEMO_PATIENT = ("lan@demo.local", "Nguyễn Thị Lan", "0912345678", date(1994, 3, 12), F)
PATIENT_COUNT = 50
FAMILY_NAMES = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ", "Ngô"]
MIDDLE_NAMES = {M: ["Văn", "Đức", "Minh", "Quốc", "Hữu"], F: ["Thị", "Ngọc", "Thu", "Thanh", "Mai"]}
GIVEN_NAMES = {
    M: ["Hùng", "Dũng", "Tuấn", "Khang", "Phong", "Quân", "Sơn", "Thắng", "Long", "Hải"],
    F: ["Lan", "Hoa", "Hương", "Linh", "Trang", "Thảo", "Yến", "Nhung", "Vy", "Hằng"],
}

MORNING = (time(8, 0), time(11, 30))
AFTERNOON = (time(13, 30), time(17, 0))


async def seed_database(
    session: AsyncSession, clock: Clock, password: str = DEMO_PASSWORD
) -> dict[str, int]:
    """Nạp dữ liệu mẫu vào database trống. Đã có dữ liệu thì từ chối, không ghi đè."""
    async with session.begin():
        existing = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        if existing:
            raise RuntimeError("Database đã có dữ liệu; seed chỉ chạy trên database trống.")

        now = clock.now()
        today = to_local(now).date()
        rng = random.Random(RANDOM_SEED)
        password_hash = await hash_password_async(password)

        specialties = {name: Specialty(name=name, description=desc) for name, desc in SPECIALTIES}
        session.add_all(specialties.values())
        await session.flush()

        services: dict[str, Service] = {}
        for item in SERVICES:
            services[item.name] = Service(
                specialty_id=specialties[item.specialty].id,
                name=item.name,
                scope_description=item.scope,
                duration_min=item.duration_min,
                ref_price_vnd=item.price_vnd,
                is_active=item.is_active,
            )
        session.add_all(services.values())

        admins = [
            User(email=email, password_hash=password_hash, role=UserRole.ADMIN, full_name=name)
            for email, name in ADMINS
        ]
        session.add_all(admins)
        await session.flush()

        doctor_ids = await _seed_doctors(session, specialties, services, password_hash, rng)
        shift_count = _seed_shifts(session, doctor_ids, today)
        time_off_count = _seed_time_offs(session, doctor_ids, today, created_by=admins[0].id)
        patient_count = await _seed_patients(session, password_hash, rng, now)

    return {
        "chuyên khoa": len(specialties),
        "dịch vụ": len(services),
        "bác sĩ": len(doctor_ids),
        "ca làm": shift_count,
        "ngày nghỉ": time_off_count,
        "bệnh nhân": patient_count,
        "quản trị": len(admins),
    }


async def _seed_doctors(
    session: AsyncSession,
    specialties: dict[str, Specialty],
    services: dict[str, Service],
    password_hash: str,
    rng: random.Random,
) -> list[int]:
    doctor_ids: list[int] = []
    for item in DOCTORS:
        user = User(
            email=item.email,
            password_hash=password_hash,
            role=UserRole.DOCTOR,
            full_name=f"{item.title} {item.name}",
            phone=_phone(rng),
            is_active=item.is_active,
        )
        session.add(user)
        await session.flush()
        bio = f"{item.years} năm kinh nghiệm khám và điều trị chuyên khoa {item.specialty.lower()}."
        session.add(
            Doctor(
                user_id=user.id,
                specialty_id=specialties[item.specialty].id,
                title=item.title,
                bio=bio,
                gender=item.gender,
            )
        )
        # Model không khai báo relationship nên phải ghi bác sĩ trước khi gán dịch vụ.
        await session.flush()
        names = item.services or tuple(
            s.name for s in SERVICES if s.specialty == item.specialty and s.is_active
        )
        session.add_all(
            DoctorService(doctor_id=user.id, service_id=services[name].id) for name in names
        )
        doctor_ids.append(user.id)
    await session.flush()
    return doctor_ids


def _seed_shifts(session: AsyncSession, doctor_ids: list[int], today: date) -> int:
    """Ca làm hiệu lực từ 2 tuần trước tới 6 tuần sau (docs mục 7.5).

    Bác sĩ chẵn: thứ Hai–Sáu cả ngày; bác sĩ lẻ: thứ Ba, thứ Năm chỉ buổi sáng. Ai cũng làm
    sáng thứ Bảy, giống giờ mở cửa trên trang chủ.
    """
    valid_from, valid_to = today - timedelta(days=14), today + timedelta(days=42)
    count = 0
    for index, doctor_id in enumerate(doctor_ids):
        for weekday in range(1, 7):
            blocks = [MORNING]
            if weekday <= 5 and (index % 2 == 0 or weekday in (1, 3, 5)):
                blocks.append(AFTERNOON)
            for start, end in blocks:
                session.add(
                    Shift(
                        doctor_id=doctor_id,
                        weekday=weekday,
                        start_time=start,
                        end_time=end,
                        valid_from=valid_from,
                        valid_to=valid_to,
                    )
                )
                count += 1
    return count


def _seed_time_offs(
    session: AsyncSession, doctor_ids: list[int], today: date, *, created_by: int
) -> int:
    """Vài ngày nghỉ: một ngày đã qua, phần còn lại trong 3 tuần tới (có cả nửa ngày)."""

    def next_weekday(weekday: int, weeks_ahead: int) -> date:
        days = (weekday - today.isoweekday()) % 7 or 7
        return today + timedelta(days=days + 7 * weeks_ahead)

    # (vị trí bác sĩ trong DOCTORS, ngày, từ giờ, đến giờ, lý do)
    plans: list[tuple[int, date, time, time, str]] = [
        (2, next_weekday(3, 0), time(0, 0), time(23, 59), "Nghỉ phép"),  # BS. Lê Quốc Bảo
        (0, next_weekday(5, 1), time(13, 0), time(17, 0), "Hội thảo chuyên môn"),
        (3, next_weekday(2, 0), time(8, 0), time(12, 0), "Công tác"),
        (7, next_weekday(4, 1), time(0, 0), time(23, 59), "Nghỉ phép"),
        (11, next_weekday(1, 2), time(0, 0), time(23, 59), "Nghỉ phép"),
        (14, next_weekday(6, 0), time(8, 0), time(12, 0), "Việc gia đình"),
        (17, next_weekday(3, 2), time(13, 0), time(17, 0), "Hội thảo chuyên môn"),
        (5, today - timedelta(days=5), time(0, 0), time(23, 59), "Nghỉ ốm"),
    ]
    for position, day, start, end, reason in plans:
        session.add(
            TimeOff(
                doctor_id=doctor_ids[position],
                start_at=local_datetime(day, start),
                end_at=local_datetime(day, end),
                reason=reason,
                created_by=created_by,
            )
        )
    return len(plans)


async def _seed_patients(
    session: AsyncSession, password_hash: str, rng: random.Random, now: datetime
) -> int:
    email, name, phone, birthday, gender = DEMO_PATIENT
    rows: list[tuple[str, str, str, date, Gender]] = [(email, name, phone, birthday, gender)]
    for number in range(1, PATIENT_COUNT):
        gender = rng.choice([M, F])
        full_name = " ".join(
            [
                rng.choice(FAMILY_NAMES),
                rng.choice(MIDDLE_NAMES[gender]),
                rng.choice(GIVEN_NAMES[gender]),
            ]
        )
        birthday = date(rng.randint(1950, 2018), rng.randint(1, 12), rng.randint(1, 28))
        rows.append((f"benhnhan{number:02d}@demo.local", full_name, _phone(rng), birthday, gender))

    for email, full_name, phone, birthday, gender in rows:
        user = User(
            email=email,
            password_hash=password_hash,
            role=UserRole.PATIENT,
            full_name=full_name,
            phone=phone,
            privacy_consent_at=now,
        )
        session.add(user)
        await session.flush()
        session.add(PatientProfile(user_id=user.id, date_of_birth=birthday, gender=gender))
    return len(rows)


def _phone(rng: random.Random) -> str:
    return rng.choice(["090", "091", "093", "097", "098"]) + f"{rng.randint(0, 9_999_999):07d}"
