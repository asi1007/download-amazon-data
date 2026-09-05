from __future__ import annotations
from datetime import datetime

from gspread import Worksheet
from gspread.utils import rowcol_to_a1

from py_src.domain.value_objects.ad_write_result import AdWriteResult
from py_src.infrastructure.sheets.label_rows import (
    AD_ROW_LABEL,
    ASIN_COLUMN,
    ASIN_LENGTH,
    HEADER_ROW,
    PRODUCT_NAME_HEADER,
    bind_label_rows,
    date_serial,
    find_column,
    read_date_columns,
)
from py_src.infrastructure.sheets.retry import retry_on_transient_error


class AdSalesSheet:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet
        self._ad_rows: dict[str, list[int]] = {}
        self._serial_to_column: dict[int, int] = {}

    def get_ad_rows(self) -> dict[str, list[int]]:
        headers = self._worksheet.row_values(HEADER_ROW)
        name_column = find_column(headers, PRODUCT_NAME_HEADER)
        asin_values = self._worksheet.col_values(ASIN_COLUMN)
        name_values = self._worksheet.col_values(name_column)
        self._ad_rows = bind_label_rows(asin_values, name_values, AD_ROW_LABEL)
        return self._ad_rows

    @retry_on_transient_error
    def write_ad_units(self, units_by_date: dict[str, dict[str, int]]) -> AdWriteResult:
        self._serial_to_column = read_date_columns(self._worksheet)
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
        serial = date_serial(datetime.strptime(day, "%Y-%m-%d").date())
        column = self._serial_to_column.get(serial)
        return [column] if column else []

