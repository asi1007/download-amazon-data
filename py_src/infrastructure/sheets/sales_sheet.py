from __future__ import annotations
from datetime import datetime, date, timezone, timedelta
from gspread import Worksheet
from gspread.utils import rowcol_to_a1, a1_range_to_grid_range, ValueRenderOption
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.infrastructure.sheets.label_rows import (
    ASIN_COLUMN,
    GROSS_PROFIT_ROW_LABEL,
    PRODUCT_NAME_HEADER,
    bind_label_rows,
    date_serial as label_date_serial,
    find_column as find_label_column,
    read_date_columns,
)
from py_src.infrastructure.sheets.retry import retry_on_transient_error

JST = timezone(timedelta(hours=9))
HEADER_ROW = 4
TOTAL_AMOUNT_ROW = 3
# 行1〜4（日付ラベル・取得時刻・総売上）は予約行。ASINは必ず行5以降にある前提で
# `row > HEADER_ROW` によりASINループの書き込みから一括で除外する。
FETCH_TIME_ROW = 2
SHEETS_EPOCH = datetime(1899, 12, 30)
DATE_LABEL_FORMAT = {"numberFormat": {"type": "DATE", "pattern": "dd"}}
TOTAL_AMOUNT_FORMAT = {"numberFormat": {"type": "NUMBER", "pattern": '#,##0,"千円"'}}
CHEAPER_FORMAT = {"backgroundColor": {"red": 1, "green": 0, "blue": 0}}
PRICIER_FORMAT = {"backgroundColor": {"red": 0, "green": 1, "blue": 1}}
BACKGROUND_COLOR_FIELD = "userEnteredFormat.backgroundColor"
GROSS_PROFIT_ESTIMATE_FORMAT = {"backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.8}}


def apply_column_formats(worksheet: Worksheet, col: int) -> None:
    worksheet.batch_format(
        [
            {"range": rowcol_to_a1(1, col), "format": DATE_LABEL_FORMAT},
            {"range": rowcol_to_a1(HEADER_ROW, col), "format": DATE_LABEL_FORMAT},
            {"range": rowcol_to_a1(TOTAL_AMOUNT_ROW, col), "format": TOTAL_AMOUNT_FORMAT},
        ]
    )


def _date_serial(target_date: date) -> int:
    naive = datetime(target_date.year, target_date.month, target_date.day)
    return (naive - SHEETS_EPOCH).days


def _fetch_time_label() -> str:
    return datetime.now(JST).strftime("%H:%M")


class SalesSheet:
    def __init__(self, sales_worksheet: Worksheet) -> None:
        self._worksheet = sales_worksheet
        self._asin_list: list[str] = []
        self._asin_to_rows: dict[str, list[int]] = {}
        self._start_column: int = 0
        self._price_column: int = 0
        self._sales_column: int | None = None

    # write_sales_nums / write_prices below are @retry_on_transient_error; this read is
    # deliberately not. It runs before the hourly/realtime deadline budget starts
    # counting (see update_today_sales.py / update_realtime_sales.py), so a transient
    # failure here should fail fast via the gspread timeout rather than spend part of
    # that budget retrying with a 30s/60s backoff.
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

    @retry_on_transient_error
    def write_sales_nums(
        self,
        asin_sales: dict[str, SalesInfo],
        target_date: date | None = None,
        include_total: bool = True,
    ) -> None:
        if target_date is None:
            target_date = (datetime.now(JST) - timedelta(days=1)).date()
        date_serial = _date_serial(target_date)
        col = self._resolve_column_for(date_serial)
        self._sales_column = col

        requests: list[dict] = []
        requests.append({"range": rowcol_to_a1(1, col), "values": [[date_serial]]})
        requests.append(
            {"range": rowcol_to_a1(FETCH_TIME_ROW, col), "values": [[_fetch_time_label()]]}
        )
        requests.append({"range": rowcol_to_a1(HEADER_ROW, col), "values": [[date_serial]]})

        total_amount = 0.0
        for asin in self._asin_list:
            if asin not in asin_sales:
                continue
            sales = asin_sales[asin]
            for row in self._asin_to_rows[asin]:
                if row > HEADER_ROW:
                    requests.append(
                        {"range": rowcol_to_a1(row, col), "values": [[sales.unit_count]]}
                    )
            total_amount += sales.total_sales_amount
        if include_total:
            # asin_sales may cover only a subset of ASINs (deadline cutoff, partial
            # fetch). Writing a total computed from a subset would silently understate
            # row 3 and contradict the individual cells. When the caller knows the
            # result is partial (include_total=False), leave row 3 as whatever the
            # previous run wrote rather than replace it with an incomplete sum.
            requests.append(
                {"range": rowcol_to_a1(TOTAL_AMOUNT_ROW, col), "values": [[total_amount]]}
            )

        self._worksheet.batch_update(requests, value_input_option="RAW")
        apply_column_formats(self._worksheet, col)

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

    @retry_on_transient_error
    def write_prices(self, prices: dict[str, float]) -> None:
        targets = [
            (asin, row)
            for asin in prices
            if asin in self._asin_to_rows
            for row in self._asin_to_rows[asin]
            if row > HEADER_ROW
        ]
        if self._sales_column is None:
            raise RuntimeError(
                "write_prices は write_sales_nums で対象列を解決した後にしか呼び出せません"
            )
        if not targets:
            return
        col = self._sales_column
        previous_prices = self._read_previous_prices(col + 1, max(row for _, row in targets))

        requests: list[dict] = []
        notes: dict[str, str] = {}
        written_cells: list[str] = []
        cheaper: list[str] = []
        pricier: list[str] = []
        for asin, row in targets:
            price = prices[asin]
            requests.append(
                {"range": rowcol_to_a1(row, self._price_column), "values": [[price]]}
            )
            cell = rowcol_to_a1(row, col)
            notes[cell] = str(price)
            written_cells.append(cell)
            previous = previous_prices.get(row)
            if previous is None:
                continue
            if price < previous:
                cheaper.append(cell)
            elif price > previous:
                pricier.append(cell)

        self._worksheet.batch_update(requests, value_input_option="RAW")
        self._worksheet.update_notes(notes)
        self._clear_backgrounds(written_cells)
        if cheaper:
            self._worksheet.format(cheaper, CHEAPER_FORMAT)
        if pricier:
            self._worksheet.format(pricier, PRICIER_FORMAT)

    def _clear_backgrounds(self, cells: list[str]) -> None:
        sheet_id = self._worksheet.id
        requests = [
            {
                "repeatCell": {
                    "range": a1_range_to_grid_range(cell, sheet_id),
                    "fields": BACKGROUND_COLOR_FIELD,
                }
            }
            for cell in cells
        ]
        self._worksheet.spreadsheet.batch_update({"requests": requests})

    @retry_on_transient_error
    def write_gross_profit(
        self, profit_by_asin: dict[str, float], target_date: date
    ) -> int:
        column = read_date_columns(self._worksheet).get(label_date_serial(target_date))
        if column is None:
            return 0

        targets = [
            (asin, row)
            for asin, rows in self._gross_profit_rows().items()
            if asin in profit_by_asin
            for row in rows
            if row > HEADER_ROW
        ]
        if not targets:
            return 0

        # batch_update は渡した dict の "range" を in-place でシート名付きに書き換える
        # (例: "CS9" -> "'売上/日'!CS9")。format() はシート名付きの範囲を受け付けないため、
        # batch_update に渡す前に書式対象のセルを別のリストへ保持しておく
        # (write_prices の written_cells と同じ回避)。
        written_cells = [rowcol_to_a1(row, column) for _, row in targets]
        requests = [
            {"range": cell, "values": [[profit_by_asin[asin]]]}
            for cell, (asin, _) in zip(written_cells, targets)
        ]
        self._worksheet.batch_update(requests, value_input_option="RAW")
        self._worksheet.format(written_cells, GROSS_PROFIT_ESTIMATE_FORMAT)
        return len(requests)

    def _gross_profit_rows(self) -> dict[str, list[int]]:
        headers = self._worksheet.row_values(HEADER_ROW)
        name_column = find_label_column(headers, PRODUCT_NAME_HEADER)
        asin_values = self._worksheet.col_values(ASIN_COLUMN)
        name_values = self._worksheet.col_values(name_column)
        return bind_label_rows(asin_values, name_values, GROSS_PROFIT_ROW_LABEL)

    def _read_previous_prices(self, col: int, last_row: int) -> dict[int, float]:
        cell_range = f"{rowcol_to_a1(1, col)}:{rowcol_to_a1(last_row, col)}"
        recorded_notes = self._worksheet.get_notes(grid_range=cell_range)
        result: dict[int, float] = {}
        for index, row_notes in enumerate(recorded_notes):
            raw = row_notes[0] if row_notes else ""
            if not raw:
                continue
            try:
                result[index + 1] = float(str(raw).replace(",", "").strip())
            except ValueError:
                continue
        return result
