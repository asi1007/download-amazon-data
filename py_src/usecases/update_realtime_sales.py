from __future__ import annotations
import time
from datetime import datetime, timezone, timedelta
from py_src.domain.value_objects.realtime_sales_result import RealtimeSalesResult
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.infrastructure.api.sp_api_sales_repository import SpApiSalesRepository
from py_src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet
from py_src.infrastructure.sheets.sales_sheet import SalesSheet

JST = timezone(timedelta(hours=9))

# This job (main.py, no subcommand) fires every 30 minutes and writes 売上/今. Same
# hang-risk shape as the hourly job (see HOURLY_SALES_DEADLINE_SECONDS in
# update_today_sales.py), scaled down for the shorter cycle: worst case per ASIN is
# still ~8.2 minutes (see that comment for the arithmetic), so a smaller deadline still
# leaves comfortable buffer before the next 30-minute firing (10 + 8.2 =~ 18.2 minutes
# worst case, ~11.8 minutes of buffer) while staying well above a healthy run (a couple
# of minutes for ~77 ASINs).
REALTIME_SALES_DEADLINE_SECONDS = 10 * 60


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
        deadline_at = time.monotonic() + REALTIME_SALES_DEADLINE_SECONDS
        # No except here on purpose: unlike write_sales_nums, write_realtime_sales
        # fills every ASIN missing from the map with 0 units / 0 sales, so a partial
        # write on deadline cutoff would corrupt 売上/今 with false zeros. Letting
        # SalesFetchDeadlineExceededError propagate leaves the previous run's numbers
        # in place and still exits non-zero for the Slack alert.
        sales_infos = self._sales_repository.get_daily_sales(
            asin_list, start_date, end_date, deadline_at=deadline_at,
        )
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
