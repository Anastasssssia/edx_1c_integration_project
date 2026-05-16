from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import logging

from .edx_client import BaseEdxClient, day_range
from .exporter import JsonBatchExporter
from .models import OneCOperation
from .onec_client import OneCClient, SendResult
from .state import StateStore
from .transformer import TransformationError, transform_order, transform_refund


class IntegrationService:
    def __init__(
        self,
        edx_client: BaseEdxClient,
        onec_client: OneCClient,
        state_store: StateStore,
        exporter: JsonBatchExporter,
        logger: logging.Logger | None = None,
    ) -> None:
        self.edx_client = edx_client
        self.onec_client = onec_client
        self.state_store = state_store
        self.exporter = exporter
        self.logger = logger or logging.getLogger(__name__)

    def load_and_transform(
        self,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
    ) -> list[OneCOperation]:
        operations: list[OneCOperation] = []

        orders = self.edx_client.get_orders(created_after=created_after, created_before=created_before)
        self.logger.info("Loaded %s orders from edX", len(orders))
        for order in orders:
            try:
                operations.append(transform_order(order))
            except TransformationError as exc:
                self.logger.warning("Skipped order due to transformation error: %s", exc)

        refunds = self.edx_client.get_refunds(created_after=created_after, created_before=created_before)
        self.logger.info("Loaded %s refunds from edX", len(refunds))
        for refund in refunds:
            try:
                operations.append(transform_refund(refund))
            except TransformationError as exc:
                self.logger.warning("Skipped refund due to transformation error: %s", exc)

        return operations

    def process_once(self, send_to_onec: bool = True) -> tuple[list[OneCOperation], list[SendResult]]:
        created_after = self.state_store.get_last_poll_at()
        created_before = datetime.now(timezone.utc)
        operations = self.load_and_transform(created_after=created_after, created_before=created_before)
        results: list[SendResult] = []
        if send_to_onec and operations:
            results = self.onec_client.send_many(operations)
        self.state_store.set_last_poll_at(created_before)
        return operations, results

    def export_batch(self, export_date: date) -> tuple[list[OneCOperation], str]:
        start, end = day_range(export_date)
        operations = self.load_and_transform(created_after=start, created_before=end)
        path = self.exporter.export(operations, export_date)
        self.logger.info("Batch export created: %s", path)
        return operations, str(path)
