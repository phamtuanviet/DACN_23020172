"""Router gốc /api/v1: nơi duy nhất ghép router của các module."""

from fastapi import APIRouter

from app.api import health
from app.modules.agent.router import router as agent_router
from app.modules.appointments.router import router as appointments_router
from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import router as catalog_router
from app.modules.reports.router import router as reports_router
from app.modules.schedule.router import router as schedule_router
from app.modules.scheduling.router import router as scheduling_router
from app.modules.support.router import router as support_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
for module_router in (
    auth_router,
    catalog_router,
    scheduling_router,
    appointments_router,
    schedule_router,
    agent_router,
    support_router,
    reports_router,
):
    api_router.include_router(module_router)
