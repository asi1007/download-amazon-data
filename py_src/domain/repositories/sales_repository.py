from __future__ import annotations
from typing import Protocol
from py_src.domain.value_objects.sales_info import SalesInfo


class SalesRepository(Protocol):
    def get_daily_sales(
        self, asin_list: list[str], start_date: str, end_date: str
    ) -> dict[str, SalesInfo]: ...
