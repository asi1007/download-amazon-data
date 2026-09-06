from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.domain.value_objects.settled_fees import (
    SettledFees,
    actual_gross_profit,
    is_fully_settled,
)
from py_src.domain.value_objects.unit_costs import UnitCosts

COSTS = UnitCosts(selling_fee=100.0, fba_fee=200.0, cost=400.0)


class TestActualGrossProfit:
    def test_all_units_settled_uses_only_the_measured_fee(self) -> None:
        sales = SalesInfo(unit_count=3, total_sales_amount=6000.0)
        settled = SettledFees(quantity=3, fba_fee_amount=1050.0)

        # 6000 - 1050(実測) - 400*3(原価)
        assert actual_gross_profit(sales, settled, COSTS) == 3750.0

    def test_unsettled_units_fall_back_to_the_estimated_fee(self) -> None:
        # 3個売れて1個だけ出荷済み。残り2個は見積の (100+200) を使う
        sales = SalesInfo(unit_count=3, total_sales_amount=6000.0)
        settled = SettledFees(quantity=1, fba_fee_amount=350.0)

        # 6000 - 350(実測) - 300*2(見積) - 400*3(原価)
        assert actual_gross_profit(sales, settled, COSTS) == 3850.0

    def test_no_settled_units_equals_the_pure_estimate(self) -> None:
        sales = SalesInfo(unit_count=3, total_sales_amount=6000.0)

        # 6000 - 300*3 - 400*3 = 3900。見積のみの式と一致する
        assert actual_gross_profit(sales, SettledFees(), COSTS) == 3900.0

    def test_settled_quantity_larger_than_sold_does_not_produce_negative_estimate(self) -> None:
        # 注文日と出荷日の期ずれで出荷個数のほうが多くなることがある。
        # 未出荷個数を負のまま使うと見積手数料が利益に足し込まれてしまう
        sales = SalesInfo(unit_count=1, total_sales_amount=2000.0)
        settled = SettledFees(quantity=3, fba_fee_amount=1050.0)

        assert actual_gross_profit(sales, settled, COSTS) == 2000.0 - 1050.0 - 400.0

    def test_returns_none_when_any_cost_is_missing(self) -> None:
        sales = SalesInfo(unit_count=3, total_sales_amount=6000.0)
        settled = SettledFees(quantity=3, fba_fee_amount=1050.0)

        assert actual_gross_profit(sales, settled, UnitCosts(selling_fee=100.0)) is None

    def test_zero_units_gives_zero_not_none(self) -> None:
        assert actual_gross_profit(SalesInfo(), SettledFees(), COSTS) == 0.0


class TestIsFullySettled:
    def test_true_when_every_sold_unit_has_a_measured_fee(self) -> None:
        assert is_fully_settled(SalesInfo(unit_count=3), SettledFees(quantity=3)) is True

    def test_false_while_any_unit_is_unshipped(self) -> None:
        assert is_fully_settled(SalesInfo(unit_count=3), SettledFees(quantity=2)) is False

    def test_true_for_a_day_with_no_sales(self) -> None:
        # 売れていない日は確定させるものが無い。黄色を残す理由がない
        assert is_fully_settled(SalesInfo(), SettledFees()) is True


class TestRefunds:
    def test_refunded_sales_are_subtracted_from_revenue(self) -> None:
        # orderMetrics は注文ベースなので返金しても売上が残る。手数料だけ戻すと
        # 返品された注文の利益が過大になる
        sales = SalesInfo(unit_count=3, total_sales_amount=6000.0)
        settled = SettledFees(quantity=3, fba_fee_amount=1050.0, refunded_sales=2000.0)

        assert actual_gross_profit(sales, settled, COSTS) == 6000.0 - 2000.0 - 1050.0 - 1200.0

    def test_refund_only_day_does_not_inflate_the_estimated_fee(self) -> None:
        # 返金は quantity を負にする。1個売れて1個返金なら quantity=0 になり、
        # 素朴な引き算だと未出荷が販売個数を超えることがある
        sales = SalesInfo(unit_count=1, total_sales_amount=2000.0)
        settled = SettledFees(quantity=-1, fba_fee_amount=-30.0, refunded_sales=434.0)

        # 未出荷は販売個数の 1 で頭打ち（2 にはならない）
        assert actual_gross_profit(sales, settled, COSTS) == 2000.0 - 434.0 + 30.0 - 300.0 - 400.0
