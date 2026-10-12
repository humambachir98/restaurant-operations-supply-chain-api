import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import SessionLocal
from app.services.receiving import auto_receive_due_orders, catch_up_date
from app.utils.time import LOCAL_TZ, now_local

logger = logging.getLogger(__name__)

AUTO_RECEIVE_JOB_ID = "auto_receive_due_orders"


def run_auto_receive(as_of=None) -> list[int]:
    """Scheduler entry point: own session, never raises (a crash would only be logged anyway)."""
    try:
        with SessionLocal() as db:
            return auto_receive_due_orders(db, as_of)
    except Exception:
        logger.exception("Auto-receive run failed")
        return []


def create_scheduler() -> BackgroundScheduler:
    """Daily auto-receive at `settings.auto_receive_time`, Berlin time (DST-aware)."""
    scheduler = BackgroundScheduler(timezone=LOCAL_TZ)
    scheduler.add_job(
        run_auto_receive,
        CronTrigger(
            hour=settings.auto_receive_time.hour,
            minute=settings.auto_receive_time.minute,
            timezone=LOCAL_TZ,
        ),
        id=AUTO_RECEIVE_JOB_ID,
        coalesce=True,  # several missed runs collapse into one
        misfire_grace_time=6 * 3600,  # still run if the process was asleep at 06:00
        max_instances=1,
    )
    return scheduler


def catch_up_on_startup() -> list[int]:
    """Receive deliveries that came due while the app wasn't running."""
    return run_auto_receive(catch_up_date(now_local(), settings.auto_receive_time))
