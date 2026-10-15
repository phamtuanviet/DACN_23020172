"""Tiến trình tác vụ nền (docs mục 10.5). Chạy: python -m app.worker

Mọi job đều idempotent; job quét giữ advisory lock nên chạy nhiều replica worker vẫn an toàn.
"""

import asyncio
import signal

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.observability import init_sentry
from app.modules.agent.jobs import expire_proposals, purge_old_conversations
from app.modules.auth.jobs import purge_expired_tokens
from app.modules.notifications.jobs import enqueue_reminders, send_notifications

log = structlog.get_logger("worker")


def build_scheduler(timezone: str) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(
        timezone=timezone, job_defaults={"coalesce": True, "max_instances": 1}
    )
    scheduler.add_job(send_notifications, IntervalTrigger(seconds=30), id="send_notifications")
    scheduler.add_job(enqueue_reminders, IntervalTrigger(minutes=5), id="enqueue_reminders")
    scheduler.add_job(expire_proposals, IntervalTrigger(minutes=1), id="expire_proposals")
    scheduler.add_job(purge_expired_tokens, CronTrigger(hour=3), id="purge_expired_tokens")
    scheduler.add_job(
        purge_old_conversations, CronTrigger(hour=3, minute=15), id="purge_old_conversations"
    )
    return scheduler


async def run() -> None:
    settings = get_settings()
    settings.validate_for_runtime()
    configure_logging(settings)
    init_sentry(settings)

    scheduler = build_scheduler(settings.clinic_tz)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    scheduler.start()
    log.info(
        "worker.started", env=settings.app_env.value, jobs=[job.id for job in scheduler.get_jobs()]
    )
    await stop.wait()
    scheduler.shutdown(wait=True)
    log.info("worker.stopped")


if __name__ == "__main__":
    asyncio.run(run())
