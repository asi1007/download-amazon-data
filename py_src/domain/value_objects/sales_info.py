from dataclasses import dataclass


@dataclass(frozen=True)
class SalesInfo:
    unit_count: int = 0
    total_sales_amount: float = 0.0
    order_count: int = 0
