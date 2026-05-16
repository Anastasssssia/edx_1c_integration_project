from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable
import json
import logging

import requests

from .config import Settings


class EdxClientError(RuntimeError):
    pass


class BaseEdxClient:
    def get_orders(self, created_after: datetime | None = None, created_before: datetime | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError

    def get_refunds(self, created_after: datetime | None = None, created_before: datetime | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError


class MockEdxClient(BaseEdxClient):
    """Client for demonstration without real Open edX API."""

    def __init__(self, orders_path: Path, refunds_path: Path, logger: logging.Logger | None = None) -> None:
        self.orders_path = orders_path
        self.refunds_path = refunds_path
        self.logger = logger or logging.getLogger(__name__)

    def _read_json_list(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            self.logger.warning("Mock file does not exist: %s", path)
            return []
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if isinstance(payload, dict) and "results" in payload:
            return list(payload["results"])
        if isinstance(payload, list):
            return payload
        raise EdxClientError(f"Unsupported mock JSON structure in {path}")

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)

    def _filter_by_date(
        self,
        records: Iterable[dict[str, Any]],
        created_after: datetime | None,
        created_before: datetime | None,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for record in records:
            raw_date = record.get("date_created") or record.get("created")
            record_dt = self._parse_datetime(raw_date)
            if created_after and record_dt and record_dt < created_after:
                continue
            if created_before and record_dt and record_dt >= created_before:
                continue
            result.append(record)
        return result

    def get_orders(self, created_after: datetime | None = None, created_before: datetime | None = None) -> list[dict[str, Any]]:
        orders = self._read_json_list(self.orders_path)
        return self._filter_by_date(orders, created_after, created_before)

    def get_refunds(self, created_after: datetime | None = None, created_before: datetime | None = None) -> list[dict[str, Any]]:
        refunds = self._read_json_list(self.refunds_path)
        return self._filter_by_date(refunds, created_after, created_before)


class EdxApiClient(BaseEdxClient):
    """Minimal REST client for Open edX e-commerce endpoints."""

    def __init__(self, settings: Settings, logger: logging.Logger | None = None) -> None:
        self.settings = settings
        self.logger = logger or logging.getLogger(__name__)
        self.session = requests.Session()
        self._access_token = settings.edx_access_token

    def _url(self, endpoint: str) -> str:
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return f"{self.settings.edx_base_url}/{endpoint.lstrip('/')}"

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        if not self.settings.edx_client_id or not self.settings.edx_client_secret:
            raise EdxClientError("EDX_CLIENT_ID and EDX_CLIENT_SECRET are required for OAuth token request")

        response = self.session.post(
            self.settings.edx_token_url,
            data={"grant_type": "client_credentials"},
            auth=(self.settings.edx_client_id, self.settings.edx_client_secret),
            timeout=30,
        )
        if response.status_code >= 400:
            raise EdxClientError(f"Cannot obtain edX token: HTTP {response.status_code}: {response.text}")
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise EdxClientError("OAuth response does not contain access_token")
        self._access_token = token
        return token

    @staticmethod
    def _format_datetime(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _get_paginated(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        url = self._url(endpoint)
        headers = {"Authorization": f"Bearer {self._get_access_token()}", "Accept": "application/json"}
        result: list[dict[str, Any]] = []

        while url:
            response = self.session.get(url, headers=headers, params=params, timeout=30)
            params = {}
            if response.status_code >= 400:
                raise EdxClientError(f"edX API error: HTTP {response.status_code}: {response.text}")
            payload = response.json()
            if isinstance(payload, list):
                result.extend(payload)
                break
            if isinstance(payload, dict):
                items = payload.get("results") or payload.get("orders") or payload.get("refunds") or []
                result.extend(items)
                url = payload.get("next")
                continue
            raise EdxClientError("Unsupported edX API response format")
        return result

    def get_orders(self, created_after: datetime | None = None, created_before: datetime | None = None) -> list[dict[str, Any]]:
        params = {
            "date_created__gte": self._format_datetime(created_after),
            "date_created__lt": self._format_datetime(created_before),
        }
        params = {key: value for key, value in params.items() if value is not None}
        return self._get_paginated(self.settings.edx_orders_endpoint, params)

    def get_refunds(self, created_after: datetime | None = None, created_before: datetime | None = None) -> list[dict[str, Any]]:
        params = {
            "date_created__gte": self._format_datetime(created_after),
            "date_created__lt": self._format_datetime(created_before),
        }
        params = {key: value for key, value in params.items() if value is not None}
        return self._get_paginated(self.settings.edx_refunds_endpoint, params)


def build_edx_client(settings: Settings, logger: logging.Logger | None = None) -> BaseEdxClient:
    if settings.use_mock_edx:
        return MockEdxClient(settings.sample_orders_path, settings.sample_refunds_path, logger)
    return EdxApiClient(settings, logger)


def day_range(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=timezone.utc)
    # Use next day at 00:00 as exclusive boundary.
    end_exclusive = datetime.combine(day, time.min, tzinfo=timezone.utc).replace(day=day.day)  # replaced below safely
    from datetime import timedelta

    return start, start + timedelta(days=1)
