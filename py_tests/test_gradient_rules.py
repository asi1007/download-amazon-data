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
from py_src.infrastructure.sheets.label_rows import (
    AD_COST_ROW_LABEL,
    AD_ROW_LABEL,
    GROSS_PROFIT_ROW_LABEL,
    OPERATING_PROFIT_ROW_LABEL,
)


def _worksheet(existing_rules: int = 0) -> Mock:
    worksheet = Mock(spec=Worksheet)
    worksheet.id = 0
    worksheet.row_values.return_value = ["ASIN", "商品名", 46269, 46268]
    col_a = ["", "", "", "ASIN", "B00EXAMPLE", "", "", "", "", "B00EXAMPLF", "", "", "", ""]
    labels = [AD_ROW_LABEL, OPERATING_PROFIT_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL]
    col_name = ["", "", "", "商品名", "ルーペ"] + labels + ["ボール"] + labels
    worksheet.col_values.side_effect = lambda col, **kwargs: col_a if col == 1 else col_name
    worksheet.spreadsheet.fetch_sheet_metadata.return_value = {
        "sheets": [{"properties": {"sheetId": 0},
                    "conditionalFormats": [{} for _ in range(existing_rules)]}]
    }
    return worksheet


def _rules(worksheet: Mock) -> list[dict]:
    requests = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]
    return [r["addConditionalFormatRule"]["rule"] for r in requests
            if "addConditionalFormatRule" in r]


class TestGradientRules:
    def test_one_rule_per_product_for_the_count_rows(self) -> None:
        # 個数は商品ごとに桁が違う。1つのスケールに載せると、販売数の多い商品
        # 以外がすべて同じ色になる
        worksheet = _worksheet()

        assert GradientRules(worksheet).apply() == 3
        count_rules = [r for r in _rules(worksheet)
                       if "midpoint" not in r["gradientRule"]]
        assert len(count_rules) == 2
        assert all(len(r["ranges"]) == 2 for r in count_rules)

    def test_count_rule_covers_the_asin_row_and_the_ad_row_together(self) -> None:
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        ranges = _rules(worksheet)[0]["ranges"]
        assert [r["startRowIndex"] for r in ranges] == [4, 5]
        assert ranges[0]["startColumnIndex"] == 2
        assert ranges[0]["endColumnIndex"] == 4

    def test_counts_go_red_to_blue_in_a_pale_tone(self) -> None:
        # 悪い = 赤、良い = 青で全行そろえ、行の種類は色味の濃さで見分ける
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        gradient = _rules(worksheet)[0]["gradientRule"]
        assert gradient["minpoint"] == {"color": PALE_RED, "type": "MIN"}
        assert gradient["maxpoint"] == {"color": PALE_BLUE, "type": "MAX"}

    def test_operating_profit_pins_zero_to_white_in_a_deep_tone(self) -> None:
        # MIN を白にすると「最も赤字の日」が白になり、黒字か赤字かが色から読めない
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        operating = [r for r in _rules(worksheet)
                     if r["gradientRule"].get("midpoint", {}).get("value") == "0"]
        gradient = operating[0]["gradientRule"]
        assert gradient["minpoint"] == {"color": DEEP_RED, "type": "MIN"}
        assert gradient["midpoint"] == {"color": WHITE, "type": "NUMBER", "value": "0"}
        assert gradient["maxpoint"] == {"color": DEEP_BLUE, "type": "MAX"}
        # 全商品を1つの規則にまとめる。金額そのものを商品間で比べられる
        assert len(operating) == 1
        assert [r["startRowIndex"] for r in operating[0]["ranges"]] == [6, 11]

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
        worksheet.row_values.return_value = ["ASIN", "商品名"]

        assert GradientRules(worksheet).apply() == 0
