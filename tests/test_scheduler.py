from agent_hum_crawler.scheduler import SchedulerOptions, start_scheduler


def test_scheduler_max_runs_one() -> None:
    counter = {"n": 0}

    def run_cycle() -> None:
        counter["n"] += 1

    start_scheduler(run_cycle=run_cycle, options=SchedulerOptions(interval_minutes=30, max_runs=1))
    assert counter["n"] == 1
