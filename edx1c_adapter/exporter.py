from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
import json

from .models import OneCOperation


class JsonBatchExporter:
    def __init__(self, export_dir: Path) -> None:
        self.export_dir = export_dir
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export(self, operations: list[OneCOperation], export_date: date) -> Path:
        path = self.export_dir / f"export_{export_date.strftime('%Y%m%d')}.json"
        payload: dict[str, Any] = {
            "source_system": "edX",
            "export_date": export_date.isoformat(),
            "count": len(operations),
            "operations": [operation.to_dict() for operation in operations],
        }
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        return path

    @staticmethod
    def read(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def validate_payload(payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if payload.get("source_system") != "edX":
            errors.append("source_system must be edX")
        operations = payload.get("operations")
        if not isinstance(operations, list):
            errors.append("operations must be a list")
            return errors
        for index, operation in enumerate(operations, start=1):
            for field in ("external_id", "operation_type", "document_type", "date", "total_amount", "customer", "lines"):
                if field not in operation:
                    errors.append(f"operation #{index}: missing required field {field}")
            if "lines" in operation and not isinstance(operation["lines"], list):
                errors.append(f"operation #{index}: lines must be a list")
        return errors
