"""Scheduler: run ingestion daily at 09:15 Asia/Kolkata."""

from __future__ import annotations

import logging
from typing import Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .corpus_loader import load_corpus
from .pipeline import run_ingestion

logger = logging.getLogger("facts_desk.scheduler")


def start_scheduler(job: Callable | None = None) -> None:
    """
    Block and run the ingestion job on the corpus.yaml schedule.

    Default: cron `15 9 * * *` timezone `Asia/Kolkata`.
    """
    corpus = load_corpus()
    cron = corpus.scheduler_cron  # e.g. "15 9 * * *"
    tz = corpus.scheduler_timezone
    parts = cron.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron}")
    minute, hour, day, month, day_of_week = parts

    trigger = CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        timezone=tz,
    )

    def _job() -> None:
        logger.info("Scheduler firing ingestion job (%s %s)", cron, tz)
        result = (job or run_ingestion)()
        logger.info("Ingestion finished: %s", result.message)

    scheduler = BlockingScheduler(timezone=tz)
    scheduler.add_job(_job, trigger=trigger, id="facts_desk_ingest", replace_existing=True)
    logger.info("Scheduler started — next ingest at cron %s (%s)", cron, tz)
    print(f"Scheduler running: ingestion daily at {hour}:{minute.zfill(2)} {tz} (cron {cron})")
    print("Press Ctrl+C to stop.")
    scheduler.start()
