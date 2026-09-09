from unittest.mock import Mock

from gspread import Worksheet

from py_src.infrastructure.sheets.gradient_rules import (
    DEEP_BLUE,
    DEEP_RED,
    PALE_BLUE,
    PALE_RED,
    WHITE,
    GradientRules,
)
from py_src.infrastructure.sheets.label_rows import ROW_LABELS_IN_ORDER


# 行5 = B00EXAMPLE の売上個数、行7 = その広告経由、行10/12 が2商品目。
# 日付列は2列なので、中央値は2つの値の平均になる
COUNT_VALUES: dict = {
    5: [10, 4],
    7: [4, 2],
    11: [20, 8],
    13: [6, 4],
}
FIRST_VALUE_ROW = 5
LAST_VALUE_ROW = 16


def _grid(values: dict) -> list:
    return [values.get(row, []) for row in range(FIRST_VALUE_ROW, LAST_VALUE_ROW + 1)]


def _worksheet(
    existing_rules: int = 0,
    date_header: tuple = (46269, 46268),
    values: dict = None,
    keys: list = None,
) -> Mock:
    worksheet = Mock(spec=Worksheet)
    worksheet.id = 0
    worksheet.row_count = 400
    worksheet.row_values.side_effect = lambda row, **kwargs: (
        (["ASIN_SELL", "", "", "", "PROFIT_RATE"] if keys is None else keys) if row == 1
        else ["ASIN", "商品名", *date_header]
    )
    worksheet.get_values.side_effect = lambda *args, **kwargs: _grid(
        COUNT_VALUES if values is None else values
    )
    col_a = ["", "", "", "ASIN", "B00EXAMPLE"] + [""] * 5 + ["B00EXAMPLF"] + [""] * 5
    labels = list(ROW_LABELS_IN_ORDER)
    col_name = ["", "", "", "商品名", "ルーペ"] + labels + ["ボール"] + labels
    worksheet.col_values.side_effect = lambda col, **kwargs: col_a if col == 1 else col_name
    worksheet.spreadsheet.fetch_sheet_metadata.return_value = {
        "sheets": [{"properties": {"sheetId": 0},
                    "conditionalFormats": [{} for _ in range(existing_rules)]}]
    }
    return worksheet


def _operating_rules(worksheet: Mock) -> list[dict]:
    # 行の種類は色の濃さで見分ける。minpoint の type では、中央値0の個数行が
    # 営業利益と同じ NUMBER になるため区別できない
    return [r for r in _rules(worksheet)
            if "gradientRule" in r and r["ranges"][0].get("endRowIndex") != 400
            and r["gradientRule"]["maxpoint"]["color"] == DEEP_BLUE]


def _operating_gradient(worksheet: Mock) -> dict:
    return _operating_rules(worksheet)[0]["gradientRule"]


def _count_rules(worksheet: Mock) -> list[dict]:
    return [r for r in _rules(worksheet)
            if "gradientRule" in r
            and r["gradientRule"]["maxpoint"]["color"] == PALE_BLUE]


def _count_rule_at(worksheet: Mock, row: int) -> dict:
    return next(r for r in _count_rules(worksheet)
                if r["ranges"][0]["startRowIndex"] == row - 1)


def _rules(worksheet: Mock) -> list[dict]:
    requests = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]
    return [r["addConditionalFormatRule"]["rule"] for r in requests
            if "addConditionalFormatRule" in r]


class TestGradientRules:
    def test_one_rule_per_row_for_the_count_rows(self) -> None:
        # 個数は商品ごとに桁が違う。1つのスケールに載せると、販売数の多い商品
        # 以外がすべて同じ色になる
        worksheet = _worksheet()

        # 商品2件 × (個数1本 + 広告経由1本 + 営業利益1本 + 順位1本)
        # + 赤字の判定1本 + 利益率の列1本
        assert GradientRules(worksheet).apply() == 10
        count_rules = _count_rules(worksheet)
        assert len(count_rules) == 4
        assert all(len(r["ranges"]) == 1 for r in count_rules)

    def test_the_asin_row_and_the_ad_row_get_separate_rules(self) -> None:
        # 広告経由は総売上より必ず小さい。同じスケールに載せると、総売上の
        # 中央値を白にしたときに広告経由行がまるごと赤に沈む
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        rows = sorted(r["ranges"][0]["startRowIndex"] for r in _count_rules(worksheet))
        # 0起点。ASIN行（行5・行10）と広告経由行（行7・行12）
        assert rows == [4, 6, 10, 12]
        first = _count_rule_at(worksheet, 5)["ranges"][0]
        assert first["startColumnIndex"] == 2
        assert first["endColumnIndex"] == 4

    def test_counts_go_red_to_blue_in_a_pale_tone(self) -> None:
        # 悪い = 赤、良い = 青で全行そろえ、行の種類は色味の濃さで見分ける
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        gradient = _count_rule_at(worksheet, 5)["gradientRule"]
        assert gradient["minpoint"] == {"color": PALE_RED, "type": "MIN"}
        assert gradient["maxpoint"] == {"color": PALE_BLUE, "type": "MAX"}

    def test_operating_profit_scales_per_product(self) -> None:
        # 商品ごとに営業利益の桁が違う。金額で上限を固定すると、規模の小さい
        # 商品は好調な日でも白のままになり、その商品の中での良し悪しが読めない
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        gradient = _operating_gradient(worksheet)
        # 0円は白に固定する。MIN を白にすると最も薄利な日が白になり、
        # 黒字か赤字かが色から読めない
        assert gradient["minpoint"] == {"color": WHITE, "type": "NUMBER", "value": "0"}
        assert gradient["maxpoint"] == {"color": DEEP_BLUE, "type": "MAX"}
        assert "midpoint" not in gradient

    def test_operating_profit_rule_is_separate_per_product(self) -> None:
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        operating = _operating_rules(worksheet)
        assert [r["ranges"][0]["startRowIndex"] for r in operating] == [5, 11]
        assert all(len(r["ranges"]) == 1 for r in operating)

    def test_only_own_rules_are_deleted(self) -> None:
        # 全件削除していたため、シートに元からあった条件付き書式（在庫日数の
        # 警告など）を巻き込んで消し、下地の直接指定が露出した
        worksheet = _worksheet()
        worksheet.spreadsheet.fetch_sheet_metadata.return_value = {
            "sheets": [{
                "properties": {"sheetId": 0},
                "conditionalFormats": [
                    {"booleanRule": {}, "ranges": [{"startColumnIndex": 18, "endColumnIndex": 19}]},
                    {"gradientRule": {}, "ranges": [
                        {"startColumnIndex": 2, "endColumnIndex": 4,
                         "startRowIndex": 4, "endRowIndex": 5},
                    ]},
                    {"gradientRule": {}, "ranges": [{"startColumnIndex": 60, "endColumnIndex": 61}]},
                ],
            }]
        }

        GradientRules(worksheet).apply()

        requests = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]
        deletes = [r["deleteConditionalFormatRule"]["index"] for r in requests
                   if "deleteConditionalFormatRule" in r]
        assert deletes == [1]

    def test_deletes_go_from_the_back_so_indexes_stay_valid(self) -> None:
        worksheet = _worksheet()
        own = {"gradientRule": {}, "ranges": [
            {"startColumnIndex": 2, "endColumnIndex": 4, "startRowIndex": 4, "endRowIndex": 5},
        ]}
        worksheet.spreadsheet.fetch_sheet_metadata.return_value = {
            "sheets": [{"properties": {"sheetId": 0}, "conditionalFormats": [own, own, own]}]
        }

        GradientRules(worksheet).apply()

        requests = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]
        deletes = [r["deleteConditionalFormatRule"]["index"] for r in requests
                   if "deleteConditionalFormatRule" in r]
        assert deletes == [2, 1, 0]

    def test_no_date_columns_means_no_rules(self) -> None:
        worksheet = _worksheet()
        worksheet.row_values.side_effect = lambda row, **kwargs: ["ASIN", "商品名"]

        assert GradientRules(worksheet).apply() == 0


class TestColumnGradients:
    def test_profit_rate_column_is_pinned_to_zero(self) -> None:
        # 4行目のヘッダーは "Column 133" のような自動採番なので1行目のキーで引く
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        column_rules = [r for r in _rules(worksheet)
                        if "gradientRule" in r and r["ranges"][0].get("endRowIndex") == 400]
        assert len(column_rules) == 1
        grid = column_rules[0]["ranges"][0]
        assert grid["startColumnIndex"] == 4
        assert grid["endColumnIndex"] == 5
        gradient = column_rules[0]["gradientRule"]
        assert gradient["minpoint"] == {"color": DEEP_RED, "type": "MIN"}
        assert gradient["midpoint"] == {"color": WHITE, "type": "NUMBER", "value": "0"}
        assert gradient["maxpoint"] == {"color": DEEP_BLUE, "type": "MAX"}

    def test_own_column_rule_is_replaced_not_duplicated(self) -> None:
        worksheet = _worksheet()
        worksheet.spreadsheet.fetch_sheet_metadata.return_value = {
            "sheets": [{"properties": {"sheetId": 0}, "conditionalFormats": [
                {"gradientRule": {}, "ranges": [
                    {"startColumnIndex": 4, "endColumnIndex": 5,
                     "startRowIndex": 4, "endRowIndex": 400},
                ]},
                {"booleanRule": {}, "ranges": [{"startColumnIndex": 4, "endColumnIndex": 5}]},
            ]}]
        }

        GradientRules(worksheet).apply()

        requests = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]
        deletes = [r["deleteConditionalFormatRule"]["index"] for r in requests
                   if "deleteConditionalFormatRule" in r]
        assert deletes == [0]


class TestNegativeOperatingProfit:
    def test_below_zero_gets_the_strongest_format(self) -> None:
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        rules = _rules(worksheet)
        critical = [r for r in rules if "booleanRule" in r]
        assert len(critical) == 1
        condition = critical[0]["booleanRule"]["condition"]
        # 0 は含めない。売れなかった日の 0 が大半で、赤くしても打つ手が無い
        assert condition["type"] == "NUMBER_LESS"
        assert condition["values"][0]["userEnteredValue"] == "0"
        assert critical[0]["booleanRule"]["format"]["textFormat"]["bold"] is True

    def test_it_is_placed_above_the_gradient_so_it_wins(self) -> None:
        # 条件付き書式は上にある規則が勝つ
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        rules = _rules(worksheet)
        critical = next(i for i, r in enumerate(rules) if "booleanRule" in r)
        gradient = next(
            i for i, r in enumerate(rules)
            if r.get("gradientRule", {}).get("minpoint", {}).get("value") == "0"
        )
        assert critical < gradient

    def test_it_covers_the_same_rows_as_the_gradient(self) -> None:
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        rules = _rules(worksheet)
        critical = next(r for r in rules if "booleanRule" in r)
        assert [r["startRowIndex"] for r in critical["ranges"]] == [5, 11]


class TestCountMedian:
    def test_the_recent_median_is_pinned_to_white(self) -> None:
        # MIN〜MAX の2点だと「その商品にとって普通の日」が色から読めない。
        # ふだんより売れた日が青、売れなかった日が赤になるようにする
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        gradient = _count_rule_at(worksheet, 5)["gradientRule"]
        assert gradient["midpoint"] == {"color": WHITE, "type": "NUMBER", "value": "7"}

    def test_the_ad_row_uses_its_own_median(self) -> None:
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        gradient = _count_rule_at(worksheet, 7)["gradientRule"]
        assert gradient["midpoint"] == {"color": WHITE, "type": "NUMBER", "value": "3"}

    def test_a_half_median_keeps_its_decimal(self) -> None:
        worksheet = _worksheet(values={5: [10, 3]})
        GradientRules(worksheet).apply()

        gradient = _count_rule_at(worksheet, 5)["gradientRule"]
        assert gradient["midpoint"]["value"] == "6.5"

    def test_a_zero_median_pins_white_to_zero_instead(self) -> None:
        # 中央値が0だと minpoint とぶつかって赤が出ない。売れなかった日を白、
        # 売れた日だけを青にする
        worksheet = _worksheet(values={5: [0, 0]})
        GradientRules(worksheet).apply()

        gradient = _count_rule_at(worksheet, 5)["gradientRule"]
        assert gradient["minpoint"] == {"color": WHITE, "type": "NUMBER", "value": "0"}
        assert gradient["maxpoint"] == {"color": PALE_BLUE, "type": "MAX"}
        assert "midpoint" not in gradient

    def test_days_older_than_the_window_are_ignored(self) -> None:
        # 3列目は46269から30日以上前。含めると中央値が実態から外れる
        worksheet = _worksheet(
            date_header=(46269, 46268, 46200),
            values={5: [10, 4, 900]},
            keys=["ASIN_SELL"],
        )
        GradientRules(worksheet).apply()

        gradient = _count_rule_at(worksheet, 5)["gradientRule"]
        assert gradient["midpoint"]["value"] == "7"

    def test_blank_days_are_excluded_but_zero_days_count(self) -> None:
        # 空セルは「まだ取っていない日」。0 は「売れなかった日」で、母数から
        # 外すと中央値が実態より高く出る
        worksheet = _worksheet(date_header=(46269, 46268, 46267), values={5: [8, 0, ""]},
                               keys=["ASIN_SELL"])
        GradientRules(worksheet).apply()

        gradient = _count_rule_at(worksheet, 5)["gradientRule"]
        assert gradient["midpoint"]["value"] == "4"

    def test_a_row_without_any_value_falls_back_to_zero(self) -> None:
        worksheet = _worksheet(values={})
        GradientRules(worksheet).apply()

        gradient = _count_rule_at(worksheet, 5)["gradientRule"]
        assert gradient["minpoint"] == {"color": WHITE, "type": "NUMBER", "value": "0"}


def _rank_rules(worksheet: Mock) -> list[dict]:
    return [
        r for r in _rules(worksheet)
        if "gradientRule" in r
        and r["gradientRule"]["minpoint"].get("color") == PALE_BLUE
    ]


class TestRankGradient:
    def test_rank_is_blue_at_the_top_and_red_at_the_bottom(self) -> None:
        # 順位は小さいほど良い。個数（多いほど良い）と向きが逆になる
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        gradient = _rank_rules(worksheet)[0]["gradientRule"]
        assert gradient["minpoint"] == {"color": PALE_BLUE, "type": "MIN"}
        assert gradient["maxpoint"] == {"color": PALE_RED, "type": "MAX"}

    def test_rank_rule_is_separate_per_product(self) -> None:
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        rank_rules = _rank_rules(worksheet)
        assert [r["ranges"][0]["startRowIndex"] for r in rank_rules] == [9, 15]
        assert all(len(r["ranges"]) == 1 for r in rank_rules)
