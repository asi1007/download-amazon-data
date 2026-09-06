from __future__ import annotations
from dataclasses import dataclass

from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.domain.value_objects.unit_costs import UnitCosts


@dataclass(frozen=True)
class SettledFees:
    quantity: int = 0
    fba_fee_amount: float = 0.0
    referral_fee_amount: float = 0.0
    refunded_sales: float = 0.0

    @property
    def fee_amount(self) -> float:
        return self.fba_fee_amount + self.referral_fee_amount


def actual_gross_profit(
    sales: SalesInfo, settled: SettledFees, costs: UnitCosts
) -> float | None:
    if costs.total_per_unit is None:
        return None
    # 売上は orderMetrics（注文ベース）に統一し、置き換えるのは手数料の項だけ。
    # Finances の Principal と orderMetrics の totalSales は税の扱いが違うため、
    # 混ぜると母集団だけでなく金額の定義まで食い違う
    # 返金は quantity を負にするため、素朴な引き算だと販売個数より多い
    # 「未出荷」が出てしまう。0 と販売個数の間に収める
    unsettled_units = min(max(sales.unit_count - settled.quantity, 0), sales.unit_count)
    estimated_fee = (costs.selling_fee + costs.fba_fee) * unsettled_units
    return (
        sales.total_sales_amount
        - settled.refunded_sales
        - settled.fee_amount
        - estimated_fee
        - costs.cost * sales.unit_count
    )


def is_fully_settled(sales: SalesInfo, settled: SettledFees) -> bool:
    return settled.quantity >= sales.unit_count
