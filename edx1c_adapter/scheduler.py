from __future__ import annotations

from datetime import date, timedelta
import logging
import time

import schedule

from .service import IntegrationService


class AdapterScheduler:
    def __init__(self, service: IntegrationService, poll_interval_minutes: int, daily_export_time: str, logger: logging.Logger | None = None) -> None:
        self.service = service
        self.poll_interval_minutes = poll_interval_minutes
        self.daily_export_time = daily_export_time
        self.logger = logger or logging.getLogger(__name__)

    def run_forever(self) -> None:
        schedule.every(self.poll_interval_minutes).minutes.do(self._safe_process_once)
        schedule.every().day.at(self.daily_export_time).do(self._safe_export_yesterday)

        self.logger.info(
            "Scheduler started: polling every %s minutes, daily export at %s",
            self.poll_interval_minutes,
            self.daily_export_time,
        )
        self._safe_process_once()

        while True:
            schedule.run_pending()
            time.sleep(1)

    def _safe_process_once(self) -> None:
        try:
            operations, results = self.service.process_once(send_to_onec=True)
            self.logger.info("Polling cycle finished: operations=%s, sent=%s", len(operations), len(results))
        except Exception:
            self.logger.exception("Polling cycle failed")

    def _safe_export_yesterday(self) -> None:
        try:
            yesterday = date.today() - timedelta(days=1)
            operations, path = self.service.export_batch(yesterday)
            self.logger.info("Daily batch export finished: operations=%s, path=%s", len(operations), path)
        except Exception:
            self.logger.exception("Daily batch export failed")
