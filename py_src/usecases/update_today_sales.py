from __future__ import annotations
import time
from datetime import date, datetime, timezone, timedelta
from py_src.domain.repositories.sales_repository import SalesRepository
from py_src.infrastructure.api.sp_api_sales_repository import SalesFetchDeadlineExceededError

JST = timezone(timedelta(hours=9))

# The hourly job (main.py today) writes only the current hour's column, and the next
# firing is 60 minutes away. A degraded SP-API can make a single ASIN retry loop take
# several minutes (see SP_API_REQUEST_TIMEOUT_SECONDS / retry sleeps in
# sp_api_authenticator.py), so 77 ASINs unbounded could still run for hours and block
# every following hour the way the 19h42m incident did. 20 minutes gives a healthy run
# (a couple of minutes for ~77 ASINs) generous headroom while still leaving 40 minutes
# of buffer before the next hourly firing if the run gives up.
HOURLY_SALES_DEADLINE_SECONDS = 20 * 60


class UpdateTodaySalesUseCase:
    def __init__(self, sales_sheet: object, sales_repository: SalesRepository) -> None:
        self._sheet = sales_sheet
        self._sales_repo = sales_repository

    def execute(self) -> None:
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
            self._sheet.write_sales_nums(error.partial_results, target_date=today)
            raise
        self._sheet.write_sales_nums(asin_sales, target_date=today)

    @staticmethod
    def _get_today_range(today: date) -> tuple[str, str]:
        today_start = datetime(today.year, today.month, today.day, tzinfo=JST)
        tomorrow_start = today_start + timedelta(days=1)
        return (
            today_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            tomorrow_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
