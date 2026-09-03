from __future__ import annotations
from datetime import date, datetime

from gspread import Worksheet
from gspread.utils import rowcol_to_a1, ValueRenderOption

from py_src.domain.value_objects.ad_write_result import AdWriteResult
from py_src.infrastructure.sheets.retry import retry_on_transient_error

HEADER_ROW = 4
ASIN_COLUMN = 1
PRODUCT_NAME_HEADER = "商品名"
AD_ROW_LABEL = "広告経由"
ASIN_LENGTH = 10
SHEETS_EPOCH = date(1899, 12, 30)


def _date_serial(day: date) -> int:
    return (day - SHEETS_EPOCH).days


class AdSalesSheet:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet
        self._ad_rows: dict[str, list[int]] = {}
        self._serial_to_column: dict[int, int] = {}

    def get_ad_rows(self) -> dict[str, list[int]]:
        headers = self._worksheet.row_values(HEADER_ROW)
        name_column = self._find_column(headers, PRODUCT_NAME_HEADER)
        asin_values = self._worksheet.col_values(ASIN_COLUMN)
        name_values = self._worksheet.col_values(name_column)
        self._ad_rows = self._bind_ad_rows(asin_values, name_values)
        return self._ad_rows

    @retry_on_transient_error
    def write_ad_units(self, units_by_date: dict[str, dict[str, int]]) -> AdWriteResult:
        self._serial_to_column = self._read_date_columns()
        columns_by_date = {day: self._columns_for(day) for day in units_by_date}
        skipped_dates = tuple(day for day, columns in columns_by_date.items() if not columns)
        requests = [
            {"range": rowcol_to_a1(row, column), "values": [[by_asin.get(asin, 0)]]}
            for day, by_asin in units_by_date.items()
            for column in columns_by_date[day]
            for asin, rows in self._ad_rows.items()
            for row in rows
        ]
        if requests:
            self._worksheet.batch_update(requests, value_input_option="RAW")
        return AdWriteResult(cells_written=len(requests), skipped_dates=skipped_dates)

    def _columns_for(self, day: str) -> list[int]:
        serial = _date_serial(datetime.strptime(day, "%Y-%m-%d").date())
        column = self._serial_to_column.get(serial)
        return [column] if column else []

    def _read_date_columns(self) -> dict[int, int]:
        header = self._worksheet.row_values(
            HEADER_ROW, value_render_option=ValueRenderOption.unformatted
        )
        return {
            value: index
            for index, value in enumerate(header, start=1)
            if isinstance(value, int)
        }

    @staticmethod
    def _bind_ad_rows(asin_values: list[str], name_values: list[str]) -> dict[str, list[int]]:
        ad_rows: dict[str, list[int]] = {}
        current_asin = ""
        for index in range(max(len(asin_values), len(name_values))):
            row = index + 1
            asin = asin_values[index].strip() if index < len(asin_values) else ""
            name = name_values[index].strip() if index < len(name_values) else ""
            if len(asin) == ASIN_LENGTH:
                current_asin = asin
                continue
            if asin:
                current_asin = ""
                continue
            if name == AD_ROW_LABEL and current_asin:
                ad_rows.setdefault(current_asin, []).append(row)
        return ad_rows

    @staticmethod
    def _find_column(headers: list[str], name: str) -> int:
        for index, value in enumerate(headers, start=1):
            if str(value).strip() == name:
                return index
        raise ValueError(f"ヘッダーに '{name}' が見つかりません")
