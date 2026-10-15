"""Mã lịch hẹn LH-YYMMDD-XXXX (FR-APT-01, docs mục 5.6)."""

import secrets
from datetime import date

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # bỏ I, L, O, U để không đọc nhầm


def new_appointment_code(created_on: date) -> str:
    suffix = "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(4))
    return f"LH-{created_on:%y%m%d}-{suffix}"
