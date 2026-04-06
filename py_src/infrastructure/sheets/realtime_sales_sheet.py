from __future__ import annotations
from datetime import datetime, timezone, timedelta
from gspread import Worksheet
from gspread.utils import rowcol_to_a1
from py_src.domain.value_objects.realtime_sales_result import RealtimeSalesResult

JST = timezone(timedelta(hours=9))


class RealtimeSalesSheet:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet
        self._asin_list: list[str] = []
        self._unit_col: int = 0
        self._sales_col: int = 0

    def get_asin_list(self) -> list[str]:
        header = self._worksheet.row_values(1)
        self._unit_col = self._find_column(header, "個数")
        self._sales_col = self._find_column(header, "売上")
        values = self._worksheet.col_values(1)
        self._asin_list = [v.strip() for v in values[1:] if v and len(v.strip()) == 10]
        return self._asin_list

    def write_realtime_sales(self, sales_map: dict[str, RealtimeSalesResult]) -> None:
        if not self._asin_list:
            return
        unit_data: list[list[int]] = []
        sales_data: list[list[float]] = []
        for asin in self._asin_list:
            sales = sales_map.get(asin)
            unit_data.append([sales.unit_count if sales else 0])
            sales_data.append([sales.total_amount if sales else 0.0])
        unit_start = rowcol_to_a1(2, self._unit_col)
        sales_start = rowcol_to_a1(2, self._sales_col)
        self._worksheet.update(unit_start, unit_data)
        self._worksheet.update(sales_start, sales_data)
        self._write_updated_at()

    def _write_updated_at(self) -> None:
        now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
        self._worksheet.update("J1", [[now]])

    @staticmethod
    def _find_column(header: list[str], name: str) -> int:
        for i, value in enumerate(header):
            if value.strip() == name:
                return i + 1
        raise ValueError(f"ヘッダーに '{name}' が見つかりません")
