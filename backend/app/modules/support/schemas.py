"""DTO Pydantic vào/ra của module support: kiểu, độ dài, định dạng."""

from datetime import datetime

from pydantic import BaseModel

from app.db.enums import SupportStatus

MAX_SUMMARY_LENGTH = 1000


class SupportRequestOut(BaseModel):
    id: int
    status: SupportStatus
    created_at: datetime
