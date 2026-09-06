from __future__ import annotations

from gspread import Worksheet

from py_src.infrastructure.sheets.label_rows import (
    AD_ROW_LABEL,
    ASIN_COLUMN,
    ASIN_LENGTH,
    HEADER_ROW,
    OPERATING_PROFIT_ROW_LABEL,
    PRODUCT_NAME_HEADER,
    bind_label_rows,
    find_column,
    read_date_columns,
)
from py_src.infrastructure.sheets.retry import retry_on_transient_error

RED = {"red": 0.96, "green": 0.42, "blue": 0.36}
BLUE = {"red": 0.24, "green": 0.52, "blue": 0.78}
WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
GREY = {"red": 0.55, "green": 0.55, "blue": 0.55}


def _gradient(minimum: dict, maximum: dict) -> dict:
    return {
        "minpoint": {"color": minimum, "type": "MIN"},
        "maxpoint": {"color": maximum, "type": "MAX"},
    }


def _grid_range(sheet_id: int, row: int, first_column: int, last_column: int) -> dict:
    return {
        "sheetId": sheet_id,
        "startRowIndex": row - 1,
        "endRowIndex": row,
        "startColumnIndex": first_column - 1,
        "endColumnIndex": last_column,
    }


class GradientRules:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet

    @retry_on_transient_error
    def apply(self) -> int:
        columns = sorted(read_date_columns(self._worksheet).values())
        if not columns:
            return 0
        first, last = columns[0], columns[-1]
        headers = self._worksheet.row_values(HEADER_ROW)
        name_column = find_column(headers, PRODUCT_NAME_HEADER)
        asin_values = self._worksheet.col_values(ASIN_COLUMN)
        name_values = self._worksheet.col_values(name_column)
        sheet_id = self._worksheet.id

        rules = self._build_rules(sheet_id, asin_values, name_values, first, last)
        requests = self._delete_existing() + [
            {"addConditionalFormatRule": {"rule": rule, "index": index}}
            for index, rule in enumerate(rules)
        ]
        self._worksheet.spreadsheet.batch_update({"requests": requests})
        return len(rules)

    def _build_rules(
        self,
        sheet_id: int,
        asin_values: list[str],
        name_values: list[str],
        first: int,
        last: int,
    ) -> list[dict]:
        ad_rows = bind_label_rows(asin_values, name_values, AD_ROW_LABEL)
        operating_rows = bind_label_rows(
            asin_values, name_values, OPERATING_PROFIT_ROW_LABEL
        )
        rules: list[dict] = []
        for asin, rows in ad_rows.items():
            for ad_row in rows:
                # 売上個数（ASIN行）と広告経由の個数を1つのスケールに載せる。
                # 商品ごとに独立させないと、販売数の多い商品以外が同じ色になる
                asin_row = ad_row - 1
                if asin_row <= HEADER_ROW:
                    continue
                rules.append({
                    "ranges": [
                        _grid_range(sheet_id, asin_row, first, last),
                        _grid_range(sheet_id, ad_row, first, last),
                    ],
                    "gradientRule": _gradient(RED, BLUE),
                })
        for rows in operating_rows.values():
            for row in rows:
                if row <= HEADER_ROW:
                    continue
                rules.append({
                    "ranges": [_grid_range(sheet_id, row, first, last)],
                    "gradientRule": _gradient(WHITE, GREY),
                })
        return rules

    def _delete_existing(self) -> list[dict]:
        # 付け直しなので古い規則を先に消す。残すと同じ範囲に何重にも積み上がる。
        # index 0 を消すと後ろが繰り上がるため、常に 0 を指定して件数分送る
        existing = self._worksheet.spreadsheet.fetch_sheet_metadata(
            {"fields": "sheets(properties(sheetId),conditionalFormats)"}
        )
        for sheet in existing.get("sheets", []):
            if sheet.get("properties", {}).get("sheetId") != self._worksheet.id:
                continue
            count = len(sheet.get("conditionalFormats", []))
            return [
                {"deleteConditionalFormatRule": {"sheetId": self._worksheet.id, "index": 0}}
                for _ in range(count)
            ]
        return []
