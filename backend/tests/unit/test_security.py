from datetime import timedelta

import pytest
from pydantic import SecretStr

from app.core.config import Environment, Settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.db.enums import UserRole
from app.db.models.users import User
from tests.conftest import TEST_NOW

KEY_ONE = "k1:" + "a" * 40
KEY_TWO = "k2:" + "b" * 40


def _settings(keys: str = KEY_ONE) -> Settings:
    return Settings(_env_file=None, app_env=Environment.DEVELOPMENT, jwt_keys=SecretStr(keys))


def _user() -> User:
    return User(id=42, role=UserRole.PATIENT, full_name="Nguyễn Thị Lan")


def test_access_token_round_trip() -> None:
    token, expires_at = create_access_token(_user(), TEST_NOW, _settings())
    claims = decode_access_token(token, TEST_NOW + timedelta(minutes=29), _settings())
    assert claims.user_id == 42
    assert claims.role is UserRole.PATIENT
    assert expires_at == TEST_NOW + timedelta(minutes=30)


def test_access_token_expires_by_application_clock() -> None:
    token, _ = create_access_token(_user(), TEST_NOW, _settings())
    with pytest.raises(AppError) as error:
        decode_access_token(token, TEST_NOW + timedelta(minutes=30), _settings())
    assert error.value.status == 401


def test_old_key_still_accepted_while_rotating() -> None:
    old_token, _ = create_access_token(_user(), TEST_NOW, _settings(KEY_ONE))
    rotated = _settings(f"{KEY_TWO},{KEY_ONE}")
    assert decode_access_token(old_token, TEST_NOW, rotated).user_id == 42
    with pytest.raises(AppError):
        decode_access_token(old_token, TEST_NOW, _settings(KEY_TWO))


def test_tampered_or_garbage_token_rejected() -> None:
    token, _ = create_access_token(_user(), TEST_NOW, _settings())
    for bad in (token[:-2] + "xx", "not-a-jwt", ""):
        with pytest.raises(AppError) as error:
            decode_access_token(bad, TEST_NOW, _settings())
        assert error.value.code == "UNAUTHENTICATED"


def test_refresh_token_is_random_and_stored_as_sha256() -> None:
    first, second = new_refresh_token(), new_refresh_token()
    assert first != second
    assert len(first) >= 43  # 32 byte mã hóa base64url
    assert hash_refresh_token(first) == hash_refresh_token(first)
    assert len(hash_refresh_token(first)) == 64


def test_password_hash_verifies_only_the_right_password() -> None:
    digest = hash_password("matkhau123")
    assert digest.startswith("$argon2id$")
    assert verify_password(digest, "matkhau123")
    assert not verify_password(digest, "matkhau124")
