from __future__ import annotations
from datetime import datetime
from operator import attrgetter
from typing import Callable

from gspread import Worksheet
from gspread.utils import rowcol_to_a1

from py_src.domain.value_objects.ad_metrics import AdMetrics
from py_src.domain.value_objects.ad_write_result import AdCostRowsNotFoundError, AdWriteResult
from py_src.infrastructure.sheets.label_rows import (
    AD_COST_ROW_LABEL,
    AD_ROW_LABEL,
    ASIN_COLUMN,
    HEADER_ROW,
    K_YEN_NUMBER_FORMAT,
    PRODUCT_NAME_HEADER,
    bind_label_rows,
    date_serial,
    find_column,
    read_date_columns,
)
from py_src.infrastructure.sheets.retry import retry_on_transient_error

MetricsByDate = dict[str, dict[str, AdMetrics]]
SheetRequest = dict[str, object]
AD_COST_ESTIMATE_FORMAT = {"numberFormat": K_YEN_NUMBER_FORMAT}


class AdSalesSheet:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet
        self._ad_rows: dict[str, list[int]] = {}
        self._ad_cost_rows: dict[str, list[int]] = {}
        self._serial_to_column: dict[int, int] = {}

    def get_ad_rows(self) -> dict[str, list[int]]:
        headers = self._worksheet.row_values(HEADER_ROW)
        name_column = find_column(headers, PRODUCT_NAME_HEADER)
        asin_values = self._worksheet.col_values(ASIN_COLUMN)
        name_values = self._worksheet.col_values(name_column)
        self._ad_rows = bind_label_rows(asin_values, name_values, AD_ROW_LABEL)
        self._ad_cost_rows = bind_label_rows(asin_values, name_values, AD_COST_ROW_LABEL)
        return self._ad_rows

    @retry_on_transient_error
    def write_ad_metrics(self, metrics_by_date: MetricsByDate) -> AdWriteResult:
        self._serial_to_column = read_date_columns(self._worksheet)
        columns_by_date = {day: self._columns_for(day) for day in metrics_by_date}
        skipped_dates = tuple(
            day for day, columns in columns_by_date.items() if not columns
        )
        unit_requests = self._requests_for(
            metrics_by_date, columns_by_date, self._ad_rows, attrgetter("units")
        )
        cost_requests = self._requests_for(
            metrics_by_date, columns_by_date, self._ad_cost_rows, attrgetter("cost")
        )
        # batch_update は渡した dict の "range" を in-place でシート名付きに書き換える
        # (sales_sheet.py の write_gross_profit / write_prices と同じ回避)。千円表記は
        # 広告費の行だけに適用するため、対象範囲を batch_update を呼ぶ前に控えておく。
        cost_cells = [request["range"] for request in cost_requests]
        # 広告費の行が1本も無いのに個数だけ書けてしまうと、終了コードは0のまま
        # 広告費の列が永久に空になる。launchd の失敗通知は終了コードでしか鳴らない
        if self._ad_rows and not self._ad_cost_rows:
            raise AdCostRowsNotFoundError(
                f"「{AD_COST_ROW_LABEL}」行が1件も見つかりません"
                f"（広告経由の行は {len(self._ad_rows)} 件ある）"
            )
        requests = unit_requests + cost_requests
        if requests:
            self._worksheet.batch_update(requests, value_input_option="RAW")
        if cost_cells:
            self._worksheet.format(cost_cells, AD_COST_ESTIMATE_FORMAT)
        return AdWriteResult(
            cells_written=len(requests),
            skipped_dates=skipped_dates,
            unit_cells_written=len(unit_requests),
            cost_cells_written=len(cost_requests),
            asins_without_cost_row=tuple(sorted(set(self._ad_rows) - set(self._ad_cost_rows))),
        )

    @staticmethod
    def _requests_for(
        metrics_by_date: MetricsByDate,
        columns_by_date: dict[str, list[int]],
        label_rows: dict[str, list[int]],
        value_of: Callable[[AdMetrics], int | float],
    ) -> list[SheetRequest]:
        # 予約行（行1〜4）には書かない。ラベル行が予約行に来ても個数や広告費で
        # 日付ラベルや総売上を潰さないため（write_sales_nums と同じガード）
        return [
            {"range": rowcol_to_a1(row, column), "values": [[value_of(by_asin.get(asin, AdMetrics()))]]}
            for day, by_asin in metrics_by_date.items()
            for column in columns_by_date[day]
            for asin, rows in label_rows.items()
            for row in rows
            if row > HEADER_ROW
        ]

    def _columns_for(self, day: str) -> list[int]:
        serial = date_serial(datetime.strptime(day, "%Y-%m-%d").date())
        column = self._serial_to_column.get(serial)
        return [column] if column else []

