"""Import mọi nhóm model để Alembic thấy đủ metadata."""

from app.db.models import agent, appointments, catalog, schedule, users

__all__ = ["agent", "appointments", "catalog", "schedule", "users"]
