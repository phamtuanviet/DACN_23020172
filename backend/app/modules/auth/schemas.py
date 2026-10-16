"""DTO của module auth (FR-AUTH-01..06).

Thông báo lỗi kiểm tra dữ liệu viết tiếng Việt qua PydanticCustomError, để frontend hiện thẳng
cạnh ô nhập (details.fields của lỗi VALIDATION_ERROR, docs mục 4.7).
"""

import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

from app.db.enums import Gender, UserRole

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^0\d{9}$")
PASSWORD_MIN_LENGTH = 8


def _email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL.match(value):
        raise PydanticCustomError("email", "Email không hợp lệ.")
    return value


def _phone(value: str) -> str:
    """Chấp nhận 0912 345 678, 0912.345.678, +84912345678; lưu dạng 0912345678."""
    digits = re.sub(r"[\s.\-()]", "", value)
    if digits.startswith("+84"):
        digits = "0" + digits[3:]
    if not _PHONE.match(digits):
        raise PydanticCustomError("phone", "Số điện thoại cần 10 chữ số, bắt đầu bằng 0.")
    return digits


def _full_name(value: str) -> str:
    value = " ".join(value.split())
    if len(value) < 2:
        raise PydanticCustomError("full_name", "Họ tên cần ít nhất 2 ký tự.")
    return value


def _password(value: str) -> str:
    """FR-AUTH-01: tối thiểu 8 ký tự, có chữ và số."""
    has_letter = any(ch.isalpha() for ch in value)
    has_digit = any(ch.isdigit() for ch in value)
    if len(value) < PASSWORD_MIN_LENGTH or not (has_letter and has_digit):
        raise PydanticCustomError("password", "Mật khẩu cần tối thiểu 8 ký tự, có cả chữ và số.")
    return value


Email = Annotated[str, Field(max_length=255), AfterValidator(_email)]
Phone = Annotated[str, Field(max_length=20), AfterValidator(_phone)]
FullName = Annotated[str, Field(max_length=100), AfterValidator(_full_name)]
Password = Annotated[str, Field(max_length=128), AfterValidator(_password)]


class RegisterRequest(BaseModel):
    full_name: FullName
    email: Email
    phone: Phone
    date_of_birth: date
    gender: Gender
    password: Password
    privacy_consent: bool = Field(
        description="Phải là true: đồng ý chính sách xử lý dữ liệu cá nhân (docs mục 11.8)"
    )

    @field_validator("privacy_consent")
    @classmethod
    def _consent_required(cls, value: bool) -> bool:
        if value is not True:
            raise PydanticCustomError(
                "consent_required", "Bạn cần đồng ý chính sách xử lý dữ liệu để đăng ký."
            )
        return value


class LoginRequest(BaseModel):
    # Không kiểm tra định dạng email ở đây: mọi trường hợp sai đều trả cùng một thông báo.
    email: Annotated[str, Field(max_length=255)]
    password: Annotated[str, Field(max_length=128)]


class MeResponse(BaseModel):
    id: int
    email: str
    full_name: str
    phone: str | None
    role: UserRole
    date_of_birth: date | None = Field(default=None, description="Chỉ bệnh nhân có")
    gender: Gender | None = Field(default=None, description="Chỉ bệnh nhân có")


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: MeResponse


class UpdateMeRequest(BaseModel):
    """Sửa thông tin cá nhân, trừ email (FR-AUTH-06). Trường bỏ trống là giữ nguyên."""

    full_name: FullName | None = None
    phone: Phone | None = None
    date_of_birth: date | None = None
    gender: Gender | None = None


class ChangePasswordRequest(BaseModel):
    current_password: Annotated[str, Field(max_length=128)]
    new_password: Password
