from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class FeeGap:
    asin: str
    quantity: int
    estimated_referral_fee: float
    actual_referral_fee: float
    estimated_fba_fee: float
    actual_fba_fee: float

    @property
    def fba_difference(self) -> float:
        return self.actual_fba_fee - self.estimated_fba_fee

    @property
    def referral_difference(self) -> float:
        return self.actual_referral_fee - self.estimated_referral_fee

    @property
    def difference(self) -> float:
        return self.fba_difference + self.referral_difference

    @property
    def ratio(self) -> float:
        estimated_total = self.estimated_referral_fee + self.estimated_fba_fee
        if not estimated_total:
            return 0.0
        return self.difference / estimated_total
