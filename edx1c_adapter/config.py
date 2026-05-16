from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    use_mock_edx: bool

    edx_base_url: str
    edx_token_url: str
    edx_client_id: str
    edx_client_secret: str
    edx_access_token: Optional[str]
    edx_orders_endpoint: str
    edx_refunds_endpoint: str

    onec_base_url: str
    onec_endpoint: str
    onec_username: Optional[str]
    onec_password: Optional[str]
    onec_timeout_seconds: int

    sample_orders_path: Path
    sample_refunds_path: Path
    export_dir: Path
    state_path: Path
    log_path: Path

    poll_interval_minutes: int
    daily_export_time: str


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "да"}


def _none_if_empty(value: str | None) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def load_settings(env_path: str | Path | None = None) -> Settings:
    if env_path:
        load_dotenv(env_path)
    else:
        load_dotenv()

    return Settings(
        use_mock_edx=_bool(os.getenv("USE_MOCK_EDX"), default=True),
        edx_base_url=os.getenv("EDX_BASE_URL", "https://edx.example.com").rstrip("/"),
        edx_token_url=os.getenv("EDX_TOKEN_URL", "https://edx.example.com/oauth2/access_token"),
        edx_client_id=os.getenv("EDX_CLIENT_ID", ""),
        edx_client_secret=os.getenv("EDX_CLIENT_SECRET", ""),
        edx_access_token=_none_if_empty(os.getenv("EDX_ACCESS_TOKEN")),
        edx_orders_endpoint=os.getenv("EDX_ORDERS_ENDPOINT", "/api/ecommerce/v2/orders/"),
        edx_refunds_endpoint=os.getenv("EDX_REFUNDS_ENDPOINT", "/api/ecommerce/v2/refunds/"),
        onec_base_url=os.getenv("ONEC_BASE_URL", "http://127.0.0.1:8088").rstrip("/"),
        onec_endpoint=os.getenv("ONEC_ENDPOINT", "/edx_integration/orders"),
        onec_username=_none_if_empty(os.getenv("ONEC_USERNAME")),
        onec_password=_none_if_empty(os.getenv("ONEC_PASSWORD")),
        onec_timeout_seconds=int(os.getenv("ONEC_TIMEOUT_SECONDS", "15")),
        sample_orders_path=Path(os.getenv("SAMPLE_ORDERS_PATH", "data/sample_orders.json")),
        sample_refunds_path=Path(os.getenv("SAMPLE_REFUNDS_PATH", "data/sample_refunds.json")),
        export_dir=Path(os.getenv("EXPORT_DIR", "exports")),
        state_path=Path(os.getenv("STATE_PATH", "state.json")),
        log_path=Path(os.getenv("LOG_PATH", "logs/adapter.log")),
        poll_interval_minutes=int(os.getenv("POLL_INTERVAL_MINUTES", "10")),
        daily_export_time=os.getenv("DAILY_EXPORT_TIME", "02:00"),
    )
