from __future__ import annotations
from datetime import datetime, timezone, timedelta
from gspread import Worksheet
from gspread.utils import rowcol_to_a1
from py_src.domain.value_objects.sales_info import SalesInfo

JST = timezone(timedelta(hours=9))
HEADER_ROW = 4


class SalesSheet:
    def __init__(self, sales_worksheet: Worksheet) -> None:
        self._worksheet = sales_worksheet
        self._asin_list: list[str] = []
        self._asin_to_row: dict[str, int] = {}
        self._start_column: int = 0
        self._price_column: int = 0

    def get_asin_list(self) -> list[str]:
        headers = self._worksheet.row_values(HEADER_ROW)
        self._start_column = self._find_column(headers, "目標販売数") + 1
        self._price_column = self._find_column(headers, "自社価格")
        values = self._worksheet.col_values(1)
        self._asin_list = []
        self._asin_to_row = {}
        for i, v in enumerate(values):
            stripped = v.strip() if v else ""
            if len(stripped) == 10:
                self._asin_list.append(stripped)
                self._asin_to_row[stripped] = i + 1
        return self._asin_list

    def write_sales_nums(self, asin_sales: dict[str, SalesInfo]) -> None:
        col = self._start_column
        self._worksheet.insert_cols(col)
        date_str = datetime.now(JST).strftime("%d")
        self._worksheet.update(rowcol_to_a1(1, col), [[date_str]])
        self._worksheet.update(rowcol_to_a1(HEADER_ROW, col), [[date_str]])
        total_amount = 0.0
        for asin in self._asin_list:
            row = self._asin_to_row[asin]
            sales = asin_sales.get(asin, SalesInfo())
            if row != 3:
                self._worksheet.update(rowcol_to_a1(row, col), [[sales.unit_count]])
            total_amount += sales.total_sales_amount
        self._worksheet.update(rowcol_to_a1(3, col), [[total_amount]])

    def get_selling_prices(self) -> dict[str, float]:
        if not self._asin_list:
            return {}
        last_row = max(self._asin_to_row.values())
        start_cell = rowcol_to_a1(1, self._price_column)
        end_cell = rowcol_to_a1(last_row, self._price_column)
        price_range = f"{start_cell}:{end_cell}"
        price_values = self._worksheet.get(price_range)
        result: dict[str, float] = {}
        for asin in self._asin_list:
            row = self._asin_to_row[asin]
            if row - 1 < len(price_values):
                cell_value = price_values[row - 1][0] if price_values[row - 1] else ""
                if cell_value:
                    cleaned = str(cell_value).replace("¥", "").replace(",", "").strip()
                    if cleaned:
                        result[asin] = float(cleaned)
        return result

    @staticmethod
    def _find_column(headers: list[str], name: str) -> int:
        for i, value in enumerate(headers):
            if value.strip() == name:
                return i + 1
        raise ValueError(f"ヘッダーに '{name}' が見つかりません")

    def write_prices(self, prices: dict[str, float]) -> None:
        col = self._start_column
        for asin, price in prices.items():
            if asin not in self._asin_to_row:
                continue
            row = self._asin_to_row[asin]
            self._worksheet.update_cell(row, self._price_column, price)
            self._worksheet.update_note(rowcol_to_a1(row, col), str(price))
            prev_cell = self._worksheet.cell(row, col + 1)
            prev_price_str = prev_cell.value if prev_cell.value else ""
            if prev_price_str:
                prev_price = float(prev_price_str)
                if price < prev_price:
                    self._worksheet.format(rowcol_to_a1(row, col), {"backgroundColor": {"red": 1, "green": 0, "blue": 0}})
                elif price > prev_price:
                    self._worksheet.format(rowcol_to_a1(row, col), {"backgroundColor": {"red": 0, "green": 1, "blue": 1}})
