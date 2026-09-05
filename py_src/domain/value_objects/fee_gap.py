from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class FeeGap:
    asin: str
    quantity: int
    estimated_unit_fee: float
    actual_unit_fee: float

    @property
    def difference(self) -> float:
        return self.actual_unit_fee - self.estimated_unit_fee

    @property
    def ratio(self) -> float:
        if not self.estimated_unit_fee:
            return 0.0
        return self.difference / self.estimated_unit_fee
