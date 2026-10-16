from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.modules.auth.schemas import RegisterRequest


def _payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "full_name": "  Nguyễn   Thị Lan ",
        "email": " Lan@Example.COM ",
        "phone": "0912 345 678",
        "date_of_birth": date(1994, 3, 12),
        "gender": "FEMALE",
        "password": "matkhau123",
        "privacy_consent": True,
    }
    data.update(overrides)
    return data


def _messages(error: ValidationError) -> list[str]:
    return [item["msg"] for item in error.errors()]


def test_register_normalizes_name_email_phone() -> None:
    body = RegisterRequest.model_validate(_payload())
    assert body.full_name == "Nguyễn Thị Lan"
    assert body.email == "lan@example.com"
    assert body.phone == "0912345678"


@pytest.mark.parametrize("phone", ["+84912345678", "0912.345.678", "(091) 234-5678"])
def test_phone_accepts_common_vietnamese_formats(phone: str) -> None:
    assert RegisterRequest.model_validate(_payload(phone=phone)).phone.startswith("09")


@pytest.mark.parametrize("phone", ["912345678", "09123", "abc", "+1 555 123 4567"])
def test_phone_rejects_invalid_numbers(phone: str) -> None:
    with pytest.raises(ValidationError) as error:
        RegisterRequest.model_validate(_payload(phone=phone))
    assert _messages(error.value) == ["Số điện thoại cần 10 chữ số, bắt đầu bằng 0."]


@pytest.mark.parametrize("password", ["ngan1", "chicochu", "12345678", "khongcoso!"])
def test_password_needs_eight_chars_with_letters_and_digits(password: str) -> None:
    with pytest.raises(ValidationError) as error:
        RegisterRequest.model_validate(_payload(password=password))
    assert _messages(error.value) == ["Mật khẩu cần tối thiểu 8 ký tự, có cả chữ và số."]


def test_vietnamese_letters_count_as_letters() -> None:
    assert RegisterRequest.model_validate(_payload(password="mậtkhẩu12")).password == "mậtkhẩu12"


def test_privacy_consent_is_required() -> None:
    with pytest.raises(ValidationError) as error:
        RegisterRequest.model_validate(_payload(privacy_consent=False))
    assert _messages(error.value) == ["Bạn cần đồng ý chính sách xử lý dữ liệu để đăng ký."]


def test_invalid_email_rejected_with_vietnamese_message() -> None:
    with pytest.raises(ValidationError) as error:
        RegisterRequest.model_validate(_payload(email="lan.example.com"))
    assert _messages(error.value) == ["Email không hợp lệ."]
