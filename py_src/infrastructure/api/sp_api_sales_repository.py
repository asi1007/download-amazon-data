from __future__ import annotations
import time
from datetime import date, datetime
import requests
from sales_data.domain.value_objects.sales_info import SalesInfo
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator, SP_API_BASE

MARKETPLACE_JP = "A1VC38T7YXB528"
REQUEST_INTERVAL_SECONDS = 1
MAX_FAILURE_RATIO = 0.1


class SalesFetchFailureError(RuntimeError):
    pass


class SalesFetchDeadlineExceededError(RuntimeError):
    def __init__(
        self, partial_results: dict[str, SalesInfo], attempted_count: int, total_count: int
    ) -> None:
        super().__init__(
            f"締切に達したため中断: {total_count}件中 {attempted_count}件のみ取得済み"
        )
        self.partial_results = partial_results


class SpApiSalesRepository:
    def __init__(self, authenticator: SpApiAuthenticator) -> None:
        self._auth = authenticator

    def get_daily_sales(
        self,
        asin_list: list[str],
        start_date: str,
        end_date: str,
        deadline_at: float | None = None,
    ) -> dict[str, SalesInfo]:
        return self._fetch_sales_for_asins(asin_list, start_date, end_date, "Day", deadline_at)

    def get_sales_by_date(
        self, asin_list: list[str], start_date: str, end_date: str
    ) -> dict[str, dict[date, SalesInfo]]:
        # 1 ASIN 1リクエストで期間全体を Day 粒度で取る。失敗した ASIN は結果に
        # 入れない（欠測を 0 と書くと販売0件と見分けがつかない）
        by_asin: dict[str, dict[date, SalesInfo]] = {}
        failed_asins: list[str] = []
        for i, asin in enumerate(asin_list):
            if i > 0:
                time.sleep(REQUEST_INTERVAL_SECONDS)
            try:
                response = self._auth.request("GET", self._metrics_url(asin, start_date, end_date))
            except requests.exceptions.RequestException:
                failed_asins.append(asin)
                continue
            by_asin[asin] = self._parse_sales_by_date(response.json())
        # 個別の失敗はセルを空のまま残すだけだが、全滅は設定ミスや障害。
        # 黙って {} を返すと呼び出し元が 0 件で正常終了してしまう
        self._reject_excessive_failures(failed_asins, len(asin_list))
        return by_asin

    @staticmethod
    def _parse_sales_by_date(data: dict) -> dict[date, SalesInfo]:
        by_date: dict[date, SalesInfo] = {}
        for entry in data.get("payload", []):
            day = _interval_start_date(entry.get("interval", ""))
            if day is None:
                continue
            by_date[day] = SalesInfo(
                unit_count=entry.get("unitCount", 0),
                total_sales_amount=float(entry.get("totalSales", {}).get("amount", 0)),
                order_count=entry.get("orderCount", 0),
            )
        return by_date

    def get_weekly_sales(
        self, asin_list: list[str], start_date: str, end_date: str
    ) -> dict[str, SalesInfo]:
        return self._fetch_sales_for_asins(asin_list, start_date, end_date, "Week", None)

    def _fetch_sales_for_asins(
        self,
        asin_list: list[str],
        start_date: str,
        end_date: str,
        granularity: str,
        deadline_at: float | None,
    ) -> dict[str, SalesInfo]:
        result, failed_asins, unattempted = self._fetch_each(
            asin_list, start_date, end_date, granularity, deadline_at
        )
        self._reject_if_deadline_exceeded(result, unattempted, len(asin_list))
        if failed_asins:
            print(f"{len(failed_asins)}件のASIN取得に失敗、再試行します: {', '.join(failed_asins)}")
            retried, failed_asins, unattempted = self._fetch_each(
                failed_asins, start_date, end_date, granularity, deadline_at
            )
            result.update(retried)
            self._reject_if_deadline_exceeded(result, unattempted, len(asin_list))
        self._reject_excessive_failures(failed_asins, len(asin_list))
        return result

    def _fetch_each(
        self,
        asin_list: list[str],
        start_date: str,
        end_date: str,
        granularity: str,
        deadline_at: float | None,
    ) -> tuple[dict[str, SalesInfo], list[str], list[str]]:
        result: dict[str, SalesInfo] = {}
        failed_asins: list[str] = []
        for i, asin in enumerate(asin_list):
            if self._deadline_passed(deadline_at):
                return result, failed_asins, asin_list[i:]
            if i > 0:
                time.sleep(REQUEST_INTERVAL_SECONDS)
            try:
                result[asin] = self._fetch_sales(asin, start_date, end_date, granularity)
            except requests.exceptions.RequestException:
                failed_asins.append(asin)
        return result, failed_asins, []

    @staticmethod
    def _deadline_passed(deadline_at: float | None) -> bool:
        return deadline_at is not None and time.monotonic() >= deadline_at

    @staticmethod
    def _reject_if_deadline_exceeded(
        result: dict[str, SalesInfo], unattempted: list[str], total_count: int
    ) -> None:
        if not unattempted:
            return
        raise SalesFetchDeadlineExceededError(
            partial_results=result, attempted_count=len(result), total_count=total_count,
        )

    def _fetch_sales(
        self, asin: str, start_date: str, end_date: str, granularity: str = "Day"
    ) -> SalesInfo:
        url = self._metrics_url(asin, start_date, end_date, granularity)
        response = self._auth.request("GET", url)
        return self._parse_sales(response.json())

    @staticmethod
    def _metrics_url(
        asin: str, start_date: str, end_date: str, granularity: str = "Day"
    ) -> str:
        return (
            f"{SP_API_BASE}/sales/v1/orderMetrics"
            f"?marketplaceIds={MARKETPLACE_JP}"
            f"&interval={start_date}--{end_date}"
            f"&granularity={granularity}"
            f"&granularityTimeZone=Asia/Tokyo"
            f"&asin={asin}"
        )

    @staticmethod
    def _reject_excessive_failures(failed_asins: list[str], total_count: int) -> None:
        if not failed_asins:
            return
        message = f"{total_count}件中 {len(failed_asins)}件のASIN取得に失敗: {', '.join(failed_asins)}"
        if len(failed_asins) > total_count * MAX_FAILURE_RATIO:
            raise SalesFetchFailureError(message)
        print(f"{message}（許容範囲内のため該当セルは空のまま続行）")

    @staticmethod
    def _parse_sales(data: dict) -> SalesInfo:
        payload = data.get("payload", [])
        if not payload:
            return SalesInfo()
        entry = payload[0]
        return SalesInfo(
            unit_count=entry.get("unitCount", 0),
            total_sales_amount=float(entry.get("totalSales", {}).get("amount", 0)),
            order_count=entry.get("orderCount", 0),
        )


def _interval_start_date(interval: str) -> date | None:
    start = interval.split("--")[0]
    try:
        return datetime.fromisoformat(start).date()
    except ValueError:
        return None
