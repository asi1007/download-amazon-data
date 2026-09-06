from __future__ import annotations

from gspread import Worksheet

from py_src.infrastructure.sheets.label_rows import (
    AD_ROW_LABEL,
    ASIN_COLUMN,
    ASIN_LENGTH,
    HEADER_ROW,
    OPERATING_PROFIT_ROW_LABEL,
    PRODUCT_NAME_HEADER,
    ROW_LABELS_IN_ORDER,
    bind_label_rows,
    find_column,
    read_date_columns,
)
from py_src.infrastructure.sheets.retry import retry_on_transient_error

# 悪い = 赤、良い = 青で全行そろえる。行の種類は色味の濃さで見分ける。
# 個数はうすい（毎日ぱっと眺める行）、営業利益は濃い（判断に使う行）
WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
PALE_RED = {"red": 0.97, "green": 0.75, "blue": 0.72}
PALE_BLUE = {"red": 0.72, "green": 0.83, "blue": 0.94}
DEEP_RED = {"red": 0.84, "green": 0.19, "blue": 0.16}
DEEP_BLUE = {"red": 0.11, "green": 0.35, "blue": 0.65}


def _gradient(minimum: dict, maximum: dict) -> dict:
    return {
        "minpoint": {"color": minimum, "type": "MIN"},
        "maxpoint": {"color": maximum, "type": "MAX"},
    }


def _gradient_around_zero(minimum: dict, maximum: dict) -> dict:
    # 0 を白に固定する。MIN を白にすると「最も赤字の日」が白になってしまい、
    # 黒字か赤字かが色から読めない
    return {
        "minpoint": {"color": minimum, "type": "MIN"},
        "midpoint": {"color": WHITE, "type": "NUMBER", "value": "0"},
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
        requests = self._delete_existing(first, last) + [
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
        # ブロックの起点は先頭ラベルから取る。「広告経由の1つ上が ASIN 行」と
        # 決め打つと、ラベルを並べ替えたときに別の行を掴む
        first_label_rows = bind_label_rows(
            asin_values, name_values, ROW_LABELS_IN_ORDER[0]
        )
        ad_offset = ROW_LABELS_IN_ORDER.index(AD_ROW_LABEL)
        operating_offset = ROW_LABELS_IN_ORDER.index(OPERATING_PROFIT_ROW_LABEL)
        rules: list[dict] = []
        operating_ranges: list[dict] = []
        for rows in first_label_rows.values():
            for first_label in rows:
                asin_row = first_label - 1
                if asin_row <= HEADER_ROW:
                    continue
                # 売上個数（ASIN行）と広告経由の個数を1つのスケールに載せる。
                # 商品ごとに独立させないと、販売数の多い商品以外が同じ色になる
                rules.append({
                    "ranges": [
                        _grid_range(sheet_id, asin_row, first, last),
                        _grid_range(sheet_id, first_label + ad_offset, first, last),
                    ],
                    "gradientRule": _gradient(PALE_RED, PALE_BLUE),
                })
                operating_ranges.append(
                    _grid_range(sheet_id, first_label + operating_offset, first, last)
                )
        # 営業利益は全商品で1つのスケールにする。0円を白に固定してあるので、
        # 同じ金額なら商品をまたいで同じ色になり、金額そのものを比べられる。
        # 個数は商品ごとに桁が違うため、こちらは商品ごとのスケールのままにする
        if operating_ranges:
            rules.append({
                "ranges": operating_ranges,
                "gradientRule": _gradient_around_zero(DEEP_RED, DEEP_BLUE),
            })
        return rules

    def _delete_existing(self, first: int, last: int) -> list[dict]:
        # **自分が入れた規則だけ**を消す。以前は全件削除していたため、シートに
        # 元からあった条件付き書式（在庫日数の警告など）を巻き込んで消し、
        # 下地の直接指定が露出した。日付列だけを対象にしたグラデーション規則を
        # 自分のものと見なす。index を消すと後ろが繰り上がるので降順に消す
        existing = self._worksheet.spreadsheet.fetch_sheet_metadata(
            {"fields": "sheets(properties(sheetId),conditionalFormats(ranges,gradientRule))"}
        )
        for sheet in existing.get("sheets", []):
            if sheet.get("properties", {}).get("sheetId") != self._worksheet.id:
                continue
            mine = [
                index
                for index, rule in enumerate(sheet.get("conditionalFormats", []))
                if _is_own_rule(rule, first, last)
            ]
            return [
                {"deleteConditionalFormatRule": {"sheetId": self._worksheet.id, "index": index}}
                for index in sorted(mine, reverse=True)
            ]
        return []


def _is_own_rule(rule: dict, first: int, last: int) -> bool:
    if "gradientRule" not in rule:
        return False
    ranges = rule.get("ranges", [])
    if not ranges:
        return False
    return all(
        r.get("startColumnIndex") == first - 1 and r.get("endColumnIndex") == last
        and r.get("endRowIndex", 0) - r.get("startRowIndex", 0) == 1
        for r in ranges
    )
