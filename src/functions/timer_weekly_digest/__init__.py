"""
Timer trigger — runs every Monday at 08:00 UTC to generate and post the
weekly compliance digest via the Foundry Agent Service.

Replaces the scheduled Prompt Flow weekly_digest cron job.
"""
import logging
import os
import sys

import azure.functions as func

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))


def main(mytimer: func.TimerRequest) -> None:
    log = logging.getLogger("timer_weekly_digest")

    if mytimer.past_due:
        log.warning("Weekly digest timer is past due — running now")

    log.info("Starting weekly compliance digest generation")

    try:
        from shared.agents.weekly_digest import run_weekly_digest

        result = run_weekly_digest()
        log.info(
            "Weekly digest completed: posted=%s, summary_length=%d",
            result.get("posted"),
            len(result.get("summary", "")),
        )
    except Exception:
        log.exception("Weekly digest agent failed")
        raise
