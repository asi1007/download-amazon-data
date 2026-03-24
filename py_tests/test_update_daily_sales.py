from unittest.mock import Mock
from py_src.usecases.update_daily_sales import UpdateDailySalesUseCase
from py_src.domain.value_objects.sales_info import SalesInfo


class TestUpdateDailySalesUseCase:
    def test_execute_writes_sales_and_prices(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE", "B00EXAMPLF"]
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
            "B00EXAMPLF": SalesInfo(unit_count=1, total_sales_amount=3000.0, order_count=1),
        }
        mock_price_repo = Mock()
        mock_price_repo.get_competitive_prices.return_value = {"B00EXAMPLE": 3200.0, "B00EXAMPLF": 1600.0}

        usecase = UpdateDailySalesUseCase(
            sales_sheet=mock_sheet, sales_repository=mock_sales_repo, price_repository=mock_price_repo,
        )
        usecase.execute()

        mock_sheet.get_asin_list.assert_called_once()
        mock_sales_repo.get_daily_sales.assert_called_once()
        mock_sheet.write_sales_nums.assert_called_once()
        mock_price_repo.get_competitive_prices.assert_called_once_with(["B00EXAMPLE", "B00EXAMPLF"])
        mock_sheet.write_prices.assert_called_once()

    def test_yesterday_date_range_is_valid(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {}
        mock_price_repo = Mock()
        mock_price_repo.get_competitive_prices.return_value = {}

        usecase = UpdateDailySalesUseCase(
            sales_sheet=mock_sheet, sales_repository=mock_sales_repo, price_repository=mock_price_repo,
        )
        usecase.execute()

        args = mock_sales_repo.get_daily_sales.call_args
        start_date = args[1].get("start_date", args[0][1] if len(args[0]) > 1 else None)
        end_date = args[1].get("end_date", args[0][2] if len(args[0]) > 2 else None)
        assert start_date.endswith("Z")
        assert end_date.endswith("Z")
        assert start_date < end_date

    def test_empty_asin_list(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {}
        mock_price_repo = Mock()
        mock_price_repo.get_competitive_prices.return_value = {}

        usecase = UpdateDailySalesUseCase(
            sales_sheet=mock_sheet, sales_repository=mock_sales_repo, price_repository=mock_price_repo,
        )
        usecase.execute()

        mock_sheet.write_sales_nums.assert_called_once_with({})
        mock_price_repo.get_competitive_prices.assert_called_once_with([])
