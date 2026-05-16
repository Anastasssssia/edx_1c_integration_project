from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import logging

import requests

from .config import Settings
from .models import OneCOperation


class OneCClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class SendResult:
    external_id: str
    status_code: int
    ok: bool
    response_text: str


class OneCClient:
    def __init__(self, settings: Settings, logger: logging.Logger | None = None) -> None:
        self.settings = settings
        self.logger = logger or logging.getLogger(__name__)
        self.session = requests.Session()

    @property
    def target_url(self) -> str:
        return f"{self.settings.onec_base_url}/{self.settings.onec_endpoint.lstrip('/')}"

    def send_operation(self, operation: OneCOperation) -> SendResult:
        auth = None
        if self.settings.onec_username and self.settings.onec_password:
            auth = (self.settings.onec_username, self.settings.onec_password)

        response = self.session.post(
            self.target_url,
            json=operation.to_dict(),
            headers={"Content-Type": "application/json; charset=utf-8"},
            auth=auth,
            timeout=self.settings.onec_timeout_seconds,
        )

        ok = 200 <= response.status_code < 300
        if ok:
            self.logger.info("Sent operation %s to 1C: HTTP %s", operation.external_id, response.status_code)
        else:
            self.logger.error(
                "Cannot send operation %s to 1C: HTTP %s: %s",
                operation.external_id,
                response.status_code,
                response.text,
            )
        return SendResult(
            external_id=operation.external_id,
            status_code=response.status_code,
            ok=ok,
            response_text=response.text,
        )

    def send_many(self, operations: list[OneCOperation]) -> list[SendResult]:
        results: list[SendResult] = []
        for operation in operations:
            results.append(self.send_operation(operation))
        return results
