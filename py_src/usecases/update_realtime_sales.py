from __future__ import annotations
from datetime import datetime, timezone, timedelta
from py_src.domain.entities.order import Order
from py_src.domain.value_objects.realtime_sales_result import RealtimeSalesResult
from py_src.infrastructure.api.orders_repository import OrdersRepository
from py_src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet

JST = timezone(timedelta(hours=9))


class UpdateRealtimeSalesUseCase:
    def __init__(self, sheet: RealtimeSalesSheet, repository: OrdersRepository) -> None:
        self._sheet = sheet
        self._repository = repository

    def execute(self) -> None:
        asin_list = self._sheet.get_asin_list()
        created_after = self._get_today_start()
        orders = self._repository.get_orders_with_items(created_after=created_after)
        current_prices = self._fetch_prices_for_zero_items(orders, asin_list)
        sales_map = self._aggregate_by_asin(orders, asin_list, current_prices)
        self._sheet.write_realtime_sales(sales_map)

    def _get_today_start(self) -> str:
        now = datetime.now(JST)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        utc_start = today_start.astimezone(timezone.utc)
        return utc_start.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _fetch_prices_for_zero_items(
        self, orders: list[Order], asin_list: list[str]
    ) -> dict[str, float]:
        asin_set = set(asin_list)
        zero_price_asins: set[str] = set()
        for order in orders:
            if order.is_canceled:
                continue
            for item in order.items:
                if item.asin in asin_set and item.item_price_amount == 0.0:
                    zero_price_asins.add(item.asin)
        if not zero_price_asins:
            return {}
        return self._repository.get_prices(list(zero_price_asins))

    def _aggregate_by_asin(
        self, orders: list[Order], asin_list: list[str], current_prices: dict[str, float]
    ) -> dict[str, RealtimeSalesResult]:
        sales_map: dict[str, RealtimeSalesResult] = {
            asin: RealtimeSalesResult(asin=asin) for asin in asin_list
        }
        active_orders = [o for o in orders if not o.is_canceled]
        for order in active_orders:
            for item in order.items:
                if item.asin in sales_map:
                    unit_price = item.item_price_amount
                    if unit_price == 0.0:
                        unit_price = current_prices.get(item.asin, 0.0)
                    sales_map[item.asin].add_sale(item.quantity_ordered, unit_price)
        return sales_map
