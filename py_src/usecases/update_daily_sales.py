from __future__ import annotations
from datetime import date, datetime, timezone, timedelta
from py_src.domain.repositories.sales_repository import SalesRepository
from py_src.domain.repositories.price_repository import PriceRepository
from py_src.domain.value_objects.gross_profit_write_result import GrossProfitWriteResult
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.domain.value_objects.unit_costs import UnitCosts, estimate_gross_profit

JST = timezone(timedelta(hours=9))


class UpdateDailySalesUseCase:
    def __init__(
        self,
        sales_sheet: object,
        sales_repository: SalesRepository,
        price_repository: PriceRepository,
        cost_reader: object,
    ) -> None:
        self._sheet = sales_sheet
        self._sales_repo = sales_repository
        self._price_repo = price_repository
        self._cost_reader = cost_reader

    def execute(self) -> GrossProfitWriteResult:
        asin_list = self._sheet.get_asin_list()
        yesterday = self._get_yesterday()
        start_date, end_date = self._get_yesterday_range(yesterday)
        asin_sales = self._sales_repo.get_daily_sales(
            asin_list=asin_list, start_date=start_date, end_date=end_date,
        )
        self._sheet.write_sales_nums(asin_sales, target_date=yesterday)
        prices = self._price_repo.get_competitive_prices(asin_list)
        self._sheet.write_prices(prices)
        # 粗利益は最後に書く。原価列のヘッダーが変わると UnitCostReader が
        # ValueError を投げるため、先に置くとその日の価格列と値下げ/値上げの色まで
        # 巻き添えで失われる（見積が1日欠けるより明らかに損が大きい）
        return self._write_gross_profit(asin_sales, yesterday)

    def _write_gross_profit(
        self, asin_sales: dict[str, SalesInfo], target_date: date
    ) -> GrossProfitWriteResult:
        costs = self._cost_reader.read()
        profits = {
            asin: profit
            for asin, sales in asin_sales.items()
            if (profit := estimate_gross_profit(sales, costs.get(asin, UnitCosts()))) is not None
        }
        return self._sheet.write_gross_profit(profits, target_date)

    @staticmethod
    def _get_yesterday() -> date:
        return (datetime.now(JST) - timedelta(days=1)).date()

    @staticmethod
    def _get_yesterday_range(yesterday: date) -> tuple[str, str]:
        yesterday_start = datetime(
            yesterday.year, yesterday.month, yesterday.day, tzinfo=JST
        )
        today_start = yesterday_start + timedelta(days=1)
        return (
            yesterday_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            today_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
