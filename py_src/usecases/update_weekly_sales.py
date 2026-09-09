from __future__ import annotations
from datetime import date, datetime, time, timezone, timedelta
from py_src.domain.repositories.sales_repository import SalesRepository
from sales_data.infrastructure.sheets.repository import SheetsSalesRepository
from py_src.infrastructure.sheets.amazon_ad_sheet import AmazonAdSheet
from py_src.infrastructure.sheets.sales_data_sheet import SalesDataSheet

JST = timezone(timedelta(hours=9))


class UpdateWeeklySalesUseCase:
    def __init__(
        self,
        sales_sheet: SheetsSalesRepository,
        sales_repository: SalesRepository,
        ad_sheet: AmazonAdSheet,
        sales_data_sheet: SalesDataSheet,
        today: date | None = None,
    ) -> None:
        self._sales_sheet = sales_sheet
        self._sales_repo = sales_repository
        self._ad_sheet = ad_sheet
        self._sales_data_sheet = sales_data_sheet
        self._today = today or datetime.now(JST).date()

    def execute(self) -> None:
        asin_list = self._sales_sheet.get_asin_list()
        start_jst, end_jst = self._weekly_range_jst()
        start_iso, end_iso = self._to_utc_iso(start_jst), self._to_utc_iso(end_jst)
        asin_sales = self._sales_repo.get_weekly_sales(
            asin_list=asin_list, start_date=start_iso, end_date=end_iso,
        )
        ad_spend = self._ad_sheet.get_ad_spend_by_period_start(start_jst.strftime("%Y-%m-%d"))
        self._sales_data_sheet.append_weekly_data(
            start_date=self._format_slash(start_jst),
            end_date=self._format_slash(end_jst),
            asin_sales=asin_sales,
            ad_spend=ad_spend,
        )

    def _weekly_range_jst(self) -> tuple[date, date]:
        weekday = self._today.weekday()
        diff = -weekday if weekday != 6 else -6
        end = self._today + timedelta(days=diff)
        start = end - timedelta(days=7)
        return start, end

    @staticmethod
    def _to_utc_iso(d: date) -> str:
        jst_midnight = datetime.combine(d, time(0, 0), tzinfo=JST)
        return jst_midnight.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _format_slash(d: date) -> str:
        return f"{d.year}/{d.month}/{d.day}"
