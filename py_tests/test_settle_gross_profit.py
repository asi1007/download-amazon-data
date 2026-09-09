from datetime import date

from py_src.domain.value_objects.finance_record import FinanceRecord
from sales_data.domain.value_objects.sales_info import SalesInfo
from py_src.domain.value_objects.settled_fees import SettledFees
from sales_data.domain.value_objects.unit_costs import UnitCosts
from py_src.usecases.settle_gross_profit import (
    aggregate_settled,
    build_fee_gaps,
    build_profit_cells,
)

SKU_TO_ASIN = {"SKU-A": "B00EXAMPLE", "SKU-B": "B00EXAMPLF"}
PURCHASE_DATES = {"503-1": date(2026, 9, 1), "503-2": date(2026, 9, 2)}
COSTS = {"B00EXAMPLE": UnitCosts(selling_fee=100.0, fba_fee=200.0, cost=400.0)}


class TestAggregateSettled:
    def test_groups_by_order_date_and_asin(self) -> None:
        records = [
            FinanceRecord("503-1", "SKU-A", quantity=2, fba_fee_amount=600.0),
            FinanceRecord("503-1", "SKU-A", quantity=1, fba_fee_amount=300.0),
            FinanceRecord("503-2", "SKU-B", quantity=1, fba_fee_amount=250.0),
        ]

        settled, unknown = aggregate_settled(records, PURCHASE_DATES, SKU_TO_ASIN)

        assert settled[(date(2026, 9, 1), "B00EXAMPLE")].quantity == 3
        assert settled[(date(2026, 9, 1), "B00EXAMPLE")].fee_amount == 900.0
        assert settled[(date(2026, 9, 2), "B00EXAMPLF")].fee_amount == 250.0
        assert unknown == 0

    def test_counts_skus_that_are_not_on_the_sheet(self) -> None:
        records = [FinanceRecord("503-1", "SKU-UNKNOWN", quantity=1, fba_fee_amount=100.0)]

        settled, unknown = aggregate_settled(records, PURCHASE_DATES, SKU_TO_ASIN)

        assert settled == {}
        assert unknown == 1

    def test_ignores_orders_placed_outside_the_window(self) -> None:
        # 窓より前に注文され、窓の中で出荷された分。書き換える日が窓に無い
        records = [FinanceRecord("503-OLD", "SKU-A", quantity=1, fba_fee_amount=100.0)]

        settled, unknown = aggregate_settled(records, PURCHASE_DATES, SKU_TO_ASIN)

        assert settled == {}
        assert unknown == 0

    def test_refund_reduces_quantity_and_fee_for_the_same_day(self) -> None:
        records = [
            FinanceRecord("503-1", "SKU-A", quantity=1, fba_fee_amount=300.0),
            FinanceRecord("503-1", "SKU-A", quantity=-1, fba_fee_amount=-30.0, refunded_sales=434.0),
        ]

        settled, _ = aggregate_settled(records, PURCHASE_DATES, SKU_TO_ASIN)

        measured = settled[(date(2026, 9, 1), "B00EXAMPLE")]
        assert measured.quantity == 0
        assert measured.fee_amount == 270.0
        assert measured.refunded_sales == 434.0


class TestBuildProfitCells:
    def test_pairs_each_days_sales_with_its_settled_fees(self) -> None:
        sales = {"B00EXAMPLE": {
            date(2026, 9, 1): SalesInfo(unit_count=3, total_sales_amount=6000.0),
        }}
        settled = {(date(2026, 9, 1), "B00EXAMPLE"): SettledFees(quantity=3, fba_fee_amount=1050.0)}

        cells = build_profit_cells(sales, settled, COSTS)

        cell = cells[date(2026, 9, 1)][0]
        assert cell.asin == "B00EXAMPLE"
        assert cell.profit == 3750.0
        assert cell.estimate == 3900.0
        assert cell.fully_settled is True

    def test_day_with_no_finance_data_stays_on_the_estimate_and_keeps_yellow(self) -> None:
        sales = {"B00EXAMPLE": {
            date(2026, 9, 1): SalesInfo(unit_count=3, total_sales_amount=6000.0),
        }}

        cells = build_profit_cells(sales, {}, COSTS)

        cell = cells[date(2026, 9, 1)][0]
        assert cell.profit == cell.estimate == 3900.0
        assert cell.fully_settled is False

    def test_asin_without_costs_is_skipped_entirely(self) -> None:
        sales = {"B00NOCOST99": {date(2026, 9, 1): SalesInfo(unit_count=1)}}

        assert build_profit_cells(sales, {}, COSTS) == {}


class TestBuildFeeGaps:
    def test_reports_per_unit_estimate_against_per_unit_actual(self) -> None:
        settled = {
            (date(2026, 9, 1), "B00EXAMPLE"): SettledFees(quantity=2, fba_fee_amount=600.0, referral_fee_amount=200.0),
            (date(2026, 9, 2), "B00EXAMPLE"): SettledFees(quantity=2, fba_fee_amount=600.0, referral_fee_amount=200.0),
        }

        gaps = build_fee_gaps(settled, COSTS)

        assert len(gaps) == 1
        gap = gaps[0]
        assert gap.asin == "B00EXAMPLE"
        assert gap.quantity == 4
        assert gap.estimated_referral_fee == 100.0
        assert gap.estimated_fba_fee == 200.0
        assert gap.actual_fba_fee + gap.actual_referral_fee == 400.0
        assert gap.difference == 100.0
        assert round(gap.ratio, 4) == round(100.0 / 300.0, 4)

    def test_sorted_by_absolute_gap_so_the_worst_estimates_come_first(self) -> None:
        costs = {
            "B00SMALL999": UnitCosts(selling_fee=100.0, fba_fee=200.0, cost=0.0),
            "B00BIG99999": UnitCosts(selling_fee=100.0, fba_fee=200.0, cost=0.0),
        }
        settled = {
            (date(2026, 9, 1), "B00SMALL999"): SettledFees(quantity=1, fba_fee_amount=310.0),
            (date(2026, 9, 1), "B00BIG99999"): SettledFees(quantity=1, fba_fee_amount=600.0),
        }

        assert [gap.asin for gap in build_fee_gaps(settled, costs)] == [
            "B00BIG99999", "B00SMALL999"
        ]

    def test_asin_with_no_settled_units_is_left_out(self) -> None:
        settled = {(date(2026, 9, 1), "B00EXAMPLE"): SettledFees(quantity=0, fba_fee_amount=0.0)}

        assert build_fee_gaps(settled, COSTS) == []

    def test_day_with_no_sales_is_settled_because_there_is_nothing_to_measure(self) -> None:
        sales = {"B00EXAMPLE": {date(2026, 9, 1): SalesInfo(unit_count=0)}}

        cells = build_profit_cells(sales, {}, COSTS)

        assert cells[date(2026, 9, 1)][0].fully_settled is True
