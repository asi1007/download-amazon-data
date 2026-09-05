from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

import pytest

from py_src.usecases.update_today_sales import UpdateTodaySalesUseCase, HOURLY_SALES_DEADLINE_SECONDS
from py_src.domain.repositories.sales_repository import SalesRepository
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.domain.value_objects.unit_costs import UnitCosts
from py_src.infrastructure.api.sp_api_sales_repository import SalesFetchDeadlineExceededError
from py_src.infrastructure.sheets.sales_sheet import SalesSheet
from py_src.infrastructure.sheets.unit_cost_reader import UnitCostReader

JST = timezone(timedelta(hours=9))


def _no_cost_reader() -> Mock:
    cost_reader = Mock(spec=UnitCostReader)
    cost_reader.read.return_value = {}
    return cost_reader


class TestUpdateTodaySalesUseCase:
    def test_execute_writes_sales_only(self) -> None:
        mock_sheet = Mock(spec=SalesSheet)
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE", "B00EXAMPLF"]
        mock_sales_repo = Mock(spec=SalesRepository)
        mock_sales_repo.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
            "B00EXAMPLF": SalesInfo(unit_count=1, total_sales_amount=3000.0, order_count=1),
        }

        usecase = UpdateTodaySalesUseCase(
            sales_sheet=mock_sheet,
            sales_repository=mock_sales_repo,
            cost_reader=_no_cost_reader(),
        )
        usecase.execute()

        mock_sheet.get_asin_list.assert_called_once()
        mock_sales_repo.get_daily_sales.assert_called_once()
        mock_sheet.write_sales_nums.assert_called_once()

    def test_does_not_write_prices(self) -> None:
        mock_sheet = Mock(spec=SalesSheet)
        mock_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock(spec=SalesRepository)
        mock_sales_repo.get_daily_sales.return_value = {}

        usecase = UpdateTodaySalesUseCase(
            sales_sheet=mock_sheet,
            sales_repository=mock_sales_repo,
            cost_reader=_no_cost_reader(),
        )
        usecase.execute()

        mock_sheet.write_prices.assert_not_called()

    def test_today_date_range_is_valid(self) -> None:
        mock_sheet = Mock(spec=SalesSheet)
        mock_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock(spec=SalesRepository)
        mock_sales_repo.get_daily_sales.return_value = {}

        usecase = UpdateTodaySalesUseCase(
            sales_sheet=mock_sheet,
            sales_repository=mock_sales_repo,
            cost_reader=_no_cost_reader(),
        )
        usecase.execute()

        args = mock_sales_repo.get_daily_sales.call_args
        start_date = args.kwargs["start_date"]
        end_date = args.kwargs["end_date"]
        assert start_date.endswith("Z")
        assert end_date.endswith("Z")
        assert start_date < end_date

    def test_write_sales_nums_receives_todays_date(self) -> None:
        mock_sheet = Mock(spec=SalesSheet)
        mock_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock(spec=SalesRepository)
        mock_sales_repo.get_daily_sales.return_value = {}

        usecase = UpdateTodaySalesUseCase(
            sales_sheet=mock_sheet,
            sales_repository=mock_sales_repo,
            cost_reader=_no_cost_reader(),
        )
        usecase.execute()

        expected_today = datetime.now(JST).date()
        _, kwargs = mock_sheet.write_sales_nums.call_args
        assert kwargs["target_date"] == expected_today

    def test_passes_a_deadline_bounded_by_the_hourly_budget(self) -> None:
        mock_sheet = Mock(spec=SalesSheet)
        mock_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock(spec=SalesRepository)
        mock_sales_repo.get_daily_sales.return_value = {}

        usecase = UpdateTodaySalesUseCase(
            sales_sheet=mock_sheet,
            sales_repository=mock_sales_repo,
            cost_reader=_no_cost_reader(),
        )
        with patch(
            "py_src.usecases.update_today_sales.time.monotonic", return_value=1_000.0,
        ):
            usecase.execute()

        _, kwargs = mock_sales_repo.get_daily_sales.call_args
        assert kwargs["deadline_at"] == 1_000.0 + HOURLY_SALES_DEADLINE_SECONDS

    def test_deadline_exceeded_writes_partial_results_then_reraises(self) -> None:
        mock_sheet = Mock(spec=SalesSheet)
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE", "B00EXAMPLF", "B00EXAMPLG"]
        partial_results = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
        }
        mock_sales_repo = Mock(spec=SalesRepository)
        mock_sales_repo.get_daily_sales.side_effect = SalesFetchDeadlineExceededError(
            partial_results=partial_results, attempted_count=1, total_count=3,
        )

        usecase = UpdateTodaySalesUseCase(
            sales_sheet=mock_sheet,
            sales_repository=mock_sales_repo,
            cost_reader=_no_cost_reader(),
        )
        with pytest.raises(SalesFetchDeadlineExceededError):
            usecase.execute()

        mock_sheet.write_sales_nums.assert_called_once()
        args, kwargs = mock_sheet.write_sales_nums.call_args
        assert args[0] == partial_results
        assert kwargs["target_date"] == datetime.now(JST).date()
        assert kwargs["include_total"] is False

    def test_deadline_exceeded_writes_gross_profit_for_partial_results(self) -> None:
        mock_sheet = Mock(spec=SalesSheet)
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE", "B00EXAMPLF"]
        partial_results = {
            "B00EXAMPLE": SalesInfo(unit_count=3, total_sales_amount=3000.0),
        }
        mock_sales_repo = Mock(spec=SalesRepository)
        mock_sales_repo.get_daily_sales.side_effect = SalesFetchDeadlineExceededError(
            partial_results=partial_results, attempted_count=1, total_count=2,
        )
        cost_reader = Mock(spec=UnitCostReader)
        cost_reader.read.return_value = {
            "B00EXAMPLE": UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=200.0)
        }

        usecase = UpdateTodaySalesUseCase(
            sales_sheet=mock_sheet, sales_repository=mock_sales_repo, cost_reader=cost_reader,
        )
        with pytest.raises(SalesFetchDeadlineExceededError):
            usecase.execute()

        mock_sheet.write_gross_profit.assert_called_once_with(
            {"B00EXAMPLE": 1200.0}, datetime.now(JST).date()
        )

    def test_writes_estimated_gross_profit_after_units(self) -> None:
        sales_sheet = Mock(spec=SalesSheet)
        sales_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        cost_reader = Mock(spec=UnitCostReader)
        cost_reader.read.return_value = {
            "B00EXAMPLE": UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=200.0)
        }
        sales_repository = Mock(spec=SalesRepository)
        sales_repository.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=3, total_sales_amount=3000.0)
        }
        usecase = UpdateTodaySalesUseCase(
            sales_sheet=sales_sheet,
            sales_repository=sales_repository,
            cost_reader=cost_reader,
        )

        usecase.execute()

        written = sales_sheet.write_gross_profit.call_args[0][0]
        assert written == {"B00EXAMPLE": 1200.0}

    def test_asin_with_missing_costs_is_blanked_rather_than_left_stale(self) -> None:
        sales_sheet = Mock(spec=SalesSheet)
        sales_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        cost_reader = Mock(spec=UnitCostReader)
        cost_reader.read.return_value = {"B00EXAMPLE": UnitCosts(None, 300.0, 200.0)}
        sales_repository = Mock(spec=SalesRepository)
        sales_repository.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=3, total_sales_amount=3000.0)
        }
        usecase = UpdateTodaySalesUseCase(
            sales_sheet=sales_sheet,
            sales_repository=sales_repository,
            cost_reader=cost_reader,
        )

        usecase.execute()

        # 書かずに飛ばすと前回の見積が黄色のまま残り、最新の数字に見える
        assert sales_sheet.write_gross_profit.call_args[0][0] == {"B00EXAMPLE": None}

    def test_units_are_written_before_profit(self) -> None:
        # 粗利益は売上個数と同じ列に書くので、列を解決する write_sales_nums が先
        sales_sheet = Mock(spec=SalesSheet)
        sales_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        cost_reader = Mock(spec=UnitCostReader)
        cost_reader.read.return_value = {
            "B00EXAMPLE": UnitCosts(selling_fee=1.0, fba_fee=1.0, cost=1.0)
        }
        sales_repository = Mock(spec=SalesRepository)
        sales_repository.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=1, total_sales_amount=10.0)
        }
        calls: list[str] = []
        sales_sheet.write_sales_nums.side_effect = lambda *a, **k: calls.append("units")
        sales_sheet.write_gross_profit.side_effect = lambda *a, **k: calls.append("profit")
        usecase = UpdateTodaySalesUseCase(
            sales_sheet=sales_sheet,
            sales_repository=sales_repository,
            cost_reader=cost_reader,
        )

        usecase.execute()

        assert calls == ["units", "profit"]
