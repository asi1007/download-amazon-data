import gzip
import json
from datetime import date
from unittest.mock import Mock

import pytest

from sales_data.domain.value_objects.ad_metrics import AdMetrics
from py_src.domain.value_objects.ads_credentials import AdsCredentials
from py_src.infrastructure.api.ads_units_repository import (
    AdsReportError,
    AdsUnitsRepository,
)

CREDENTIALS = AdsCredentials(
    client_id="id", client_secret="secret", refresh_token="token",
    profile_id="123", region="FE",
)


def _response(status_code: int = 200, payload: dict | None = None, content: bytes = b"") -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload or {}
    response.content = content
    response.text = json.dumps(payload or {})
    return response


def _gzipped(rows: list[dict]) -> bytes:
    return gzip.compress(json.dumps(rows).encode())


class TestAdsUnitsRepository:
    def test_returns_units_by_date_and_asin(self) -> None:
        rows = [
            {"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D", "unitsSoldSameSku14d": 3},
            {"date": "2026-09-01", "advertisedAsin": "B0GQPRJNPF", "unitsSoldSameSku14d": 0},
            {"date": "2026-09-02", "advertisedAsin": "B0HH5DR13D", "unitsSoldSameSku14d": 5},
        ]
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.side_effect = [
            _response(payload={"status": "PENDING"}),
            _response(payload={"status": "COMPLETED", "url": "https://example.com/report.gz"}),
            _response(content=_gzipped(rows)),
        ]
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        metrics = repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 2))

        assert metrics == {
            "2026-09-01": {
                "B0HH5DR13D": AdMetrics(units=3, cost=0.0),
                "B0GQPRJNPF": AdMetrics(units=0, cost=0.0),
            },
            "2026-09-02": {"B0HH5DR13D": AdMetrics(units=5, cost=0.0)},
        }

    def test_report_creation_failure_raises(self) -> None:
        session = Mock()
        session.post.return_value = _response(status_code=422, payload={"detail": "bad column"})
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        with pytest.raises(AdsReportError, match="422"):
            repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 2))

    def test_report_failure_status_raises(self) -> None:
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.return_value = _response(payload={"status": "FAILURE"})
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        with pytest.raises(AdsReportError, match="FAILURE"):
            repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 2))

    def test_polling_timeout_raises(self) -> None:
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.return_value = _response(payload={"status": "PROCESSING"})
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0, max_polls=3,
        )
        repository._access_token = "cached"  # noqa: SLF001

        with pytest.raises(AdsReportError, match="タイムアウト"):
            repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 2))

    def test_rows_without_asin_or_date_are_skipped(self) -> None:
        rows = [
            {"date": "2026-09-01", "advertisedAsin": "", "unitsSoldSameSku14d": 3},
            {"date": "", "advertisedAsin": "B0HH5DR13D", "unitsSoldSameSku14d": 3},
            {"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D", "unitsSoldSameSku14d": 2},
        ]
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.side_effect = [
            _response(payload={"status": "COMPLETED", "url": "https://example.com/r.gz"}),
            _response(content=_gzipped(rows)),
        ]
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        metrics = repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 1))

        assert metrics == {"2026-09-01": {"B0HH5DR13D": AdMetrics(units=2, cost=0.0)}}

    def test_same_asin_appearing_twice_is_summed(self) -> None:
        rows = [
            {"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D", "unitsSoldSameSku14d": 2},
            {"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D", "unitsSoldSameSku14d": 1},
        ]
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.side_effect = [
            _response(payload={"status": "COMPLETED", "url": "https://example.com/r.gz"}),
            _response(content=_gzipped(rows)),
        ]
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        metrics = repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 1))

        assert metrics == {"2026-09-01": {"B0HH5DR13D": AdMetrics(units=3, cost=0.0)}}

    def test_token_fetch_success_and_caching(self) -> None:
        rows = [{"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D", "unitsSoldSameSku14d": 1}]
        session = Mock()
        session.post.side_effect = [
            _response(payload={"access_token": "token123"}),  # Token response
            _response(payload={"reportId": "r1"}),  # Report creation
        ]
        session.get.side_effect = [
            _response(payload={"status": "COMPLETED", "url": "https://example.com/r.gz"}),
            _response(content=_gzipped(rows)),
        ]
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )

        metrics = repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 1))

        assert metrics == {"2026-09-01": {"B0HH5DR13D": AdMetrics(units=1, cost=0.0)}}
        assert repository._access_token == "token123"  # noqa: SLF001
        assert session.post.call_count == 2  # Token + Report

    def test_token_fetch_failure_raises(self) -> None:
        session = Mock()
        session.post.return_value = _response(status_code=401, payload={"error": "invalid_client"})
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )

        with pytest.raises(AdsReportError, match="401"):
            repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 1))

    def test_token_response_missing_access_token_raises(self) -> None:
        session = Mock()
        session.post.return_value = _response(payload={})  # Missing access_token
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )

        with pytest.raises(AdsReportError, match="access_token がありません"):
            repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 1))

    def test_poll_http_error_raises_instead_of_timing_out(self) -> None:
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.return_value = _response(status_code=401, payload={"error": "invalid_client"})
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0, max_polls=3,
        )
        repository._access_token = "cached"  # noqa: SLF001

        with pytest.raises(AdsReportError, match="401"):
            repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 2))

        assert session.get.call_count == 1

    def test_download_url_failure_raises(self) -> None:
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.side_effect = [
            _response(payload={"status": "COMPLETED", "url": "https://example.com/r.gz"}),
            _response(status_code=403),  # Presigned URL expired
        ]
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        with pytest.raises(AdsReportError, match="403"):
            repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 1))

    def test_returns_units_and_cost_by_date_and_asin(self) -> None:
        rows = [
            {"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D",
             "unitsSoldSameSku14d": 3, "cost": 120.5},
            {"date": "2026-09-01", "advertisedAsin": "B0GQPRJNPF",
             "unitsSoldSameSku14d": 0, "cost": 40.0},
        ]
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.side_effect = [
            _response(payload={"status": "COMPLETED", "url": "https://example.com/r.gz"}),
            _response(content=_gzipped(rows)),
        ]
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        metrics = repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 1))

        assert metrics["2026-09-01"]["B0HH5DR13D"] == AdMetrics(units=3, cost=120.5)
        assert metrics["2026-09-01"]["B0GQPRJNPF"] == AdMetrics(units=0, cost=40.0)

    def test_same_asin_appearing_twice_sums_both_units_and_cost(self) -> None:
        rows = [
            {"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D",
             "unitsSoldSameSku14d": 2, "cost": 100.0},
            {"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D",
             "unitsSoldSameSku14d": 1, "cost": 50.5},
        ]
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.side_effect = [
            _response(payload={"status": "COMPLETED", "url": "https://example.com/r.gz"}),
            _response(content=_gzipped(rows)),
        ]
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        metrics = repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 1))

        assert metrics["2026-09-01"]["B0HH5DR13D"] == AdMetrics(units=3, cost=150.5)

    def test_cost_column_is_requested(self) -> None:
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.side_effect = [
            _response(payload={"status": "COMPLETED", "url": "https://example.com/r.gz"}),
            _response(content=_gzipped([])),
        ]
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 1))

        body = session.post.call_args.kwargs["json"]
        assert "cost" in body["configuration"]["columns"]
