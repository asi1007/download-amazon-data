from __future__ import annotations
from gspread import Worksheet
from py_src.domain.value_objects.sales_info import SalesInfo


class SalesDataSheet:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet

    def append_weekly_data(
        self,
        start_date: str,
        end_date: str,
        asin_sales: dict[str, SalesInfo],
        ad_spend: dict[str, float],
    ) -> None:
        if not asin_sales:
            return
        rows: list[list[str | int | float]] = []
        for asin, sales in asin_sales.items():
            rows.append([
                start_date,
                end_date,
                asin,
                sales.unit_count,
                sales.total_sales_amount,
                sales.order_count,
                ad_spend.get(asin, 0.0),
            ])
        self._worksheet.append_rows(rows)
