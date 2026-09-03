from __future__ import annotations
from datetime import datetime, timezone, timedelta
from gspread import Worksheet
from gspread.utils import rowcol_to_a1
from py_src.domain.value_objects.realtime_sales_result import RealtimeSalesResult

JST = timezone(timedelta(hours=9))
ASIN_LENGTH = 10


class RealtimeSalesSheet:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet
        self._asin_list: list[str] = []
        self._asin_rows: list[tuple[str, int]] = []
        self._unit_col: int = 0
        self._sales_col: int = 0

    def get_asin_list(self) -> list[str]:
        header = self._worksheet.row_values(1)
        self._unit_col = self._find_column(header, "個数")
        self._sales_col = self._find_column(header, "売上")
        values = self._worksheet.col_values(1)
        self._asin_rows = [
            (value.strip(), index + 1)
            for index, value in enumerate(values)
            if index > 0 and value and len(value.strip()) == ASIN_LENGTH
        ]
        self._asin_list = [asin for asin, _ in self._asin_rows]
        return self._asin_list

    def write_realtime_sales(self, sales_map: dict[str, RealtimeSalesResult]) -> None:
        if not self._asin_rows:
            return
        last_row = self._asin_rows[-1][1]
        unit_data: list[list[int | str]] = [[""] for _ in range(last_row - 1)]
        sales_data: list[list[float | str]] = [[""] for _ in range(last_row - 1)]
        for asin, row in self._asin_rows:
            sales = sales_map.get(asin)
            unit_data[row - 2] = [sales.unit_count if sales else 0]
            sales_data[row - 2] = [sales.total_amount if sales else 0.0]
        self._worksheet.update(rowcol_to_a1(2, self._unit_col), unit_data)
        self._worksheet.update(rowcol_to_a1(2, self._sales_col), sales_data)
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
