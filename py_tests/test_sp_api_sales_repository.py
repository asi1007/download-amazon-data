from unittest.mock import Mock, patch
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator
from py_src.infrastructure.api.sp_api_sales_repository import SpApiSalesRepository


def _make_response(json_data: dict, status_code: int = 200) -> Mock:
    resp = Mock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = Mock()
    return resp


def _create_auth(mock_session: Mock) -> SpApiAuthenticator:
    mock_session.post.return_value = _make_response({"access_token": "token"})
    return SpApiAuthenticator(
        client_id="id", client_secret="secret", refresh_token="refresh", session=mock_session,
    )


class TestSpApiSalesRepository:
    @patch("py_src.infrastructure.api.sp_api_sales_repository.time.sleep")
    def test_get_daily_sales_single_asin(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        auth = _create_auth(mock_session)
        auth.authenticate()
        mock_session.request.return_value = _make_response({
            "payload": [{"unitCount": 5, "totalSales": {"currencyCode": "JPY", "amount": 15000.0}, "orderCount": 3}],
        })
        repo = SpApiSalesRepository(authenticator=auth)
        result = repo.get_daily_sales(["B00EXAMPLE"], "2026-03-23T15:00:00Z", "2026-03-24T15:00:00Z")
        assert result["B00EXAMPLE"].unit_count == 5
        assert result["B00EXAMPLE"].total_sales_amount == 15000.0
        assert result["B00EXAMPLE"].order_count == 3

    @patch("py_src.infrastructure.api.sp_api_sales_repository.time.sleep")
    def test_get_daily_sales_empty_payload(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        auth = _create_auth(mock_session)
        auth.authenticate()
        mock_session.request.return_value = _make_response({"payload": []})
        repo = SpApiSalesRepository(authenticator=auth)
        result = repo.get_daily_sales(["B00EXAMPLE"], "2026-03-23T15:00:00Z", "2026-03-24T15:00:00Z")
        assert result["B00EXAMPLE"].unit_count == 0
        assert result["B00EXAMPLE"].total_sales_amount == 0.0

    @patch("py_src.infrastructure.api.sp_api_sales_repository.time.sleep")
    def test_get_daily_sales_multiple_asins(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        auth = _create_auth(mock_session)
        auth.authenticate()
        mock_session.request.side_effect = [
            _make_response({"payload": [{"unitCount": 2, "totalSales": {"amount": 6000.0}, "orderCount": 1}]}),
            _make_response({"payload": [{"unitCount": 1, "totalSales": {"amount": 3000.0}, "orderCount": 1}]}),
        ]
        repo = SpApiSalesRepository(authenticator=auth)
        result = repo.get_daily_sales(["B00EXAMPLE", "B00EXAMPLF"], "2026-03-23T15:00:00Z", "2026-03-24T15:00:00Z")
        assert result["B00EXAMPLE"].unit_count == 2
        assert result["B00EXAMPLF"].unit_count == 1

    @patch("py_src.infrastructure.api.sp_api_sales_repository.time.sleep")
    def test_get_weekly_sales_uses_week_granularity(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        auth = _create_auth(mock_session)
        auth.authenticate()
        mock_session.request.return_value = _make_response({
            "payload": [{"unitCount": 50, "totalSales": {"amount": 150000.0}, "orderCount": 30}],
        })
        repo = SpApiSalesRepository(authenticator=auth)
        result = repo.get_weekly_sales(["B00EXAMPLE"], "2026-04-19T15:00:00Z", "2026-04-26T15:00:00Z")
        called_url = mock_session.request.call_args[0][1]
        assert "granularity=Week" in called_url
        assert result["B00EXAMPLE"].unit_count == 50
        assert result["B00EXAMPLE"].total_sales_amount == 150000.0
        assert result["B00EXAMPLE"].order_count == 30

    @patch("py_src.infrastructure.api.sp_api_sales_repository.time.sleep")
    def test_get_weekly_sales_multiple_asins(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        auth = _create_auth(mock_session)
        auth.authenticate()
        mock_session.request.side_effect = [
            _make_response({"payload": [{"unitCount": 10, "totalSales": {"amount": 30000.0}, "orderCount": 5}]}),
            _make_response({"payload": []}),
        ]
        repo = SpApiSalesRepository(authenticator=auth)
        result = repo.get_weekly_sales(["B00EXAMPLE", "B00EXAMPLF"], "2026-04-19T15:00:00Z", "2026-04-26T15:00:00Z")
        assert result["B00EXAMPLE"].unit_count == 10
        assert result["B00EXAMPLF"].unit_count == 0
