from __future__ import annotations
from datetime import datetime, timezone, timedelta
from py_src.domain.value_objects.realtime_sales_result import RealtimeSalesResult
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.infrastructure.api.sp_api_sales_repository import SpApiSalesRepository
from py_src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet
from py_src.infrastructure.sheets.sales_sheet import SalesSheet

JST = timezone(timedelta(hours=9))


class UpdateRealtimeSalesUseCase:
    def __init__(
        self,
        realtime_sheet: RealtimeSalesSheet,
        sales_repository: SpApiSalesRepository,
        sales_sheet: SalesSheet | None = None,
    ) -> None:
        self._realtime_sheet = realtime_sheet
        self._sales_repository = sales_repository
        self._sales_sheet = sales_sheet

    def execute(self) -> None:
        asin_list = self._realtime_sheet.get_asin_list()
        selling_prices = self._load_selling_prices()
        start_date, end_date = self._get_today_range()
        sales_infos = self._sales_repository.get_daily_sales(asin_list, start_date, end_date)
        sales_map = self._build_sales_map(asin_list, sales_infos, selling_prices)
        self._realtime_sheet.write_realtime_sales(sales_map)

    def _load_selling_prices(self) -> dict[str, float]:
        if not self._sales_sheet:
            return {}
        self._sales_sheet.get_asin_list()
        return self._sales_sheet.get_selling_prices()

    def _get_today_range(self) -> tuple[str, str]:
        now = datetime.now(JST)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        start_utc = today_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_utc = tomorrow_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return start_utc, end_utc

    def _build_sales_map(
        self,
        asin_list: list[str],
        sales_infos: dict[str, SalesInfo],
        selling_prices: dict[str, float],
    ) -> dict[str, RealtimeSalesResult]:
        sales_map: dict[str, RealtimeSalesResult] = {}
        for asin in asin_list:
            info = sales_infos.get(asin, SalesInfo())
            unit_count = info.unit_count
            total_amount = unit_count * selling_prices.get(asin, 0.0)
            sales_map[asin] = RealtimeSalesResult(
                asin=asin, unit_count=unit_count, total_amount=total_amount,
            )
        return sales_map
