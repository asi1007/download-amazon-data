from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ItemFee:
    order_id: str
    seller_sku: str
    fee_amount: float
