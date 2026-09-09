from __future__ import annotations
import time
from datetime import date, datetime, timezone, timedelta
from py_src.domain.repositories.sales_repository import SalesRepository
from sales_data.domain.value_objects.gross_profit_write_result import GrossProfitWriteResult
from sales_data.domain.value_objects.sales_info import SalesInfo
from sales_data.domain.value_objects.unit_costs import UnitCosts, estimate_gross_profit
from py_src.infrastructure.api.sp_api_sales_repository import SalesFetchDeadlineExceededError

JST = timezone(timedelta(hours=9))

# The hourly job (main.py today) writes only the current hour's column, and the next
# firing is 60 minutes away. A degraded SP-API can make a single ASIN's retry loop take
# up to ~8.2 minutes worst case (5 attempts: 42s of sleep between attempts + 5 x 90s
# SP_API_REQUEST_TIMEOUT_SECONDS read timeout = 492s), so 77 ASINs unbounded could still
# run for hours and block every following hour the way the 19h42m incident did. The
# deadline is checked once per ASIN before starting its fetch, not mid-request, so the
# in-flight ASIN when the deadline fires can still run its own worst case to completion:
# worst-case wall clock is therefore ~20 + 8.2 =~ 28 minutes, leaving ~32 minutes of
# buffer before the next hourly firing. 20 minutes gives a healthy run (a couple of
# minutes for ~77 ASINs) generous headroom while keeping that buffer comfortable.
HOURLY_SALES_DEADLINE_SECONDS = 20 * 60


class UpdateTodaySalesUseCase:
    def __init__(
        self,
        sales_sheet: object,
        sales_repository: SalesRepository,
        cost_reader: object,
    ) -> None:
        self._sheet = sales_sheet
        self._sales_repo = sales_repository
        self._cost_reader = cost_reader

    def execute(self) -> GrossProfitWriteResult:
        today = datetime.now(JST).date()
        asin_list = self._sheet.get_asin_list()
        start_date, end_date = self._get_today_range(today)
        deadline_at = time.monotonic() + HOURLY_SALES_DEADLINE_SECONDS
        try:
            asin_sales = self._sales_repo.get_daily_sales(
                asin_list=asin_list,
                start_date=start_date,
                end_date=end_date,
                deadline_at=deadline_at,
            )
        except SalesFetchDeadlineExceededError as error:
            # A partial result understates row 3 (total sales) if summed as-is, so
            # tell the sheet not to touch it — leaving the previous hour's total in
            # place is more honest than replacing it with an incomplete sum. The
            # gross profit row has no such total to distort, so it is written for
            # whichever ASINs did make it in before the deadline.
            self._sheet.write_sales_nums(
                error.partial_results, target_date=today, include_total=False,
            )
            self._write_gross_profit(error.partial_results, today)
            raise
        self._sheet.write_sales_nums(asin_sales, target_date=today)
        return self._write_gross_profit(asin_sales, today)

    def _write_gross_profit(
        self, asin_sales: dict[str, SalesInfo], target_date: date
    ) -> GrossProfitWriteResult:
        costs = self._cost_reader.read()
        # 原価や手数料が欠けた ASIN は「書かない」ではなく「空にする」。
        # 前回の見積が残ると、黄色のまま最新の数字のように見えてしまう
        profits = {
            asin: estimate_gross_profit(sales, costs.get(asin, UnitCosts()))
            for asin, sales in asin_sales.items()
        }
        return self._sheet.write_gross_profit(profits, target_date)

    @staticmethod
    def _get_today_range(today: date) -> tuple[str, str]:
        today_start = datetime(today.year, today.month, today.day, tzinfo=JST)
        tomorrow_start = today_start + timedelta(days=1)
        return (
            today_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            tomorrow_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
