from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.domain.value_objects.unit_costs import UnitCosts, estimate_gross_profit


class TestEstimateGrossProfit:
    def test_subtracts_per_unit_costs_from_actual_sales(self) -> None:
        sales = SalesInfo(unit_count=3, total_sales_amount=3000.0)
        costs = UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=200.0)

        # 3000 - (100 + 300 + 200) * 3 = 1200
        assert estimate_gross_profit(sales, costs) == 1200.0

    def test_uses_actual_sales_not_units_times_price(self) -> None:
        # セール等で実売上が単価×個数と一致しなくても、実売上をそのまま使う
        sales = SalesInfo(unit_count=2, total_sales_amount=1500.0)
        costs = UnitCosts(selling_fee=50.0, fba_fee=100.0, cost=100.0)

        assert estimate_gross_profit(sales, costs) == 1000.0

    def test_returns_none_when_any_cost_is_missing(self) -> None:
        sales = SalesInfo(unit_count=1, total_sales_amount=1000.0)

        assert estimate_gross_profit(sales, UnitCosts(None, 300.0, 200.0)) is None
        assert estimate_gross_profit(sales, UnitCosts(100.0, None, 200.0)) is None
        assert estimate_gross_profit(sales, UnitCosts(100.0, 300.0, None)) is None

    def test_zero_units_gives_zero_profit(self) -> None:
        sales = SalesInfo(unit_count=0, total_sales_amount=0.0)
        costs = UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=200.0)

        assert estimate_gross_profit(sales, costs) == 0.0

    def test_can_be_negative(self) -> None:
        sales = SalesInfo(unit_count=1, total_sales_amount=500.0)
        costs = UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=200.0)

        assert estimate_gross_profit(sales, costs) == -100.0
