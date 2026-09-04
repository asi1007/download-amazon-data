import pytest
import requests
from unittest.mock import Mock, patch
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator
from py_src.infrastructure.api.sp_api_sales_repository import (
    SpApiSalesRepository,
    SalesFetchFailureError,
    SalesFetchDeadlineExceededError,
)


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


def _sales_payload(unit_count: int) -> Mock:
    return _make_response({
        "payload": [{
            "unitCount": unit_count,
            "totalSales": {"amount": unit_count * 3000.0},
            "orderCount": unit_count,
        }],
    })


def _asins(count: int) -> list[str]:
    return [f"B00EXAMP{i:02d}" for i in range(count)]


@patch("py_src.infrastructure.api.sp_api_sales_repository.time.sleep")
class TestPartialFailureTolerance:
    def test_one_failing_asin_does_not_abort_the_others(self, mock_sleep: Mock) -> None:
        auth = Mock()
        auth.request.side_effect = [
            requests.exceptions.ConnectionError("Connection reset by peer"),
            _sales_payload(1),
            _sales_payload(7),
        ]
        repo = SpApiSalesRepository(authenticator=auth)

        result = repo.get_daily_sales(
            ["B00EXAMPLE", "B00EXAMPLF"], "2026-08-07T15:00:00Z", "2026-08-08T15:00:00Z",
        )

        assert result["B00EXAMPLF"].unit_count == 1
        assert result["B00EXAMPLE"].unit_count == 7

    def test_asin_failing_every_pass_is_omitted_from_result(self, mock_sleep: Mock) -> None:
        asin_list = _asins(20)
        failing_asin = asin_list[0]

        def respond(method: str, url: str) -> Mock:
            if f"asin={failing_asin}" in url:
                raise requests.exceptions.ConnectionError("Connection reset by peer")
            return _sales_payload(3)

        auth = Mock()
        auth.request.side_effect = respond
        repo = SpApiSalesRepository(authenticator=auth)

        result = repo.get_daily_sales(asin_list, "2026-08-07T15:00:00Z", "2026-08-08T15:00:00Z")

        assert failing_asin not in result
        assert len(result) == 19

    def test_raises_when_failures_exceed_tolerance(self, mock_sleep: Mock) -> None:
        auth = Mock()
        auth.request.side_effect = requests.exceptions.ConnectionError("Connection reset by peer")
        repo = SpApiSalesRepository(authenticator=auth)

        with pytest.raises(SalesFetchFailureError):
            repo.get_daily_sales(_asins(20), "2026-08-07T15:00:00Z", "2026-08-08T15:00:00Z")

    def test_successful_asins_are_requested_once(self, mock_sleep: Mock) -> None:
        auth = Mock()
        auth.request.return_value = _sales_payload(2)
        repo = SpApiSalesRepository(authenticator=auth)

        repo.get_daily_sales(_asins(10), "2026-08-07T15:00:00Z", "2026-08-08T15:00:00Z")

        assert auth.request.call_count == 10


@patch("py_src.infrastructure.api.sp_api_sales_repository.time.sleep")
class TestDeadline:
    def test_deadline_not_passed_behaves_like_no_deadline(self, mock_sleep: Mock) -> None:
        auth = Mock()
        auth.request.return_value = _sales_payload(2)
        repo = SpApiSalesRepository(authenticator=auth)

        with patch(
            "py_src.infrastructure.api.sp_api_sales_repository.time.monotonic",
            return_value=0.0,
        ):
            result = repo.get_daily_sales(
                _asins(5), "2026-08-07T15:00:00Z", "2026-08-08T15:00:00Z", deadline_at=1000.0,
            )

        assert len(result) == 5
        assert auth.request.call_count == 5

    def test_deadline_already_passed_raises_before_any_request(self, mock_sleep: Mock) -> None:
        auth = Mock()
        auth.request.return_value = _sales_payload(2)
        repo = SpApiSalesRepository(authenticator=auth)

        with patch(
            "py_src.infrastructure.api.sp_api_sales_repository.time.monotonic",
            return_value=1000.0,
        ):
            with pytest.raises(SalesFetchDeadlineExceededError) as excinfo:
                repo.get_daily_sales(
                    _asins(5), "2026-08-07T15:00:00Z", "2026-08-08T15:00:00Z", deadline_at=0.0,
                )

        assert auth.request.call_count == 0
        assert excinfo.value.partial_results == {}

    def test_deadline_hit_partway_returns_partial_results_and_stops_requesting(
        self, mock_sleep: Mock
    ) -> None:
        auth = Mock()
        auth.request.return_value = _sales_payload(4)
        repo = SpApiSalesRepository(authenticator=auth)

        # monotonic() is polled once per ASIN before each attempt. Let the first two
        # through, then report the deadline as passed for the remaining three.
        monotonic_values = [0.0, 0.0, 100.0, 100.0, 100.0, 100.0]
        with patch(
            "py_src.infrastructure.api.sp_api_sales_repository.time.monotonic",
            side_effect=monotonic_values,
        ):
            with pytest.raises(SalesFetchDeadlineExceededError) as excinfo:
                repo.get_daily_sales(
                    _asins(5), "2026-08-07T15:00:00Z", "2026-08-08T15:00:00Z", deadline_at=50.0,
                )

        assert auth.request.call_count == 2
        assert len(excinfo.value.partial_results) == 2

    def test_deadline_does_not_apply_to_weekly_sales(self, mock_sleep: Mock) -> None:
        auth = Mock()
        auth.request.return_value = _sales_payload(2)
        repo = SpApiSalesRepository(authenticator=auth)

        with patch(
            "py_src.infrastructure.api.sp_api_sales_repository.time.monotonic",
            return_value=1000.0,
        ):
            result = repo.get_weekly_sales(
                _asins(3), "2026-08-07T15:00:00Z", "2026-08-08T15:00:00Z",
            )

        assert len(result) == 3
        assert auth.request.call_count == 3
