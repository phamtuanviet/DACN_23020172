"""Ràng buộc dùng chung cho dữ liệu vào, chặn những giá trị đúng kiểu nhưng làm database hoặc phép
tính ngày giờ báo lỗi 500 (lỗi 500 còn sinh event Sentry và traceback không cần thiết).

- Id: cột bigint của PostgreSQL, số lớn hơn 2^63 − 1 làm truy vấn lỗi NumericValueOutOfRange.
- Chuỗi: PostgreSQL không lưu được ký tự NUL (0x00).
- Ngày: giữ trong khoảng hợp lý để phép cộng ngày, đổi múi giờ không tràn năm 1 hay năm 9999.
"""

from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, Field
from pydantic_core import PydanticCustomError

MAX_ID = 2**63 - 1
MIN_DATE = date(2000, 1, 1)
MAX_DATE = date(2100, 12, 31)


def no_nul(value: str) -> str:
    if "\x00" in value:
        raise PydanticCustomError("nul", "Dữ liệu chứa ký tự không hợp lệ.")
    return value


def reasonable_date(value: date) -> date:
    if not MIN_DATE <= value <= MAX_DATE:
        raise PydanticCustomError("date_range", "Ngày nằm ngoài phạm vi cho phép.")
    return value


def reasonable_datetime(value: datetime) -> datetime:
    reasonable_date(value.date())
    return value


DbId = Annotated[int, Field(ge=1, le=MAX_ID)]
SafeText = Annotated[str, AfterValidator(no_nul)]
ReasonableDate = Annotated[date, AfterValidator(reasonable_date)]
