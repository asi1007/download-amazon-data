from __future__ import annotations
import gzip
import json
import time
from datetime import date
from typing import Any, Protocol

import requests

from py_src.domain.value_objects.ads_credentials import AdsCredentials

TOKEN_URL = "https://api.amazon.com/auth/o2/token"
REPORT_MEDIA = "application/vnd.createasyncreportrequest.v3+json"
REPORT_TYPE_ID = "spAdvertisedProduct"
UNITS_COLUMN = "unitsSoldSameSku14d"
COLUMNS = ["date", "advertisedAsin", UNITS_COLUMN]
TIMEOUT_SECONDS = 90
DOWNLOAD_TIMEOUT_SECONDS = 180
DEFAULT_POLL_INTERVAL_SECONDS = 12
DEFAULT_MAX_POLLS = 40


class AdsReportError(RuntimeError):
    pass


class HttpSession(Protocol):
    def post(self, url: str, **kwargs: Any) -> Any: ...
    def get(self, url: str, **kwargs: Any) -> Any: ...


class AdsUnitsRepository:
    def __init__(
        self,
        credentials: AdsCredentials,
        session: HttpSession = requests,
        poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
        max_polls: int = DEFAULT_MAX_POLLS,
    ) -> None:
        self._credentials = credentials
        self._session = session
        self._poll_interval_seconds = poll_interval_seconds
        self._max_polls = max_polls
        self._access_token: str = ""

    def get_daily_units(self, start: date, end: date) -> dict[str, dict[str, int]]:
        report_id = self._create_report(start, end)
        download_url = self._wait_for_report(report_id)
        rows = self._download_rows(download_url)
        return self._group_by_date(rows)

    def _create_report(self, start: date, end: date) -> str:
        body = {
            "name": f"ad-units-{start.isoformat()}-{end.isoformat()}",
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "configuration": {
                "adProduct": "SPONSORED_PRODUCTS",
                "groupBy": ["advertiser"],
                "columns": COLUMNS,
                "reportTypeId": REPORT_TYPE_ID,
                "timeUnit": "DAILY",
                "format": "GZIP_JSON",
            },
        }
        response = self._session.post(
            f"{self._credentials.api_base_url}/reporting/reports",
            headers=self._headers(),
            json=body,
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            raise AdsReportError(
                f"広告レポートの作成に失敗: {response.status_code} {response.text[:200]}"
            )
        return str(response.json()["reportId"])

    def _wait_for_report(self, report_id: str) -> str:
        url = f"{self._credentials.api_base_url}/reporting/reports/{report_id}"
        for _ in range(self._max_polls):
            response = self._session.get(
                url, headers=self._headers(), timeout=TIMEOUT_SECONDS
            )
            if response.status_code >= 400:
                raise AdsReportError(
                    f"広告レポートのポーリングに失敗: {response.status_code} {response.text[:200]}"
                )
            status = response.json()
            if status.get("status") == "COMPLETED":
                return str(status["url"])
            if status.get("status") == "FAILURE":
                raise AdsReportError(f"広告レポートが FAILURE で終了: {status}")
            time.sleep(self._poll_interval_seconds)
        raise AdsReportError(f"広告レポート {report_id} の生成がタイムアウトしました")

    def _download_rows(self, download_url: str) -> list[dict[str, Any]]:
        response = self._session.get(download_url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
        if response.status_code >= 400:
            raise AdsReportError(
                f"広告レポートのダウンロードに失敗: {response.status_code}"
            )
        return json.loads(gzip.decompress(response.content).decode())

    @staticmethod
    def _group_by_date(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        grouped: dict[str, dict[str, int]] = {}
        for row in rows:
            day = str(row.get("date") or "")
            asin = str(row.get("advertisedAsin") or "")
            if not day or not asin:
                continue
            units = int(row.get(UNITS_COLUMN) or 0)
            by_asin = grouped.setdefault(day, {})
            by_asin[asin] = by_asin.get(asin, 0) + units
        return grouped

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._authenticate()}",
            "Amazon-Advertising-API-ClientId": self._credentials.client_id,
            "Amazon-Advertising-API-Scope": self._credentials.profile_id,
            "Accept": REPORT_MEDIA,
            "Content-Type": REPORT_MEDIA,
        }

    def _authenticate(self) -> str:
        if self._access_token:
            return self._access_token
        response = self._session.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._credentials.refresh_token,
                "client_id": self._credentials.client_id,
                "client_secret": self._credentials.client_secret,
            },
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            raise AdsReportError(
                f"Ads API のトークン取得に失敗: {response.status_code} {response.text[:200]}"
            )
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise AdsReportError(
                f"Ads API のトークン応答に access_token がありません: {str(payload)[:200]}"
            )
        self._access_token = str(token)
        return self._access_token
