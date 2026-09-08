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


def _worksheet(existing_rules: int = 0) -> Mock:
    worksheet = Mock(spec=Worksheet)
    worksheet.id = 0
    worksheet.row_count = 400
    worksheet.row_values.side_effect = lambda row, **kwargs: (
        ["ASIN_SELL", "", "", "", "PROFIT_RATE"] if row == 1
        else ["ASIN", "商品名", 46269, 46268]
    )
    col_a = ["", "", "", "ASIN", "B00EXAMPLE", "", "", "", "", "B00EXAMPLF", "", "", "", ""]
    labels = list(ROW_LABELS_IN_ORDER)
    col_name = ["", "", "", "商品名", "ルーペ"] + labels + ["ボール"] + labels
    worksheet.col_values.side_effect = lambda col, **kwargs: col_a if col == 1 else col_name
    worksheet.spreadsheet.fetch_sheet_metadata.return_value = {
        "sheets": [{"properties": {"sheetId": 0},
                    "conditionalFormats": [{} for _ in range(existing_rules)]}]
    }
    return worksheet


def _operating_rules(worksheet: Mock) -> list[dict]:
    return [r for r in _rules(worksheet)
            if "gradientRule" in r and r["ranges"][0].get("endRowIndex") != 400
            and r["gradientRule"]["minpoint"].get("type") == "NUMBER"]


def _operating_gradient(worksheet: Mock) -> dict:
    return _operating_rules(worksheet)[0]["gradientRule"]


def _count_rules(worksheet: Mock) -> list[dict]:
    return [r for r in _rules(worksheet)
            if "gradientRule" in r and r["gradientRule"]["minpoint"].get("type") == "MIN"
            and r["ranges"][0].get("endRowIndex") != 400]


def _rules(worksheet: Mock) -> list[dict]:
    requests = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]
    return [r["addConditionalFormatRule"]["rule"] for r in requests
            if "addConditionalFormatRule" in r]


class TestGradientRules:
    def test_one_rule_per_product_for_the_count_rows(self) -> None:
        # 個数は商品ごとに桁が違う。1つのスケールに載せると、販売数の多い商品
        # 以外がすべて同じ色になる
        worksheet = _worksheet()

        # 商品2件 × (個数1本 + 営業利益1本) + 赤字の判定1本 + 利益率の列1本
        assert GradientRules(worksheet).apply() == 6
        count_rules = _count_rules(worksheet)
        assert len(count_rules) == 2
        assert all(len(r["ranges"]) == 2 for r in count_rules)

    def test_count_rule_covers_the_asin_row_and_the_ad_row_together(self) -> None:
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        ranges = _count_rules(worksheet)[0]["ranges"]
        # ASIN行（0起点で4）と広告経由行。並べ替え後は隣り合っていない
        assert [r["startRowIndex"] for r in ranges] == [4, 6]
        assert ranges[0]["startColumnIndex"] == 2
        assert ranges[0]["endColumnIndex"] == 4

    def test_counts_go_red_to_blue_in_a_pale_tone(self) -> None:
        # 悪い = 赤、良い = 青で全行そろえ、行の種類は色味の濃さで見分ける
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        gradient = _count_rules(worksheet)[0]["gradientRule"]
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
        assert [r["ranges"][0]["startRowIndex"] for r in operating] == [5, 10]
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
        assert [r["startRowIndex"] for r in critical["ranges"]] == [5, 10]
