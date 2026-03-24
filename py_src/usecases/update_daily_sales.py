from __future__ import annotations
from datetime import datetime, timezone, timedelta
from py_src.domain.repositories.sales_repository import SalesRepository
from py_src.domain.repositories.price_repository import PriceRepository
from py_src.domain.value_objects.sales_info import SalesInfo

JST = timezone(timedelta(hours=9))


class UpdateDailySalesUseCase:
    def __init__(
        self,
        sales_sheet: object,
        sales_repository: SalesRepository,
        price_repository: PriceRepository,
    ) -> None:
        self._sheet = sales_sheet
        self._sales_repo = sales_repository
        self._price_repo = price_repository

    def execute(self) -> None:
        asin_list = self._sheet.get_asin_list()
        start_date, end_date = self._get_yesterday_range()
        asin_sales = self._sales_repo.get_daily_sales(
            asin_list=asin_list, start_date=start_date, end_date=end_date,
        )
        self._sheet.write_sales_nums(asin_sales)
        prices = self._price_repo.get_competitive_prices(asin_list)
        self._sheet.write_prices(prices)

    @staticmethod
    def _get_yesterday_range() -> tuple[str, str]:
        now = datetime.now(JST)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        utc_start = yesterday_start.astimezone(timezone.utc)
        utc_end = today_start.astimezone(timezone.utc)
        return (
            utc_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            utc_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
