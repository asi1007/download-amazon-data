from datetime import date, timezone, timedelta
from unittest.mock import Mock

from backfill_daily_sales import _backfill_one_day
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.infrastructure.sheets.sales_sheet import SalesSheet

JST = timezone(timedelta(hours=9))


class TestBackfillOneDay:
    def test_writes_through_write_sales_nums_with_target_date(self) -> None:
        sales_sheet = Mock(spec=SalesSheet)
        sales_repository = Mock()
        asin_sales = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
        }
        sales_repository.get_daily_sales.return_value = asin_sales

        _backfill_one_day(sales_sheet, ["B00EXAMPLE"], sales_repository, "2026-06-18")

        sales_sheet.write_sales_nums.assert_called_once_with(
            asin_sales, target_date=date(2026, 6, 18)
        )

    def test_does_not_reach_into_sales_sheet_privates(self) -> None:
        sales_sheet = Mock(spec=SalesSheet)
        sales_repository = Mock()
        sales_repository.get_daily_sales.return_value = {}

        _backfill_one_day(sales_sheet, ["B00EXAMPLE"], sales_repository, "2026-06-18")

        sales_sheet._resolve_column_for.assert_not_called()

    def test_fetches_the_requested_days_utc_window(self) -> None:
        sales_sheet = Mock(spec=SalesSheet)
        sales_repository = Mock()
        sales_repository.get_daily_sales.return_value = {}

        _backfill_one_day(sales_sheet, ["B00EXAMPLE"], sales_repository, "2026-06-18")

        args, _ = sales_repository.get_daily_sales.call_args
        asin_list, start_date_utc, end_date_utc = args
        assert asin_list == ["B00EXAMPLE"]
        assert start_date_utc == "2026-06-17T15:00:00Z"
        assert end_date_utc == "2026-06-18T15:00:00Z"
