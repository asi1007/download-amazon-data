import pytest
from unittest.mock import Mock
from py_src.usecases.update_realtime_sales import UpdateRealtimeSalesUseCase
from py_src.domain.entities.order import Order, OrderItem


class TestUpdateRealtimeSalesUseCase:
    def test_aggregates_by_asin(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE", "B00EXAMPLF"]
        mock_repo = Mock()
        mock_repo.get_orders_with_items.return_value = [
            Order(
                order_id="503-001",
                order_status="Shipped",
                items=[
                    OrderItem(asin="B00EXAMPLE", quantity_ordered=2, item_price_amount=3000.0),
                    OrderItem(asin="B00EXAMPLF", quantity_ordered=1, item_price_amount=1500.0),
                ],
            ),
        ]
        mock_repo.get_prices.return_value = {}

        usecase = UpdateRealtimeSalesUseCase(sheet=mock_sheet, repository=mock_repo)
        usecase.execute()

        mock_sheet.write_realtime_sales.assert_called_once()
        sales_map = mock_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 2
        assert sales_map["B00EXAMPLE"].total_amount == 6000.0
        assert sales_map["B00EXAMPLF"].unit_count == 1

    def test_excludes_canceled_orders(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_repo = Mock()
        mock_repo.get_orders_with_items.return_value = [
            Order(
                order_id="503-001",
                order_status="Canceled",
                items=[OrderItem(asin="B00EXAMPLE", quantity_ordered=2, item_price_amount=3000.0)],
            ),
        ]
        mock_repo.get_prices.return_value = {}

        usecase = UpdateRealtimeSalesUseCase(sheet=mock_sheet, repository=mock_repo)
        usecase.execute()

        sales_map = mock_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 0

    def test_uses_current_price_for_zero_items(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_repo = Mock()
        mock_repo.get_orders_with_items.return_value = [
            Order(
                order_id="503-001",
                order_status="Pending",
                items=[OrderItem(asin="B00EXAMPLE", quantity_ordered=3, item_price_amount=0.0)],
            ),
        ]
        mock_repo.get_prices.return_value = {"B00EXAMPLE": 1500.0}

        usecase = UpdateRealtimeSalesUseCase(sheet=mock_sheet, repository=mock_repo)
        usecase.execute()

        sales_map = mock_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 3
        assert sales_map["B00EXAMPLE"].total_amount == 4500.0

    def test_raises_on_api_failure(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_repo = Mock()
        mock_repo.get_orders_with_items.side_effect = Exception("API error")

        usecase = UpdateRealtimeSalesUseCase(sheet=mock_sheet, repository=mock_repo)

        with pytest.raises(Exception, match="API error"):
            usecase.execute()

        mock_sheet.write_realtime_sales.assert_not_called()

    def test_handles_zero_orders(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_repo = Mock()
        mock_repo.get_orders_with_items.return_value = []
        mock_repo.get_prices.return_value = {}

        usecase = UpdateRealtimeSalesUseCase(sheet=mock_sheet, repository=mock_repo)
        usecase.execute()

        sales_map = mock_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 0
