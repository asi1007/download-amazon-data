from __future__ import annotations
import time
import requests
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator, SP_API_BASE

MARKETPLACE_JP = "A1VC38T7YXB528"
REQUEST_INTERVAL_SECONDS = 1
MAX_FAILURE_RATIO = 0.1


class SalesFetchFailureError(RuntimeError):
    pass


class SpApiSalesRepository:
    def __init__(self, authenticator: SpApiAuthenticator) -> None:
        self._auth = authenticator

    def get_daily_sales(
        self, asin_list: list[str], start_date: str, end_date: str
    ) -> dict[str, SalesInfo]:
        return self._fetch_sales_for_asins(asin_list, start_date, end_date, "Day")

    def get_weekly_sales(
        self, asin_list: list[str], start_date: str, end_date: str
    ) -> dict[str, SalesInfo]:
        return self._fetch_sales_for_asins(asin_list, start_date, end_date, "Week")

    def _fetch_sales_for_asins(
        self, asin_list: list[str], start_date: str, end_date: str, granularity: str
    ) -> dict[str, SalesInfo]:
        result, failed_asins = self._fetch_each(asin_list, start_date, end_date, granularity)
        if failed_asins:
            print(f"{len(failed_asins)}件のASIN取得に失敗、再試行します: {', '.join(failed_asins)}")
            retried, failed_asins = self._fetch_each(
                failed_asins, start_date, end_date, granularity
            )
            result.update(retried)
        self._reject_excessive_failures(failed_asins, len(asin_list))
        return result

    def _fetch_each(
        self, asin_list: list[str], start_date: str, end_date: str, granularity: str
    ) -> tuple[dict[str, SalesInfo], list[str]]:
        result: dict[str, SalesInfo] = {}
        failed_asins: list[str] = []
        for i, asin in enumerate(asin_list):
            if i > 0:
                time.sleep(REQUEST_INTERVAL_SECONDS)
            try:
                result[asin] = self._fetch_sales(asin, start_date, end_date, granularity)
            except requests.exceptions.RequestException:
                failed_asins.append(asin)
        return result, failed_asins

    def _fetch_sales(
        self, asin: str, start_date: str, end_date: str, granularity: str = "Day"
    ) -> SalesInfo:
        interval = f"{start_date}--{end_date}"
        url = (
            f"{SP_API_BASE}/sales/v1/orderMetrics"
            f"?marketplaceIds={MARKETPLACE_JP}"
            f"&interval={interval}"
            f"&granularity={granularity}"
            f"&granularityTimeZone=Asia/Tokyo"
            f"&asin={asin}"
        )
        response = self._auth.request("GET", url)
        return self._parse_sales(response.json())

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
