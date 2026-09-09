from __future__ import annotations

from statistics import median
from typing import Callable

from gspread import Worksheet
from gspread.utils import ValueRenderOption, rowcol_to_a1

from py_src.infrastructure.sheets.label_rows import (
    AD_ROW_LABEL,
    ASIN_COLUMN,
    ASIN_LENGTH,
    HEADER_ROW,
    OPERATING_PROFIT_ROW_LABEL,
    PRODUCT_NAME_HEADER,
    RANK_ROW_LABEL,
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
# 営業利益がマイナスの日は最上級に目立たせる。グラデーションより前に置くことで
# こちらが優先される（条件付き書式は上にある規則が勝つ）。
# 0 は含めない。売れなかった日の 0 が大半で、赤くしても打つ手が無い
# （実データで 0 以下は 38% あり、うち 93% がちょうど 0 だった）
NEGATIVE_PROFIT_FORMAT = {
    "backgroundColor": {"red": 0.78, "green": 0.16, "blue": 0.13},
    "textFormat": {"foregroundColor": WHITE, "bold": True},
}


# 中央値は直近この日数から取る。暦の1ヶ月だと月初に数日ぶんしか残らず、
# その数日の出来不出来で白の位置が飛ぶ
RECENT_DAYS = 30
FIRST_VALUE_ROW = HEADER_ROW + 1


def _number(value: float) -> str:
    # 中央値は偶数日だと .5 になる。9.0 は "9"、9.5 は "9.5" にする
    return f"{value:g}"


def _gradient_around_median(minimum: dict, maximum: dict, center: float) -> dict:
    # その商品にとって普通の日を白にする。MIN〜MAX の2点だと、ふだんより
    # 売れた日なのか売れなかった日なのかが色から読めない
    if center <= 0:
        # 中央値が0のとき midpoint に0を置くと minpoint とぶつかって赤が出ない。
        # 売れなかった日を白、売れた日だけを青にする
        return {
            "minpoint": {"color": WHITE, "type": "NUMBER", "value": "0"},
            "maxpoint": {"color": maximum, "type": "MAX"},
        }
    return {
        "minpoint": {"color": minimum, "type": "MIN"},
        "midpoint": {"color": WHITE, "type": "NUMBER", "value": _number(center)},
        "maxpoint": {"color": maximum, "type": "MAX"},
    }


def recent_columns(date_columns: dict[int, int], recent_days: int = RECENT_DAYS) -> list[int]:
    if not date_columns:
        return []
    latest = max(date_columns)
    return sorted(
        column
        for serial, column in date_columns.items()
        if latest - serial < recent_days
    )


def median_of_row(
    grid: list[list], first_column: int, row: int, columns: list[int]
) -> float:
    # 空セルは「まだ取っていない日」なので母数から外す。0 は「売れなかった日」
    # で、外すと中央値が実態より高く出る。bool は int の派生なので除く
    index = row - FIRST_VALUE_ROW
    if index < 0 or index >= len(grid):
        return 0.0
    line = grid[index]
    values = []
    for column in columns:
        offset = column - first_column
        if offset < 0 or offset >= len(line):
            continue
        value = line[offset]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        values.append(float(value))
    return median(values) if values else 0.0


def _gradient_from_zero(maximum: dict) -> dict:
    # 0円を白に固定し、その商品の最大益を青にする。金額で上限を固定すると
    # 規模の小さい商品が好調な日でも白のままになり、その商品の中での
    # 良し悪しが読めない。0 を白にするのは、MIN を白にすると最も薄利な日が
    # 白になって黒字か赤字かが色から読めなくなるため
    return {
        "minpoint": {"color": WHITE, "type": "NUMBER", "value": "0"},
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


# 4行目のヘッダーには "Column 133" のような自動採番が混ざっていて列を特定できない。
# 1行目の英語キーで引く（listing-creator の key_column_map と同じ考え方）
KEY_ROW = 1
COLUMN_GRADIENT_KEYS: tuple[str, ...] = ("PROFIT_RATE",)


def _column_grid_range(sheet_id: int, column: int, last_row: int) -> dict:
    return {
        "sheetId": sheet_id,
        "startRowIndex": HEADER_ROW,
        "endRowIndex": last_row,
        "startColumnIndex": column - 1,
        "endColumnIndex": column,
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
        date_columns = read_date_columns(self._worksheet)
        columns = sorted(date_columns.values())
        if not columns:
            return 0
        first, last = columns[0], columns[-1]
        headers = self._worksheet.row_values(HEADER_ROW)
        name_column = find_column(headers, PRODUCT_NAME_HEADER)
        asin_values = self._worksheet.col_values(ASIN_COLUMN)
        name_values = self._worksheet.col_values(name_column)
        median_for = self._median_reader(recent_columns(date_columns))
        sheet_id = self._worksheet.id

        rules = self._build_rules(
            sheet_id, asin_values, name_values, first, last, median_for
        )
        rules += self._column_rules(sheet_id)
        requests = self._delete_existing(first, last) + [
            {"addConditionalFormatRule": {"rule": rule, "index": index}}
            for index, rule in enumerate(rules)
        ]
        self._worksheet.spreadsheet.batch_update({"requests": requests})
        return len(rules)

    def _median_reader(self, columns: list[int]) -> Callable[[int], float]:
        # 中央値は行ごとに要るが、1行ずつ読むと商品数ぶんのリクエストになる。
        # 直近ぶんの矩形を1回で取り、そこから引く
        if not columns:
            return lambda row: 0.0
        first_column = columns[0]
        grid = self._worksheet.get_values(
            f"{rowcol_to_a1(FIRST_VALUE_ROW, first_column)}"
            f":{rowcol_to_a1(self._worksheet.row_count, columns[-1])}",
            value_render_option=ValueRenderOption.unformatted,
        )
        return lambda row: median_of_row(grid, first_column, row, columns)

    def _build_rules(
        self,
        sheet_id: int,
        asin_values: list[str],
        name_values: list[str],
        first: int,
        last: int,
        median_for: Callable[[int], float],
    ) -> list[dict]:
        # ブロックの起点は先頭ラベルから取る。「広告経由の1つ上が ASIN 行」と
        # 決め打つと、ラベルを並べ替えたときに別の行を掴む
        first_label_rows = bind_label_rows(
            asin_values, name_values, ROW_LABELS_IN_ORDER[0]
        )
        ad_offset = ROW_LABELS_IN_ORDER.index(AD_ROW_LABEL)
        operating_offset = ROW_LABELS_IN_ORDER.index(OPERATING_PROFIT_ROW_LABEL)
        rank_offset = ROW_LABELS_IN_ORDER.index(RANK_ROW_LABEL)
        rules: list[dict] = []
        operating_ranges: list[dict] = []
        for rows in first_label_rows.values():
            for first_label in rows:
                asin_row = first_label - 1
                if asin_row <= HEADER_ROW:
                    continue
                # 売上個数（ASIN行）と広告経由は別のスケールに載せる。広告経由は
                # 総売上より必ず小さいので、総売上の中央値を白にすると広告経由行が
                # まるごと赤に沈む。商品ごとに独立させるのは、1つのスケールに
                # 載せると販売数の多い商品以外が同じ色になるため
                for row in (asin_row, first_label + ad_offset):
                    rules.append({
                        "ranges": [_grid_range(sheet_id, row, first, last)],
                        "gradientRule": _gradient_around_median(
                            PALE_RED, PALE_BLUE, median_for(row)
                        ),
                    })
                # 営業利益も個数と同じく商品ごとのスケールにする。商品ごとに
                # 桁が違うため、1つのスケールに載せると規模の小さい商品が
                # すべて白に潰れる
                operating_range = _grid_range(
                    sheet_id, first_label + operating_offset, first, last
                )
                operating_ranges.append(operating_range)
                # 順位は小さいほど良い。MIN（最上位）を青、MAX（最下位）を赤にする。
                # 個数と同じうすい色にして、行の種類は位置で見分ける
                rules.append({
                    "ranges": [
                        _grid_range(sheet_id, first_label + rank_offset, first, last)
                    ],
                    "gradientRule": {
                        "minpoint": {"color": PALE_BLUE, "type": "MIN"},
                        "maxpoint": {"color": PALE_RED, "type": "MAX"},
                    },
                })
                rules.append({
                    "ranges": [operating_range],
                    "gradientRule": _gradient_from_zero(DEEP_BLUE),
                })
        if operating_ranges:
            # 0 以下の判定を先に入れる。後ろのグラデーションは残りの日に効く
            rules.insert(0, {
                "ranges": operating_ranges,
                "booleanRule": {
                    "condition": {
                        "type": "NUMBER_LESS",
                        "values": [{"userEnteredValue": "0"}],
                    },
                    "format": NEGATIVE_PROFIT_FORMAT,
                },
            })
        return rules

    def _column_rules(self, sheet_id: int) -> list[dict]:
        # 利益率のような「列そのもの」を色分けするもの。0 を白に固定し、
        # マイナスは赤、プラスは青にする（営業利益と同じ読み方にそろえる）
        keys = self._worksheet.row_values(KEY_ROW)
        last_row = self._worksheet.row_count
        rules = []
        for key in COLUMN_GRADIENT_KEYS:
            try:
                column = find_column(keys, key)
            except ValueError:
                continue
            rules.append({
                "ranges": [_column_grid_range(sheet_id, column, last_row)],
                "gradientRule": _gradient_around_zero(DEEP_RED, DEEP_BLUE),
            })
        return rules

    def _managed_columns(self) -> set[int]:
        keys = self._worksheet.row_values(KEY_ROW)
        columns = set()
        for key in COLUMN_GRADIENT_KEYS:
            try:
                columns.add(find_column(keys, key))
            except ValueError:
                continue
        return columns

    def _delete_existing(self, first: int, last: int) -> list[dict]:
        # **自分が入れた規則だけ**を消す。以前は全件削除していたため、シートに
        # 元からあった条件付き書式（在庫日数の警告など）を巻き込んで消し、
        # 下地の直接指定が露出した。日付列だけを対象にしたグラデーション規則を
        # 自分のものと見なす。index を消すと後ろが繰り上がるので降順に消す
        managed = self._managed_columns()
        existing = self._worksheet.spreadsheet.fetch_sheet_metadata(
            {"fields": "sheets(properties(sheetId),conditionalFormats(ranges,gradientRule))"}
        )
        for sheet in existing.get("sheets", []):
            if sheet.get("properties", {}).get("sheetId") != self._worksheet.id:
                continue
            mine = [
                index
                for index, rule in enumerate(sheet.get("conditionalFormats", []))
                if _is_own_rule(rule, first, last, managed)
            ]
            return [
                {"deleteConditionalFormatRule": {"sheetId": self._worksheet.id, "index": index}}
                for index in sorted(mine, reverse=True)
            ]
        return []


def _is_own_rule(rule: dict, first: int, last: int, managed_columns: set[int]) -> bool:
    if "gradientRule" not in rule and not _is_negative_profit_rule(rule):
        return False
    ranges = rule.get("ranges", [])
    if not ranges:
        return False
    return all(_is_own_range(r, first, last, managed_columns) for r in ranges)


def _is_own_range(grid: dict, first: int, last: int, managed_columns: set[int]) -> bool:
    # 日付列を横断する1行ぶんの範囲か、自分が面倒を見ている列の縦1本か
    row_span = grid.get("endRowIndex", 0) - grid.get("startRowIndex", 0)
    if (
        grid.get("startColumnIndex") == first - 1
        and grid.get("endColumnIndex") == last
        and row_span == 1
    ):
        return True
    return (
        grid.get("startColumnIndex", -1) + 1 in managed_columns
        and grid.get("endColumnIndex") == grid.get("startColumnIndex", 0) + 1
    )


def _is_negative_profit_rule(rule: dict) -> bool:
    condition = rule.get("booleanRule", {}).get("condition", {})
    return (
        condition.get("type") == "NUMBER_LESS"
        and condition.get("values", [{}])[0].get("userEnteredValue") == "0"
    )
