from datetime import date
from unittest.mock import Mock, patch
from py_src.infrastructure.api.orders_repository import OrdersRepository
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator, SP_API_REQUEST_TIMEOUT_SECONDS


def _make_response(json_data: dict, status_code: int = 200) -> Mock:
    resp = Mock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = Mock()
    return resp


class TestOrdersRepository:
    def _create_repo(self, mock_session: Mock) -> OrdersRepository:
        mock_session.post.return_value = _make_response({"access_token": "test_access_token"})
        auth = SpApiAuthenticator(
            client_id="test_id",
            client_secret="test_secret",
            refresh_token="test_token",
            session=mock_session,
        )
        return OrdersRepository(authenticator=auth)

    @patch("py_src.infrastructure.api.orders_repository.time.sleep")
    def test_get_orders_with_items(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        orders_response = _make_response({
            "payload": {
                "Orders": [
                    {"AmazonOrderId": "503-001", "OrderStatus": "Shipped", "PurchaseDate": "2026-03-15T10:00:00Z"},
                ],
            },
        })
        items_response = _make_response({
            "payload": {
                "OrderItems": [
                    {"ASIN": "B00EXAMPLE", "QuantityOrdered": 2, "ItemPrice": {"CurrencyCode": "JPY", "Amount": "3000"}},
                ],
            },
        })
        mock_session.get.side_effect = [orders_response, items_response]
        repo = self._create_repo(mock_session)
        orders = repo.get_orders_with_items(created_after="2026-03-15T00:00:00Z")
        assert len(orders) == 1
        assert orders[0].order_id == "503-001"
        assert orders[0].items[0].asin == "B00EXAMPLE"

    @patch("py_src.infrastructure.api.orders_repository.time.sleep")
    def test_get_orders_with_items_empty(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        orders_response = _make_response({"payload": {"Orders": []}})
        mock_session.get.return_value = orders_response
        repo = self._create_repo(mock_session)
        orders = repo.get_orders_with_items(created_after="2026-03-15T00:00:00Z")
        assert len(orders) == 0

    @patch("py_src.infrastructure.api.orders_repository.time.sleep")
    def test_get_orders_with_items_pagination(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        page1_response = _make_response({
            "payload": {
                "Orders": [{"AmazonOrderId": "503-001", "OrderStatus": "Shipped", "PurchaseDate": "2026-03-15T10:00:00Z"}],
                "NextToken": "token123",
            },
        })
        page2_response = _make_response({
            "payload": {
                "Orders": [{"AmazonOrderId": "503-002", "OrderStatus": "Shipped", "PurchaseDate": "2026-03-15T11:00:00Z"}],
            },
        })
        items_response = _make_response({
            "payload": {
                "OrderItems": [{"ASIN": "B00EXAMPLE", "QuantityOrdered": 1, "ItemPrice": {"CurrencyCode": "JPY", "Amount": "1000"}}],
            },
        })
        mock_session.get.side_effect = [page1_response, page2_response, items_response, items_response]
        repo = self._create_repo(mock_session)
        orders = repo.get_orders_with_items(created_after="2026-03-15T00:00:00Z")
        assert len(orders) == 2

    @patch("py_src.infrastructure.api.orders_repository.time.sleep")
    def test_fetch_all_orders_passes_timeout(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        mock_session.get.return_value = _make_response({"payload": {"Orders": []}})
        repo = self._create_repo(mock_session)
        repo.get_orders_with_items(created_after="2026-03-15T00:00:00Z")
        assert mock_session.get.call_args.kwargs["timeout"] == SP_API_REQUEST_TIMEOUT_SECONDS

    @patch("py_src.infrastructure.api.orders_repository.time.sleep")
    def test_build_order_passes_timeout(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        orders_response = _make_response({
            "payload": {
                "Orders": [
                    {"AmazonOrderId": "503-001", "OrderStatus": "Shipped", "PurchaseDate": "2026-03-15T10:00:00Z"},
                ],
            },
        })
        items_response = _make_response({"payload": {"OrderItems": []}})
        mock_session.get.side_effect = [orders_response, items_response]
        repo = self._create_repo(mock_session)
        repo.get_orders_with_items(created_after="2026-03-15T00:00:00Z")
        assert mock_session.get.call_args.kwargs["timeout"] == SP_API_REQUEST_TIMEOUT_SECONDS

    def test_get_purchase_dates_maps_order_id_to_date(self) -> None:
        auth = Mock()
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"payload": {"Orders": [
            {"AmazonOrderId": "249-1", "PurchaseDate": "2026-09-01T10:00:00Z"},
            {"AmazonOrderId": "249-2", "PurchaseDate": "2026-09-02T23:30:00Z"},
        ]}}
        auth._session.get.return_value = response
        repository = OrdersRepository(authenticator=auth)

        dates = repository.get_purchase_dates("2026-09-01T00:00:00Z", "2026-09-03T00:00:00Z")

        assert dates == {"249-1": date(2026, 9, 1), "249-2": date(2026, 9, 3)}
