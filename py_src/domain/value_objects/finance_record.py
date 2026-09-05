from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class FinanceRecord:
    order_id: str
    seller_sku: str
    quantity: int = 0
    fee_amount: float = 0.0
    refunded_sales: float = 0.0
