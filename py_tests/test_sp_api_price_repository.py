from unittest.mock import Mock, patch
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator
from py_src.infrastructure.api.sp_api_price_repository import SpApiPriceRepository


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


class TestSpApiPriceRepository:
    @patch("py_src.infrastructure.api.sp_api_price_repository.time.sleep")
    def test_get_competitive_prices(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        auth = _create_auth(mock_session)
        auth.authenticate()
        mock_session.request.return_value = _make_response({
            "payload": [{
                "ASIN": "B00EXAMPLE", "status": "Success",
                "Product": {"Offers": [{"BuyingPrice": {"ListingPrice": {"Amount": 3000.0}}}]},
            }],
        })
        repo = SpApiPriceRepository(authenticator=auth)
        prices = repo.get_competitive_prices(["B00EXAMPLE"])
        assert prices == {"B00EXAMPLE": 3000.0}

    @patch("py_src.infrastructure.api.sp_api_price_repository.time.sleep")
    def test_skips_failed_asin(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        auth = _create_auth(mock_session)
        auth.authenticate()
        mock_session.request.return_value = _make_response({
            "payload": [{"ASIN": "B00EXAMPLE", "status": "ClientError"}],
        })
        repo = SpApiPriceRepository(authenticator=auth)
        prices = repo.get_competitive_prices(["B00EXAMPLE"])
        assert prices == {}

    @patch("py_src.infrastructure.api.sp_api_price_repository.time.sleep")
    def test_batches_over_20_asins(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        auth = _create_auth(mock_session)
        auth.authenticate()
        asins = [f"B00EXAMPL{i:02d}" for i in range(25)]
        batch1 = [{"ASIN": a, "status": "Success", "Product": {"Offers": [{"BuyingPrice": {"ListingPrice": {"Amount": 1000.0}}}]}} for a in asins[:20]]
        batch2 = [{"ASIN": a, "status": "Success", "Product": {"Offers": [{"BuyingPrice": {"ListingPrice": {"Amount": 2000.0}}}]}} for a in asins[20:]]
        mock_session.request.side_effect = [
            _make_response({"payload": batch1}),
            _make_response({"payload": batch2}),
        ]
        repo = SpApiPriceRepository(authenticator=auth)
        prices = repo.get_competitive_prices(asins)
        assert len(prices) == 25
