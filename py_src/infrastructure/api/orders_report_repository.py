from __future__ import annotations
import gzip
import time
from datetime import date, datetime, timedelta, timezone
from typing import Callable

import requests

from py_src.infrastructure.api.sp_api_authenticator import (
    SpApiAuthenticator,
    SP_API_BASE,
    SP_API_REQUEST_TIMEOUT_SECONDS,
)

MARKETPLACE_JP = "A1VC38T7YXB528"
JST = timezone(timedelta(hours=9))
# 注文日ベースの全注文レポート。getOrders は 1分あたり1リクエストしか通らず、
# 14日分の約100ページに100分かかる（実際に 429 で落ちた）。こちらは
# 1リクエスト + ポーリングで同じ範囲を取れる
REPORT_TYPE = "GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL"
DEFAULT_POLL_INTERVAL_SECONDS = 15
DEFAULT_MAX_POLLS = 40
TERMINAL_FAILURE_STATUSES = ("CANCELLED", "FATAL")
ORDER_ID_COLUMN = "amazon-order-id"
PURCHASE_DATE_COLUMN = "purchase-date"


class ReportNotReadyError(RuntimeError):
    pass


class OrdersReportRepository:
    def __init__(
        self,
        authenticator: SpApiAuthenticator,
        downloader: Callable[[str], bytes] | None = None,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        max_polls: int = DEFAULT_MAX_POLLS,
    ) -> None:
        self._auth = authenticator
        self._download = downloader or _download
        self._poll_interval_seconds = poll_interval_seconds
        self._max_polls = max_polls

    def get_purchase_dates(self, start: date, end: date) -> dict[str, date]:
        report_id = self._request_report(start, end)
        document_id = self._await_document(report_id)
        return self._parse(self._fetch_document(document_id))

    def _request_report(self, start: date, end: date) -> str:
        body = {
            "reportType": REPORT_TYPE,
            "dataStartTime": _jst_midnight_iso(start),
            "dataEndTime": _jst_midnight_iso(end),
            "marketplaceIds": [MARKETPLACE_JP],
        }
        response = self._auth.request(
            "POST", f"{SP_API_BASE}/reports/2021-06-30/reports", json=body
        )
        return response.json()["reportId"]

    def _await_document(self, report_id: str) -> str:
        for _ in range(self._max_polls):
            time.sleep(self._poll_interval_seconds)
            payload = self._auth.request(
                "GET", f"{SP_API_BASE}/reports/2021-06-30/reports/{report_id}"
            ).json()
            status = payload.get("processingStatus")
            if status == "DONE":
                return payload["reportDocumentId"]
            if status in TERMINAL_FAILURE_STATUSES:
                raise ReportNotReadyError(f"注文レポートが {status} で終了しました")
        raise ReportNotReadyError(
            f"注文レポートが {self._max_polls} 回のポーリングで完了しませんでした"
        )

    def _fetch_document(self, document_id: str) -> str:
        payload = self._auth.request(
            "GET", f"{SP_API_BASE}/reports/2021-06-30/documents/{document_id}"
        ).json()
        raw = self._download(payload["url"])
        if payload.get("compressionAlgorithm") == "GZIP":
            raw = gzip.decompress(raw)
        # 日本のフラットファイルは cp932。utf-8 で読むと商品名で落ちる
        return raw.decode("cp932", errors="replace")

    @staticmethod
    def _parse(text: str) -> dict[str, date]:
        lines = text.splitlines()
        if not lines:
            return {}
        header = lines[0].split("\t")
        purchase_dates: dict[str, date] = {}
        for line in lines[1:]:
            row = dict(zip(header, line.split("\t")))
            order_id = row.get(ORDER_ID_COLUMN, "").strip()
            purchased = _to_jst_date(row.get(PURCHASE_DATE_COLUMN, ""))
            if order_id and purchased is not None:
                purchase_dates[order_id] = purchased
        return purchase_dates


def _jst_midnight_iso(target: date) -> str:
    return datetime(target.year, target.month, target.day, tzinfo=JST).isoformat()


def _to_jst_date(raw: str) -> date | None:
    try:
        return datetime.fromisoformat(raw.strip()).astimezone(JST).date()
    except ValueError:
        return None


def _download(url: str) -> bytes:
    return requests.get(url, timeout=SP_API_REQUEST_TIMEOUT_SECONDS).content
