import pytest
from unittest.mock import Mock
from py_src.usecases.update_realtime_sales import UpdateRealtimeSalesUseCase
from py_src.domain.value_objects.sales_info import SalesInfo


class TestUpdateRealtimeSalesUseCase:
    def test_calculates_amount_from_unit_count_and_selling_price(self) -> None:
        mock_realtime_sheet = Mock()
        mock_realtime_sheet.get_asin_list.return_value = ["B00EXAMPLE", "B00EXAMPLF"]
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=3, total_sales_amount=900.0, order_count=2),
            "B00EXAMPLF": SalesInfo(unit_count=1, total_sales_amount=400.0, order_count=1),
        }
        mock_sales_sheet = Mock()
        mock_sales_sheet.get_selling_prices.return_value = {
            "B00EXAMPLE": 500.0,
            "B00EXAMPLF": 800.0,
        }
        usecase = UpdateRealtimeSalesUseCase(
            realtime_sheet=mock_realtime_sheet,
            sales_repository=mock_sales_repo,
            sales_sheet=mock_sales_sheet,
        )
        usecase.execute()

        sales_map = mock_realtime_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 3
        assert sales_map["B00EXAMPLE"].total_amount == 1500.0
        assert sales_map["B00EXAMPLF"].unit_count == 1
        assert sales_map["B00EXAMPLF"].total_amount == 800.0

    def test_zero_sales(self) -> None:
        mock_realtime_sheet = Mock()
        mock_realtime_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=0, total_sales_amount=0.0, order_count=0),
        }
        mock_sales_sheet = Mock()
        mock_sales_sheet.get_selling_prices.return_value = {"B00EXAMPLE": 500.0}
        usecase = UpdateRealtimeSalesUseCase(
            realtime_sheet=mock_realtime_sheet,
            sales_repository=mock_sales_repo,
            sales_sheet=mock_sales_sheet,
        )
        usecase.execute()

        sales_map = mock_realtime_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 0
        assert sales_map["B00EXAMPLE"].total_amount == 0.0

    def test_missing_selling_price_defaults_to_zero(self) -> None:
        mock_realtime_sheet = Mock()
        mock_realtime_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=5, total_sales_amount=1000.0, order_count=3),
        }
        mock_sales_sheet = Mock()
        mock_sales_sheet.get_selling_prices.return_value = {}
        usecase = UpdateRealtimeSalesUseCase(
            realtime_sheet=mock_realtime_sheet,
            sales_repository=mock_sales_repo,
            sales_sheet=mock_sales_sheet,
        )
        usecase.execute()

        sales_map = mock_realtime_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 5
        assert sales_map["B00EXAMPLE"].total_amount == 0.0

    def test_works_without_sales_sheet(self) -> None:
        mock_realtime_sheet = Mock()
        mock_realtime_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=5, total_sales_amount=1000.0, order_count=3),
        }
        usecase = UpdateRealtimeSalesUseCase(
            realtime_sheet=mock_realtime_sheet,
            sales_repository=mock_sales_repo,
        )
        usecase.execute()

        sales_map = mock_realtime_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 5
        assert sales_map["B00EXAMPLE"].total_amount == 0.0
