from __future__ import annotations
from datetime import date, datetime, timezone, timedelta
from py_src.domain.repositories.sales_repository import SalesRepository

JST = timezone(timedelta(hours=9))


class UpdateTodaySalesUseCase:
    def __init__(self, sales_sheet: object, sales_repository: SalesRepository) -> None:
        self._sheet = sales_sheet
        self._sales_repo = sales_repository

    def execute(self) -> None:
        today = datetime.now(JST).date()
        asin_list = self._sheet.get_asin_list()
        start_date, end_date = self._get_today_range(today)
        asin_sales = self._sales_repo.get_daily_sales(
            asin_list=asin_list, start_date=start_date, end_date=end_date,
        )
        self._sheet.write_sales_nums(asin_sales, target_date=today)

    @staticmethod
    def _get_today_range(today: date) -> tuple[str, str]:
        today_start = datetime(today.year, today.month, today.day, tzinfo=JST)
        tomorrow_start = today_start + timedelta(days=1)
        return (
            today_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            tomorrow_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
