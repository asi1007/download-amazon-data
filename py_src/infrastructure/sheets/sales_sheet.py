from __future__ import annotations
from datetime import datetime, timezone, timedelta
from gspread import Worksheet
from gspread.utils import rowcol_to_a1, ValueRenderOption
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.infrastructure.sheets.retry import retry_on_connection_error

JST = timezone(timedelta(hours=9))
HEADER_ROW = 4
SHEETS_EPOCH = datetime(1899, 12, 30)
DATE_LABEL_FORMAT = {"numberFormat": {"type": "DATE", "pattern": "dd"}}


def apply_date_label_format(worksheet: Worksheet, col: int) -> None:
    label_cells = [rowcol_to_a1(1, col), rowcol_to_a1(HEADER_ROW, col)]
    worksheet.format(label_cells, DATE_LABEL_FORMAT)


def _date_serial(jst_datetime: datetime) -> int:
    naive = datetime(jst_datetime.year, jst_datetime.month, jst_datetime.day)
    return (naive - SHEETS_EPOCH).days


class SalesSheet:
    def __init__(self, sales_worksheet: Worksheet) -> None:
        self._worksheet = sales_worksheet
        self._asin_list: list[str] = []
        self._asin_to_rows: dict[str, list[int]] = {}
        self._start_column: int = 0
        self._price_column: int = 0

    def get_asin_list(self) -> list[str]:
        headers = self._worksheet.row_values(HEADER_ROW)
        self._start_column = self._find_column(headers, "目標販売数") + 1
        self._price_column = self._find_column(headers, "自社価格")
        values = self._worksheet.col_values(1)
        self._asin_list = []
        self._asin_to_rows = {}
        for i, v in enumerate(values):
            stripped = v.strip() if v else ""
            if len(stripped) != 10:
                continue
            if stripped not in self._asin_to_rows:
                self._asin_list.append(stripped)
                self._asin_to_rows[stripped] = []
            self._asin_to_rows[stripped].append(i + 1)
        return self._asin_list

    @retry_on_connection_error
    def write_sales_nums(self, asin_sales: dict[str, SalesInfo]) -> None:
        yesterday = datetime.now(JST) - timedelta(days=1)
        date_serial = _date_serial(yesterday)
        col = self._resolve_column_for(date_serial)

        requests: list[dict] = []
        requests.append({"range": rowcol_to_a1(1, col), "values": [[date_serial]]})
        requests.append({"range": rowcol_to_a1(HEADER_ROW, col), "values": [[date_serial]]})

        total_amount = 0.0
        for asin in self._asin_list:
            if asin not in asin_sales:
                continue
            sales = asin_sales[asin]
            for row in self._asin_to_rows[asin]:
                if row != 3:
                    requests.append(
                        {"range": rowcol_to_a1(row, col), "values": [[sales.unit_count]]}
                    )
            total_amount += sales.total_sales_amount
        requests.append({"range": rowcol_to_a1(3, col), "values": [[total_amount]]})

        self._worksheet.batch_update(requests, value_input_option="RAW")
        apply_date_label_format(self._worksheet, col)

    def _resolve_column_for(self, date_serial: int) -> int:
        existing_column = self._find_serial_column(date_serial)
        if existing_column is not None:
            return existing_column
        self._insert_labeled_column(date_serial)
        return self._start_column

    def _insert_labeled_column(self, date_serial: int) -> None:
        label_column = [date_serial, *[""] * (HEADER_ROW - 2), date_serial]
        self._worksheet.insert_cols([label_column], self._start_column)

    def _find_serial_column(self, date_serial: int) -> int | None:
        header = self._worksheet.row_values(
            HEADER_ROW, value_render_option=ValueRenderOption.unformatted
        )
        for i, value in enumerate(header[self._start_column - 1:], start=self._start_column):
            if value == date_serial:
                return i
        return None

    def get_selling_prices(self) -> dict[str, float]:
        if not self._asin_list:
            return {}
        last_row = max(self._last_row_of(asin) for asin in self._asin_list)
        start_cell = rowcol_to_a1(1, self._price_column)
        end_cell = rowcol_to_a1(last_row, self._price_column)
        price_range = f"{start_cell}:{end_cell}"
        price_values = self._worksheet.get(price_range)
        result: dict[str, float] = {}
        for asin in self._asin_list:
            row = self._asin_to_rows[asin][0]
            if row - 1 < len(price_values):
                cell_value = price_values[row - 1][0] if price_values[row - 1] else ""
                if cell_value:
                    cleaned = str(cell_value).replace("¥", "").replace(",", "").strip()
                    if cleaned:
                        result[asin] = float(cleaned)
        return result

    def _last_row_of(self, asin: str) -> int:
        return self._asin_to_rows[asin][-1]

    @staticmethod
    def _find_column(headers: list[str], name: str) -> int:
        for i, value in enumerate(headers):
            if value.strip() == name:
                return i + 1
        raise ValueError(f"ヘッダーに '{name}' が見つかりません")

    @retry_on_connection_error
    def write_prices(self, prices: dict[str, float]) -> None:
        targets = [
            (asin, row)
            for asin in prices
            if asin in self._asin_to_rows
            for row in self._asin_to_rows[asin]
        ]
        if not targets:
            return
        col = self._start_column
        previous_prices = self._read_previous_prices(col + 1, max(row for _, row in targets))

        requests: list[dict] = []
        notes: dict[str, str] = {}
        cheaper: list[str] = []
        pricier: list[str] = []
        for asin, row in targets:
            price = prices[asin]
            requests.append(
                {"range": rowcol_to_a1(row, self._price_column), "values": [[price]]}
            )
            cell = rowcol_to_a1(row, col)
            notes[cell] = str(price)
            previous = previous_prices.get(row)
            if previous is None:
                continue
            if price < previous:
                cheaper.append(cell)
            elif price > previous:
                pricier.append(cell)

        self._worksheet.batch_update(requests, value_input_option="RAW")
        self._worksheet.update_notes(notes)
        if cheaper:
            self._worksheet.format(cheaper, {"backgroundColor": {"red": 1, "green": 0, "blue": 0}})
        if pricier:
            self._worksheet.format(pricier, {"backgroundColor": {"red": 0, "green": 1, "blue": 1}})

    def _read_previous_prices(self, col: int, last_row: int) -> dict[int, float]:
        cell_range = f"{rowcol_to_a1(1, col)}:{rowcol_to_a1(last_row, col)}"
        values = self._worksheet.get(cell_range)
        result: dict[int, float] = {}
        for index, row_values in enumerate(values):
            raw = row_values[0] if row_values else ""
            if not raw:
                continue
            try:
                result[index + 1] = float(str(raw).replace(",", "").strip())
            except ValueError:
                continue
        return result
