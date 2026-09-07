from unittest.mock import Mock

from gspread import Worksheet

from py_src.infrastructure.sheets.inventory_alerts import (
    CRITICAL_FORMAT,
    WARNING_FORMAT,
    WHITE,
    InventoryAlerts,
)

HEADER = [
    "ASIN", "商品名", "FBA\n在庫日数", "昨日売上2週分", "3日間平均2周分",
    "週平均2周分", "在庫日数", "目標売上\n在庫日数", "その他",
]


def _worksheet(existing: list[dict] | None = None) -> Mock:
    worksheet = Mock(spec=Worksheet)
    worksheet.id = 0
    worksheet.row_count = 400
    worksheet.row_values.return_value = HEADER
    worksheet.spreadsheet.fetch_sheet_metadata.return_value = {
        "sheets": [{"properties": {"sheetId": 0}, "conditionalFormats": existing or []}]
    }
    return worksheet


def _requests(worksheet: Mock) -> list[dict]:
    return worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]


def _rules(worksheet: Mock) -> list[dict]:
    return [r["addConditionalFormatRule"]["rule"] for r in _requests(worksheet)
            if "addConditionalFormatRule" in r]


class TestInventoryAlerts:
    def test_fba_stock_days_is_the_only_critical_one(self) -> None:
        # 在庫切れが近いほど手を打つ余地が無い
        worksheet = _worksheet()

        assert InventoryAlerts(worksheet).apply() == 3
        formats = [r["booleanRule"]["format"] for r in _rules(worksheet)]
        assert formats.count(CRITICAL_FORMAT) == 1
        assert formats.count(WARNING_FORMAT) == 2

    def test_thresholds_match_each_column(self) -> None:
        worksheet = _worksheet()
        InventoryAlerts(worksheet).apply()

        by_column = {
            r["ranges"][0]["startColumnIndex"] + 1:
                r["booleanRule"]["condition"]["values"][0]["userEnteredValue"]
            for r in _rules(worksheet)
        }
        assert by_column == {3: "14", 7: "72", 8: "72"}

    def test_header_with_a_newline_is_matched(self) -> None:
        # 実シートのヘッダーは 'FBA\n在庫日数'
        worksheet = _worksheet()
        InventoryAlerts(worksheet).apply()

        assert any(r["ranges"][0]["startColumnIndex"] == 2 for r in _rules(worksheet))

    def test_rules_only_cover_rows_below_the_header(self) -> None:
        worksheet = _worksheet()
        InventoryAlerts(worksheet).apply()

        assert all(r["ranges"][0]["startRowIndex"] == 4 for r in _rules(worksheet))

    def test_surrounding_cells_are_reset_to_white(self) -> None:
        # 条件付き書式を消したときに下地のピンクが露出した
        worksheet = _worksheet()
        InventoryAlerts(worksheet).apply()

        resets = [r["repeatCell"] for r in _requests(worksheet) if "repeatCell" in r]
        assert len(resets) == 6
        assert all(
            r["cell"]["userEnteredFormat"]["backgroundColor"] == WHITE for r in resets
        )
        assert {r["range"]["startColumnIndex"] for r in resets} == {2, 3, 4, 5, 6, 7}

    def test_only_own_rules_are_deleted(self) -> None:
        worksheet = _worksheet(existing=[
            {"booleanRule": {"condition": {"type": "CUSTOM_FORMULA"}},
             "ranges": [{"startColumnIndex": 2, "endColumnIndex": 3}]},
            {"booleanRule": {"condition": {"type": "NUMBER_LESS_THAN_EQ"}},
             "ranges": [{"startColumnIndex": 2, "endColumnIndex": 3}]},
            {"booleanRule": {"condition": {"type": "NUMBER_LESS_THAN_EQ"}},
             "ranges": [{"startColumnIndex": 40, "endColumnIndex": 41}]},
        ])
        InventoryAlerts(worksheet).apply()

        deletes = [r["deleteConditionalFormatRule"]["index"] for r in _requests(worksheet)
                   if "deleteConditionalFormatRule" in r]
        assert deletes == [1]
