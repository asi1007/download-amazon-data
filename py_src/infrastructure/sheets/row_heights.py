from __future__ import annotations

from gspread import Worksheet

from py_src.infrastructure.sheets.label_rows import (
    AD_ROW_LABEL,
    ASIN_COLUMN,
    HEADER_ROW,
    PRODUCT_NAME_HEADER,
    ROW_LABELS_IN_ORDER,
    bind_label_rows,
    find_column,
)
from py_src.infrastructure.sheets.retry import retry_on_transient_error

MINIMUM_LABEL_ROW_HEIGHT = 10
DEFAULT_ASIN_ROW_HEIGHT = 39


def plan_label_row_heights(
    ad_rows: dict[str, list[int]], heights: dict[int, int]
) -> list[tuple[int, int, int]]:
    # ラベル行は ASIN 行の直後に ROW_LABELS_IN_ORDER 本ぶん続く。まとめて1件の
    # updateDimensionProperties にできるので、商品ごとに1リクエストで済む
    plan: list[tuple[int, int, int]] = []
    for rows in ad_rows.values():
        for ad_row in rows:
            asin_row = ad_row - 1
            if asin_row <= HEADER_ROW:
                continue
            asin_height = heights.get(asin_row, DEFAULT_ASIN_ROW_HEIGHT)
            height = max(asin_height // 2, MINIMUM_LABEL_ROW_HEIGHT)
            plan.append((ad_row, ad_row + len(ROW_LABELS_IN_ORDER) - 1, height))
    return sorted(plan)


class RowHeights:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet

    @retry_on_transient_error
    def shrink_label_rows(self) -> int:
        headers = self._worksheet.row_values(HEADER_ROW)
        name_column = find_column(headers, PRODUCT_NAME_HEADER)
        ad_rows = bind_label_rows(
            self._worksheet.col_values(ASIN_COLUMN),
            self._worksheet.col_values(name_column),
            AD_ROW_LABEL,
        )
        plan = plan_label_row_heights(ad_rows, self._read_heights())
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

    def _read_heights(self) -> dict[int, int]:
        metadata = self._worksheet.spreadsheet.fetch_sheet_metadata({
            "fields": "sheets(properties(sheetId),data(rowMetadata(pixelSize)))",
            "ranges": [f"{self._worksheet.title}!A1:A"],
        })
        for sheet in metadata.get("sheets", []):
            if sheet.get("properties", {}).get("sheetId") != self._worksheet.id:
                continue
            rows = sheet.get("data", [{}])[0].get("rowMetadata", [])
            return {
                index: row["pixelSize"]
                for index, row in enumerate(rows, start=1)
                if row.get("pixelSize")
            }
        return {}
