from py_src.domain.entities.order import Order, OrderItem


class TestOrderItem:
    def test_from_api_response(self) -> None:
        api_data: dict = {
            "ASIN": "B00EXAMPLE",
            "QuantityOrdered": 2,
            "ItemPrice": {"CurrencyCode": "JPY", "Amount": "3000"},
        }
        item = OrderItem.from_api_response(api_data)

        assert item.asin == "B00EXAMPLE"
        assert item.quantity_ordered == 2
        assert item.item_price_amount == 3000.0

    def test_missing_item_price(self) -> None:
        api_data: dict = {
            "ASIN": "B00EXAMPLE",
            "QuantityOrdered": 1,
            "ItemPrice": None,
        }
        item = OrderItem.from_api_response(api_data)

        assert item.item_price_amount == 0.0

    def test_no_item_price_key(self) -> None:
        api_data: dict = {
            "ASIN": "B00EXAMPLE",
            "QuantityOrdered": 1,
        }
        item = OrderItem.from_api_response(api_data)

        assert item.item_price_amount == 0.0


class TestOrder:
    def test_from_api_response(self) -> None:
        order_data: dict = {
            "AmazonOrderId": "503-001",
            "OrderStatus": "Shipped",
            "PurchaseDate": "2026-03-15T10:00:00Z",
        }
        items_data: list[dict] = [
            {"ASIN": "B00EXAMPLE", "QuantityOrdered": 2, "ItemPrice": {"CurrencyCode": "JPY", "Amount": "3000"}},
        ]
        order = Order.from_api_response(order_data, items_data)

        assert order.order_id == "503-001"
        assert order.order_status == "Shipped"
        assert len(order.items) == 1

    def test_is_canceled_true(self) -> None:
        order = Order(order_id="503-001", order_status="Canceled", items=[])

        assert order.is_canceled is True

    def test_is_canceled_false(self) -> None:
        order = Order(order_id="503-001", order_status="Shipped", items=[])

        assert order.is_canceled is False
