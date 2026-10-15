"""Enum dùng chung, khớp các kiểu ENUM của PostgreSQL ở ERD mục 4."""

from enum import StrEnum


class UserRole(StrEnum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class AppointmentStatus(StrEnum):
    BOOKED = "BOOKED"
    ARRIVED = "ARRIVED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class Channel(StrEnum):
    WEB = "WEB"
    AGENT = "AGENT"
    ADMIN = "ADMIN"
    SYSTEM = "SYSTEM"


class HistoryAction(StrEnum):
    CREATE = "CREATE"
    RESCHEDULE = "RESCHEDULE"
    CANCEL = "CANCEL"
    STATUS_CHANGE = "STATUS_CHANGE"
    NOTE_UPDATE = "NOTE_UPDATE"
    FLAG = "FLAG"


class NotificationType(StrEnum):
    BOOKED = "BOOKED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"
    REMINDER = "REMINDER"


class NotificationStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class MessageRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"


class ProposalType(StrEnum):
    BOOK = "BOOK"
    RESCHEDULE = "RESCHEDULE"
    CANCEL = "CANCEL"


class ProposalStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class SupportStatus(StrEnum):
    OPEN = "OPEN"
    DONE = "DONE"
