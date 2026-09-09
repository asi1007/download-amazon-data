from __future__ import annotations
from dataclasses import dataclass

from sales_data.domain.value_objects.sales_info import SalesInfo


@dataclass(frozen=True)
class UnitCosts:
    selling_fee: float | None = None
    fba_fee: float | None = None
    cost: float | None = None

    @property
    def total_per_unit(self) -> float | None:
        parts = (self.selling_fee, self.fba_fee, self.cost)
        if any(part is None for part in parts):
            return None
        return sum(parts)


def estimate_gross_profit(sales: SalesInfo, costs: UnitCosts) -> float | None:
    per_unit = costs.total_per_unit
    if per_unit is None:
        return None
    return sales.total_sales_amount - per_unit * sales.unit_count
