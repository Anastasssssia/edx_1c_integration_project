from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from .models import AccountingLine, OneCOperation


class TransformationError(ValueError):
    pass


SUPPORTED_ORDER_STATUSES = {"complete", "refunded"}


def _decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise TransformationError(f"Cannot convert value to decimal: {value!r}") from exc


def _quantity(value: Any) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "1")).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise TransformationError(f"Cannot convert quantity to decimal: {value!r}") from exc


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _qty(value: Decimal) -> str:
    return str(value.normalize())


def _normalize_datetime(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_get_user(order: dict[str, Any]) -> dict[str, str]:
    user = order.get("user") or {}
    external_user_id = str(user.get("id") or user.get("username") or "retail_customer")
    email = str(user.get("email") or "retail@example.local")
    name = str(user.get("name") or user.get("full_name") or user.get("username") or "Розничный покупатель")
    return {
        "external_user_id": external_user_id,
        "email": email,
        "name": name,
    }


def _extract_lines(order: dict[str, Any]) -> list[AccountingLine]:
    raw_lines = order.get("lines") or order.get("items") or []
    if not raw_lines:
        title = str(order.get("title") or "Образовательная услуга edX")
        amount = _decimal(order.get("total_excl_tax") or order.get("total") or order.get("amount"))
        return [
            AccountingLine(
                item_external_id=str(order.get("course_id") or "edx-service"),
                item_name=title,
                quantity="1",
                price=_money(amount),
                amount=_money(amount),
            )
        ]

    result: list[AccountingLine] = []
    for line in raw_lines:
        course_id = str(line.get("course_id") or line.get("product_id") or line.get("sku") or "edx-course")
        title = str(line.get("title") or line.get("name") or "Курс edX")
        quantity = _quantity(line.get("quantity", 1))
        price = _decimal(line.get("price") or line.get("unit_price") or line.get("line_price_excl_tax") or 0)
        amount = (quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        result.append(
            AccountingLine(
                item_external_id=course_id,
                item_name=title,
                quantity=_qty(quantity),
                price=_money(price),
                amount=_money(amount),
            )
        )
    return result


def transform_order(order: dict[str, Any]) -> OneCOperation:
    number = str(order.get("number") or order.get("order_number") or "").strip()
    if not number:
        raise TransformationError("Order number is required")

    status = str(order.get("status") or "").strip().lower()
    if status not in SUPPORTED_ORDER_STATUSES:
        raise TransformationError(f"Unsupported order status: {status!r}")

    operation_type = "refund" if status == "refunded" else "sale"
    document_type = "ВозвратОтПокупателя" if operation_type == "refund" else "РеализацияУслуг"
    external_id = f"edx:order:{number}:{operation_type}"

    lines = _extract_lines(order)
    total_amount = _decimal(order.get("total_excl_tax") or order.get("total") or sum(Decimal(line.amount) for line in lines))

    return OneCOperation(
        external_id=external_id,
        source_system="edX",
        operation_type=operation_type,  # type: ignore[arg-type]
        document_type=document_type,  # type: ignore[arg-type]
        source_order_number=number,
        source_refund_number=None,
        original_order_number=number if operation_type == "refund" else None,
        date=_normalize_datetime(order.get("date_created") or order.get("created")),
        status=status,
        currency=str(order.get("currency") or "USD"),
        total_amount=_money(total_amount),
        customer=_safe_get_user(order),
        lines=lines,
        payment=order.get("payment") or {},
        meta={
            "raw_status": order.get("status"),
            "source": "orders",
        },
    )


def transform_refund(refund: dict[str, Any]) -> OneCOperation:
    refund_number = str(refund.get("refund_number") or refund.get("number") or refund.get("id") or "").strip()
    if not refund_number:
        raise TransformationError("Refund number is required")

    order_number = str(refund.get("order_number") or refund.get("order") or refund.get("source_order_number") or "").strip()
    if not order_number:
        raise TransformationError("Refund must contain original order number")

    amount = _decimal(refund.get("total") or refund.get("amount") or refund.get("total_excl_tax"))
    line = AccountingLine(
        item_external_id=str(refund.get("course_id") or "edx-refund"),
        item_name=str(refund.get("title") or "Возврат оплаты за образовательную услугу edX"),
        quantity="1",
        price=_money(amount),
        amount=_money(amount),
    )

    user = refund.get("user") or {}
    customer = {
        "external_user_id": str(user.get("id") or "retail_customer"),
        "email": str(user.get("email") or "retail@example.local"),
        "name": str(user.get("name") or "Розничный покупатель"),
    }

    return OneCOperation(
        external_id=f"edx:refund:{refund_number}",
        source_system="edX",
        operation_type="refund",
        document_type="ВозвратОтПокупателя",
        source_order_number=order_number,
        source_refund_number=refund_number,
        original_order_number=order_number,
        date=_normalize_datetime(refund.get("date_created") or refund.get("created")),
        status="refunded",
        currency=str(refund.get("currency") or "USD"),
        total_amount=_money(amount),
        customer=customer,
        lines=[line],
        payment=refund.get("payment") or {},
        meta={
            "reason": refund.get("reason", ""),
            "source": "refunds",
        },
    )
