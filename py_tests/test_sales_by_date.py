from datetime import date
from unittest.mock import Mock

from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator
from py_src.infrastructure.api.sp_api_sales_repository import SpApiSalesRepository


def _metrics_response(entries: list[dict]) -> Mock:
    response = Mock()
    response.json.return_value = {"payload": entries}
    return response


def _entry(day: str, units: int, sales: float) -> dict:
    return {
        "interval": f"{day}T00:00:00+09:00--{day}T23:59:59+09:00",
        "unitCount": units,
        "orderCount": units,
        "totalSales": {"amount": sales, "currencyCode": "JPY"},
    }


class TestGetSalesByDate:
    def test_returns_one_entry_per_day_not_just_the_first(self) -> None:
        # 既存の _parse_sales は payload[0] しか読まない。14日を1リクエストで
        # 取るにはすべての日を読む必要がある
        auth = Mock(spec=SpApiAuthenticator)
        auth.request.return_value = _metrics_response([
            _entry("2026-08-22", 3, 4500.0),
            _entry("2026-08-23", 0, 0.0),
            _entry("2026-08-24", 5, 7500.0),
        ])
        repository = SpApiSalesRepository(authenticator=auth)

        by_asin = repository.get_sales_by_date(
            ["B00EXAMPLE"], "2026-08-22T00:00:00+09:00", "2026-08-25T00:00:00+09:00"
        )

        assert by_asin["B00EXAMPLE"] == {
            date(2026, 8, 22): SalesInfo(unit_count=3, total_sales_amount=4500.0, order_count=3),
            date(2026, 8, 23): SalesInfo(unit_count=0, total_sales_amount=0.0, order_count=0),
            date(2026, 8, 24): SalesInfo(unit_count=5, total_sales_amount=7500.0, order_count=5),
        }

    def test_asin_that_fails_is_absent_rather_than_zero_filled(self) -> None:
        # 欠測を 0 と書くと販売0件と見分けがつかなくなる（既存の契約と同じ）
        import requests

        auth = Mock(spec=SpApiAuthenticator)
        auth.request.side_effect = requests.exceptions.ConnectionError("reset")
        repository = SpApiSalesRepository(authenticator=auth)

        by_asin = repository.get_sales_by_date(
            ["B00EXAMPLE"], "2026-08-22T00:00:00+09:00", "2026-08-25T00:00:00+09:00"
        )

        assert by_asin == {}

    def test_entry_without_a_parsable_interval_is_skipped(self) -> None:
        auth = Mock(spec=SpApiAuthenticator)
        auth.request.return_value = _metrics_response([
            {"unitCount": 3, "totalSales": {"amount": 100.0}},
            _entry("2026-08-24", 5, 7500.0),
        ])
        repository = SpApiSalesRepository(authenticator=auth)

        by_asin = repository.get_sales_by_date(["B00EXAMPLE"], "a", "b")

        assert list(by_asin["B00EXAMPLE"]) == [date(2026, 8, 24)]
