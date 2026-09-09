from __future__ import annotations

from gspread import Worksheet

from py_src.infrastructure.sheets.label_rows import (
    ASIN_COLUMN,
    COLLAPSIBLE_ROW_LABELS,
    HEADER_ROW,
    OPERATING_PROFIT_ROW_LABEL,
    PRODUCT_NAME_HEADER,
    bind_label_rows,
    find_column,
)
from py_src.infrastructure.sheets.retry import retry_on_transient_error


def plan_groups(operating_rows: dict[str, list[int]]) -> list[tuple[int, int]]:
    # 営業利益の1つ下から、たたむラベル行のぶんだけをグループにする。
    # ASIN行（売上個数）と営業利益はたたんだ状態でも見えたままになる
    return sorted(
        (row + 1, row + len(COLLAPSIBLE_ROW_LABELS))
        for rows in operating_rows.values()
        for row in rows
        if row > HEADER_ROW
    )


class RowGroups:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet

    @retry_on_transient_error
    def collapse_label_rows(self) -> int:
        headers = self._worksheet.row_values(HEADER_ROW)
        name_column = find_column(headers, PRODUCT_NAME_HEADER)
        operating_rows = bind_label_rows(
            self._worksheet.col_values(ASIN_COLUMN),
            self._worksheet.col_values(name_column),
            OPERATING_PROFIT_ROW_LABEL,
        )
        plan = plan_groups(operating_rows)
        if not plan:
            return 0
        sheet_id = self._worksheet.id
        requests = self._delete_existing(sheet_id)
        for first, last in plan:
            grid = {
                "sheetId": sheet_id,
                "dimension": "ROWS",
                "startIndex": first - 1,
                "endIndex": last,
            }
            requests.append({"addDimensionGroup": {"range": grid}})
            requests.append({
                "updateDimensionGroup": {
                    "dimensionGroup": {"range": grid, "depth": 1, "collapsed": True},
                    "fields": "collapsed",
                }
            })
        self._worksheet.spreadsheet.batch_update({"requests": requests})
        return len(plan)

    @retry_on_transient_error
    def collapse_expanded(self) -> int:
        # 人が中を見るために開いた行を閉じ直すだけ。範囲の作り直しは
        # write_sales_sheet.py（新商品の挿入時）と apply_row_groups.py の役目で、
        # ここで作り直すと新商品の追加漏れを隠してしまう
        expanded = [
            group
            for group in self._existing_groups(self._worksheet.id)
            if not group.get("collapsed")
        ]
        if not expanded:
            return 0
        self._worksheet.spreadsheet.batch_update({
            "requests": [
                {
                    "updateDimensionGroup": {
                        "dimensionGroup": {
                            "range": group["range"],
                            "depth": group.get("depth", 1),
                            "collapsed": True,
                        },
                        "fields": "collapsed",
                    }
                }
                for group in expanded
            ]
        })
        return len(expanded)

    def _existing_groups(self, sheet_id: int) -> list[dict]:
        metadata = self._worksheet.spreadsheet.fetch_sheet_metadata(
            {"fields": "sheets(properties(sheetId),rowGroups(range,depth,collapsed))"}
        )
        for sheet in metadata.get("sheets", []):
            if sheet.get("properties", {}).get("sheetId") == sheet_id:
                return sheet.get("rowGroups", [])
        return []

    def _delete_existing(self, sheet_id: int) -> list[dict]:
        # 作り直しなので古いグループを消す。残すと同じ範囲に入れ子で積み上がる
        return [
            {"deleteDimensionGroup": {"range": group["range"]}}
            for group in sorted(
                self._existing_groups(sheet_id), key=lambda g: -g.get("depth", 1)
            )
        ]
