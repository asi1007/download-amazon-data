from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

import pytest

from py_src.usecases.update_today_sales import UpdateTodaySalesUseCase, HOURLY_SALES_DEADLINE_SECONDS
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.infrastructure.api.sp_api_sales_repository import SalesFetchDeadlineExceededError

JST = timezone(timedelta(hours=9))


class TestUpdateTodaySalesUseCase:
    def test_execute_writes_sales_only(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE", "B00EXAMPLF"]
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
            "B00EXAMPLF": SalesInfo(unit_count=1, total_sales_amount=3000.0, order_count=1),
        }

        usecase = UpdateTodaySalesUseCase(
            sales_sheet=mock_sheet, sales_repository=mock_sales_repo,
        )
        usecase.execute()

        mock_sheet.get_asin_list.assert_called_once()
        mock_sales_repo.get_daily_sales.assert_called_once()
        mock_sheet.write_sales_nums.assert_called_once()

    def test_does_not_write_prices(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {}

        usecase = UpdateTodaySalesUseCase(
            sales_sheet=mock_sheet, sales_repository=mock_sales_repo,
        )
        usecase.execute()

        mock_sheet.write_prices.assert_not_called()

    def test_today_date_range_is_valid(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {}

        usecase = UpdateTodaySalesUseCase(
            sales_sheet=mock_sheet, sales_repository=mock_sales_repo,
        )
        usecase.execute()

        args = mock_sales_repo.get_daily_sales.call_args
        start_date = args.kwargs["start_date"]
        end_date = args.kwargs["end_date"]
        assert start_date.endswith("Z")
        assert end_date.endswith("Z")
        assert start_date < end_date

    def test_write_sales_nums_receives_todays_date(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {}

        usecase = UpdateTodaySalesUseCase(
            sales_sheet=mock_sheet, sales_repository=mock_sales_repo,
        )
        usecase.execute()

        expected_today = datetime.now(JST).date()
        _, kwargs = mock_sheet.write_sales_nums.call_args
        assert kwargs["target_date"] == expected_today

    def test_passes_a_deadline_bounded_by_the_hourly_budget(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {}

        usecase = UpdateTodaySalesUseCase(
            sales_sheet=mock_sheet, sales_repository=mock_sales_repo,
        )
        with patch(
            "py_src.usecases.update_today_sales.time.monotonic", return_value=1_000.0,
        ):
            usecase.execute()

        _, kwargs = mock_sales_repo.get_daily_sales.call_args
        assert kwargs["deadline_at"] == 1_000.0 + HOURLY_SALES_DEADLINE_SECONDS

    def test_deadline_exceeded_writes_partial_results_then_reraises(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE", "B00EXAMPLF", "B00EXAMPLG"]
        partial_results = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
        }
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.side_effect = SalesFetchDeadlineExceededError(
            partial_results=partial_results, attempted_count=1, total_count=3,
        )

        usecase = UpdateTodaySalesUseCase(
            sales_sheet=mock_sheet, sales_repository=mock_sales_repo,
        )
        with pytest.raises(SalesFetchDeadlineExceededError):
            usecase.execute()

        mock_sheet.write_sales_nums.assert_called_once()
        args, kwargs = mock_sheet.write_sales_nums.call_args
        assert args[0] == partial_results
        assert kwargs["target_date"] == datetime.now(JST).date()
