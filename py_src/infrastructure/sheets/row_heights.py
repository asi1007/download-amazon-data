from __future__ import annotations

from gspread import Worksheet

from py_src.infrastructure.sheets.label_rows import (
    ASIN_COLUMN,
    HEADER_ROW,
    PRODUCT_NAME_HEADER,
    ROW_LABELS_IN_ORDER,
    bind_label_rows,
    find_column,
)
from py_src.infrastructure.sheets.retry import retry_on_transient_error

# ラベル行の並びは変わりうるので、ブロックの起点は必ず先頭ラベルから取る。
# 「広告経由の1つ上が ASIN 行」と決め打つと、並べ替えたときに次の商品の
# ASIN 行まで縮めてしまう（実際に72行を潰した）
FIRST_LABEL = ROW_LABELS_IN_ORDER[0]
ASIN_ROW_HEIGHT = 39
LABEL_ROW_HEIGHT = ASIN_ROW_HEIGHT // 2


def plan_row_heights(first_label_rows: dict[str, list[int]]) -> list[tuple[int, int, int]]:
    plan: list[tuple[int, int, int]] = []
    for rows in first_label_rows.values():
        for first in rows:
            if first - 1 <= HEADER_ROW:
                continue
            plan.append((first - 1, first - 1, ASIN_ROW_HEIGHT))
            plan.append((first, first + len(ROW_LABELS_IN_ORDER) - 1, LABEL_ROW_HEIGHT))
    return sorted(plan)


class RowHeights:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet

    @retry_on_transient_error
    def shrink_label_rows(self) -> int:
        headers = self._worksheet.row_values(HEADER_ROW)
        name_column = find_column(headers, PRODUCT_NAME_HEADER)
        first_label_rows = bind_label_rows(
            self._worksheet.col_values(ASIN_COLUMN),
            self._worksheet.col_values(name_column),
            FIRST_LABEL,
        )
        plan = plan_row_heights(first_label_rows)
        if not plan:
            return 0
        sheet_id = self._worksheet.id
        requests = [
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": first - 1,
                        "endIndex": last,
                    },
                    "properties": {"pixelSize": height},
                    "fields": "pixelSize",
                }
            }
            for first, last, height in plan
        ]
        self._worksheet.spreadsheet.batch_update({"requests": requests})
        return sum(last - first + 1 for first, last, _ in plan)
