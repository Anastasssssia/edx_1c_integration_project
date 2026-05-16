from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        tmp_path.replace(self.path)

    def get_last_poll_at(self) -> datetime | None:
        value = self.load().get("last_poll_at")
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def set_last_poll_at(self, value: datetime | None = None) -> None:
        if value is None:
            value = datetime.now(timezone.utc)
        data = self.load()
        data["last_poll_at"] = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        self.save(data)
