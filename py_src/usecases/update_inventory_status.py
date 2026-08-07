from __future__ import annotations
from datetime import datetime, timezone, timedelta
from py_src.infrastructure.api.sp_api_inventory_repository import SpApiInventoryRepository
from py_src.infrastructure.api.sp_api_price_repository import SpApiPriceRepository
from py_src.infrastructure.sheets.inventory_sheet import InventorySheet


class UpdateInventoryStatusUseCase:
    def __init__(
        self,
        inventory_repository: SpApiInventoryRepository,
        price_repository: SpApiPriceRepository,
        inventory_sheet: InventorySheet,
    ) -> None:
        self._inventory_repository = inventory_repository
        self._price_repository = price_repository
        self._inventory_sheet = inventory_sheet

    def execute(self) -> int:
        start = self._one_month_ago_iso()
        summaries = self._inventory_repository.get_all_summaries(start_date_time=start)
        unique_asins = sorted({s.asin for s in summaries if s.asin})
        prices = self._price_repository.get_competitive_prices(unique_asins) if unique_asins else {}
        summaries_with_prices = [s.with_price(prices.get(s.asin, "")) for s in summaries]
        self._inventory_sheet.write_inventory_data(summaries_with_prices)
        return len(summaries_with_prices)

    @staticmethod
    def _one_month_ago_iso() -> str:
        moment = datetime.now(timezone.utc) - timedelta(days=30)
        return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")
