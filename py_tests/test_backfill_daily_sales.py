from datetime import date, timezone, timedelta
from unittest.mock import Mock, call, patch

import backfill_daily_sales
from backfill_daily_sales import _backfill_one_day
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.domain.value_objects.unit_costs import UnitCosts
from py_src.domain.value_objects.gross_profit_write_result import GrossProfitWriteResult
from py_src.infrastructure.sheets.sales_sheet import SalesSheet
from py_src.infrastructure.sheets.unit_cost_reader import UnitCostReader

JST = timezone(timedelta(hours=9))


class TestBackfillOneDay:
    def test_writes_through_write_sales_nums_with_target_date(self) -> None:
        sales_sheet = Mock(spec=SalesSheet)
        sales_sheet.write_gross_profit.return_value = GrossProfitWriteResult()
        sales_repository = Mock()
        asin_sales = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
        }
        sales_repository.get_daily_sales.return_value = asin_sales

        _backfill_one_day(sales_sheet, ["B00EXAMPLE"], sales_repository, "2026-06-18", {})

        sales_sheet.write_sales_nums.assert_called_once_with(
            asin_sales, target_date=date(2026, 6, 18)
        )

    def test_does_not_reach_into_sales_sheet_privates(self) -> None:
        sales_sheet = Mock(spec=SalesSheet)
        sales_sheet.write_gross_profit.return_value = GrossProfitWriteResult()
        sales_repository = Mock()
        sales_repository.get_daily_sales.return_value = {}

        _backfill_one_day(sales_sheet, ["B00EXAMPLE"], sales_repository, "2026-06-18", {})

        sales_sheet._resolve_column_for.assert_not_called()

    def test_fetches_the_requested_days_utc_window(self) -> None:
        sales_sheet = Mock(spec=SalesSheet)
        sales_sheet.write_gross_profit.return_value = GrossProfitWriteResult()
        sales_repository = Mock()
        sales_repository.get_daily_sales.return_value = {}

        _backfill_one_day(sales_sheet, ["B00EXAMPLE"], sales_repository, "2026-06-18", {})

        args, _ = sales_repository.get_daily_sales.call_args
        asin_list, start_date_utc, end_date_utc = args
        assert asin_list == ["B00EXAMPLE"]
        assert start_date_utc == "2026-06-17T15:00:00Z"
        assert end_date_utc == "2026-06-18T15:00:00Z"

    def test_writes_gross_profit_after_sales_nums_using_the_given_costs(self) -> None:
        sales_sheet = Mock(spec=SalesSheet)
        sales_sheet.write_gross_profit.return_value = GrossProfitWriteResult()
        sales_repository = Mock()
        asin_sales = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
        }
        sales_repository.get_daily_sales.return_value = asin_sales
        costs = {
            "B00EXAMPLE": UnitCosts(selling_fee=100.0, fba_fee=200.0, cost=300.0),
        }

        _backfill_one_day(sales_sheet, ["B00EXAMPLE"], sales_repository, "2026-06-18", costs)

        sales_sheet.assert_has_calls(
            [
                call.write_sales_nums(asin_sales, target_date=date(2026, 6, 18)),
                call.write_gross_profit({"B00EXAMPLE": 4800.0}, date(2026, 6, 18)),
            ]
        )

    def test_does_not_write_gross_profit_when_cost_is_missing(self) -> None:
        sales_sheet = Mock(spec=SalesSheet)
        sales_sheet.write_gross_profit.return_value = GrossProfitWriteResult()
        sales_repository = Mock()
        asin_sales = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
        }
        sales_repository.get_daily_sales.return_value = asin_sales

        _backfill_one_day(sales_sheet, ["B00EXAMPLE"], sales_repository, "2026-06-18", {})

        sales_sheet.write_gross_profit.assert_called_once_with({}, date(2026, 6, 18))


class TestMainReadsCostsOnce:
    def test_reads_unit_costs_once_regardless_of_target_date_count(self) -> None:
        # 費用（販売手数料・FBA手数料・原価）は日付に依らないため、複数日をバックフィル
        # しても UnitCostReader.read() は1度しか呼ばれないことを確認する。
        with (
            patch.object(backfill_daily_sales, "load_dotenv"),
            patch.object(backfill_daily_sales, "SpApiAuthenticator") as authenticator_cls,
            patch.object(backfill_daily_sales, "SpApiSalesRepository") as repository_cls,
            patch.object(backfill_daily_sales, "_open_spreadsheet") as open_spreadsheet,
            patch.object(backfill_daily_sales, "SalesSheet") as sales_sheet_cls,
            patch.object(backfill_daily_sales, "UnitCostReader", spec=UnitCostReader) as reader_cls,
            patch.object(backfill_daily_sales.sys, "argv", ["backfill_daily_sales.py", "2026-06-18", "2026-06-19"]),
        ):
            repository_cls.return_value.get_daily_sales.return_value = {}
            sales_sheet_cls.return_value.get_asin_list.return_value = ["B00EXAMPLE"]
            reader_cls.return_value.read.return_value = {}

            backfill_daily_sales.main()

            reader_cls.return_value.read.assert_called_once_with()
            assert sales_sheet_cls.return_value.write_sales_nums.call_count == 2
