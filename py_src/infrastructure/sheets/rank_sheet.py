from __future__ import annotations

from gspread import Worksheet
from gspread.utils import ValueRenderOption

from py_src.infrastructure.sheets.label_rows import (
    ASIN_COLUMN,
    HEADER_ROW,
    PRODUCT_NAME_HEADER,
    find_column,
)
from py_src.infrastructure.sheets.retry import retry_on_transient_error


class RankSheet:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet

    @retry_on_transient_error
    def read_grid(self) -> tuple[list[str], list[str], list[object]]:
        # 日付列はシリアル整数で持っている。書式付きで読むと "09" のような
        # 文字列になり、日付として引けない
        header = self._worksheet.row_values(
            HEADER_ROW, value_render_option=ValueRenderOption.unformatted
        )
        name_column = find_column(header, PRODUCT_NAME_HEADER)
        values = self._worksheet.get_all_values()
        asins = [_at(row, ASIN_COLUMN) for row in values]
        names = [_at(row, name_column) for row in values]
        return asins, names, header

    @retry_on_transient_error
    def apply_updates(self, updates: list[dict]) -> None:
        if not updates:
            return
        self._worksheet.batch_update(updates, value_input_option="USER_ENTERED")


def _at(row: list[str], column: int) -> str:
    return row[column - 1].strip() if len(row) >= column else ""
