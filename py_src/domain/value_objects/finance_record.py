from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class FinanceRecord:
    order_id: str
    seller_sku: str
    quantity: int = 0
    fba_fee_amount: float = 0.0
    referral_fee_amount: float = 0.0
    refunded_sales: float = 0.0

    @property
    def fee_amount(self) -> float:
        return self.fba_fee_amount + self.referral_fee_amount
