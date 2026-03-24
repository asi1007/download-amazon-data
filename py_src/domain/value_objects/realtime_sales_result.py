from dataclasses import dataclass, field


@dataclass
class RealtimeSalesResult:
    asin: str
    unit_count: int = field(default=0)
    total_amount: float = field(default=0.0)

    def add_sale(self, quantity: int, unit_price: float) -> None:
        self.unit_count += quantity
        self.total_amount += quantity * unit_price
