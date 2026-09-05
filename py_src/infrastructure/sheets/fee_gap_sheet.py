from __future__ import annotations
from datetime import datetime

import gspread
from gspread import Spreadsheet

from py_src.domain.value_objects.fee_gap import FeeGap
from py_src.infrastructure.sheets.retry import retry_on_transient_error

FEE_GAP_SHEET_NAME = "手数料乖離"
HEADER = ["ASIN", "商品名", "個数", "見積/個", "実測/個", "差/個", "差%", "更新"]
INITIAL_ROWS = 200
INITIAL_COLUMNS = len(HEADER)
PRODUCT_URL_PREFIX = "https://www.amazon.co.jp/dp/"


class FeeGapSheet:
    def __init__(self, spreadsheet: Spreadsheet) -> None:
        self._spreadsheet = spreadsheet

    @retry_on_transient_error
    def write(
        self, gaps: list[FeeGap], names: dict[str, str], updated_at: datetime
    ) -> int:
        worksheet = self._worksheet()
        stamp = updated_at.strftime("%Y-%m-%d %H:%M")
        values = [HEADER] + [
            [
                f'=HYPERLINK("{PRODUCT_URL_PREFIX}{gap.asin}","{gap.asin}")',
                names.get(gap.asin, ""),
                gap.quantity,
                round(gap.estimated_unit_fee, 1),
                round(gap.actual_unit_fee, 1),
                round(gap.difference, 1),
                round(gap.ratio, 3),
                stamp,
            ]
            for gap in gaps
        ]
        # 前回より対象が減ったとき、古い行が残ると直したはずの商品が残り続ける
        worksheet.clear()
        worksheet.update(values, value_input_option="USER_ENTERED")
        return len(gaps)

    def _worksheet(self) -> gspread.Worksheet:
        try:
            return self._spreadsheet.worksheet(FEE_GAP_SHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            return self._spreadsheet.add_worksheet(
                title=FEE_GAP_SHEET_NAME, rows=INITIAL_ROWS, cols=INITIAL_COLUMNS
            )
