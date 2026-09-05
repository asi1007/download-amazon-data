from datetime import date
from unittest.mock import Mock

import pytest

from py_src.infrastructure.api.orders_report_repository import (
    OrdersReportRepository,
    ReportNotReadyError,
)
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator

HEADER = "amazon-order-id\tpurchase-date\tsku\tquantity\titem-status"
ROWS = [
    "503-1\t2026-09-03T10:15:00+09:00\tSKU-A\t1\tShipped",
    "503-2\t2026-09-03T23:30:00+00:00\tSKU-B\t2\tShipped",
    "503-3\t\tSKU-C\t1\tShipped",
]
TSV = ("\n".join([HEADER] + ROWS)).encode("cp932")


def _response(payload: dict) -> Mock:
    response = Mock()
    response.json.return_value = payload
    return response


def _auth(statuses: list[str]) -> Mock:
    auth = Mock(spec=SpApiAuthenticator)
    responses = [_response({"reportId": "R1"})]
    responses += [
        _response({"processingStatus": status, "reportDocumentId": "D1"})
        for status in statuses
    ]
    responses.append(_response({"url": "https://example.com/doc"}))
    auth.request.side_effect = responses
    return auth


def _repository(auth: Mock, body: bytes = TSV) -> OrdersReportRepository:
    downloader = Mock(return_value=body)
    return OrdersReportRepository(
        authenticator=auth, downloader=downloader, poll_interval_seconds=0
    )


class TestOrdersReportRepository:
    def test_maps_order_id_to_its_jst_purchase_date(self) -> None:
        repository = _repository(_auth(["DONE"]))

        dates = repository.get_purchase_dates(date(2026, 9, 3), date(2026, 9, 4))

        # 2件目は UTC 23:30 なので JST では翌日
        assert dates == {"503-1": date(2026, 9, 3), "503-2": date(2026, 9, 4)}

    def test_row_without_a_purchase_date_is_skipped(self) -> None:
        repository = _repository(_auth(["DONE"]))

        assert "503-3" not in repository.get_purchase_dates(date(2026, 9, 3), date(2026, 9, 4))

    def test_polls_until_the_report_is_done(self) -> None:
        auth = _auth(["IN_QUEUE", "IN_PROGRESS", "DONE"])
        repository = _repository(auth)

        repository.get_purchase_dates(date(2026, 9, 3), date(2026, 9, 4))

        assert auth.request.call_count == 5

    def test_raises_when_the_report_is_cancelled(self) -> None:
        repository = _repository(_auth(["CANCELLED"]))

        with pytest.raises(ReportNotReadyError):
            repository.get_purchase_dates(date(2026, 9, 3), date(2026, 9, 4))

    def test_raises_when_polling_runs_out(self) -> None:
        auth = Mock(spec=SpApiAuthenticator)
        auth.request.side_effect = [_response({"reportId": "R1"})] + [
            _response({"processingStatus": "IN_PROGRESS"}) for _ in range(10)
        ]
        repository = OrdersReportRepository(
            authenticator=auth, downloader=Mock(), poll_interval_seconds=0, max_polls=3
        )

        with pytest.raises(ReportNotReadyError):
            repository.get_purchase_dates(date(2026, 9, 3), date(2026, 9, 4))

    def test_decompresses_a_gzip_document(self) -> None:
        import gzip

        auth = Mock(spec=SpApiAuthenticator)
        auth.request.side_effect = [
            _response({"reportId": "R1"}),
            _response({"processingStatus": "DONE", "reportDocumentId": "D1"}),
            _response({"url": "https://example.com/doc", "compressionAlgorithm": "GZIP"}),
        ]
        repository = _repository(auth, body=gzip.compress(TSV))

        dates = repository.get_purchase_dates(date(2026, 9, 3), date(2026, 9, 4))

        assert dates["503-1"] == date(2026, 9, 3)

    def test_requests_the_window_in_jst(self) -> None:
        auth = _auth(["DONE"])
        _repository(auth).get_purchase_dates(date(2026, 9, 3), date(2026, 9, 4))

        body = auth.request.call_args_list[0].kwargs["json"]
        assert body["dataStartTime"] == "2026-09-03T00:00:00+09:00"
        assert body["dataEndTime"] == "2026-09-04T00:00:00+09:00"
