from __future__ import annotations

from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Any, Literal

OperationType = Literal["sale", "refund"]
DocumentType = Literal["РеализацияУслуг", "ВозвратОтПокупателя"]


@dataclass(frozen=True)
class UserInfo:
    external_user_id: str
    email: str
    name: str = ""


@dataclass(frozen=True)
class SourceLine:
    course_id: str
    title: str
    quantity: Decimal
    price: Decimal


@dataclass(frozen=True)
class AccountingLine:
    item_external_id: str
    item_name: str
    quantity: str
    price: str
    amount: str


@dataclass(frozen=True)
class OneCOperation:
    external_id: str
    source_system: str
    operation_type: OperationType
    document_type: DocumentType
    source_order_number: str
    source_refund_number: str | None
    original_order_number: str | None
    date: str
    status: str
    currency: str
    total_amount: str
    customer: dict[str, str]
    lines: list[AccountingLine]
    payment: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["lines"] = [asdict(line) for line in self.lines]
        return data
