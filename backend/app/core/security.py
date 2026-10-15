"""Mật khẩu, JWT, refresh token và dependency phân quyền (docs mục 4.6).

Đã có: băm mật khẩu Argon2id.
Cần làm: tạo/kiểm tra access token (có `kid` để xoay khóa), xoay vòng refresh token,
dependency `current_user` và `require_roles(...)`.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

_hasher = PasswordHasher()  # Argon2id với tham số mặc định của argon2-cffi (TD-08)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False
