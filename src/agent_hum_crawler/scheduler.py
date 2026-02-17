"""Scheduling utilities for periodic monitoring cycles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from apscheduler.schedulers import SchedulerNotRunningError
from apscheduler.schedulers.blocking import BlockingScheduler


@dataclass
class SchedulerOptions:
    interval_minutes: int
    max_runs: int | None = None


def start_scheduler(run_cycle: Callable[[], None], options: SchedulerOptions) -> None:
    if options.max_runs == 1:
        run_cycle()
        return

    scheduler = BlockingScheduler()
    run_counter = {"count": 0}

    def job_wrapper() -> None:
        run_cycle()
        run_counter["count"] += 1
        if options.max_runs is not None and run_counter["count"] >= options.max_runs:
            try:
                scheduler.shutdown(wait=False)
            except SchedulerNotRunningError:
                pass

    scheduler.add_job(job_wrapper, "interval", minutes=options.interval_minutes, id="monitoring_cycle")
    job_wrapper()
    if options.max_runs is None or run_counter["count"] < options.max_runs:
        scheduler.start()
