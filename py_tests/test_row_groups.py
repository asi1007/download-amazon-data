from unittest.mock import Mock

from gspread import Worksheet

from py_src.infrastructure.sheets.label_rows import (
    AD_COST_ROW_LABEL,
    AD_ROW_LABEL,
    GROSS_PROFIT_ROW_LABEL,
    OPERATING_PROFIT_ROW_LABEL,
)
from py_src.infrastructure.sheets.row_groups import RowGroups, plan_groups


class TestPlanGroups:
    def test_group_starts_below_the_operating_profit_row(self) -> None:
        # ASIN行と営業利益はたたんでも見えたままにする
        assert plan_groups({"B00EXAMPLE": [8]}) == [(9, 11)]

    def test_one_group_per_product(self) -> None:
        assert plan_groups({"A": [8], "B": [13]}) == [(9, 11), (14, 16)]

    def test_reserved_rows_are_skipped(self) -> None:
        assert plan_groups({"A": [3]}) == []


def _worksheet(existing_groups: list[dict] | None = None) -> Mock:
    worksheet = Mock(spec=Worksheet)
    worksheet.id = 0
    worksheet.row_values.return_value = ["ASIN", "商品名"]
    col_a = ["", "", "", "ASIN", "B00EXAMPLE", "", "", "", ""]
    col_name = [
        "", "", "", "商品名", "ルーペ",
        OPERATING_PROFIT_ROW_LABEL, AD_ROW_LABEL,
        GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL,
    ]
    worksheet.col_values.side_effect = lambda col, **kwargs: col_a if col == 1 else col_name
    worksheet.spreadsheet.fetch_sheet_metadata.return_value = {
        "sheets": [{"properties": {"sheetId": 0}, "rowGroups": existing_groups or []}]
    }
    return worksheet


def _requests(worksheet: Mock) -> list[dict]:
    return worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]


class TestRowGroups:
    def test_creates_a_collapsed_group_under_the_operating_profit_row(self) -> None:
        worksheet = _worksheet()

        assert RowGroups(worksheet).collapse_label_rows() == 1
        added = [r for r in _requests(worksheet) if "addDimensionGroup" in r]
        assert added[0]["addDimensionGroup"]["range"]["startIndex"] == 6
        assert added[0]["addDimensionGroup"]["range"]["endIndex"] == 9

    def test_group_is_collapsed(self) -> None:
        worksheet = _worksheet()
        RowGroups(worksheet).collapse_label_rows()

        updated = [r for r in _requests(worksheet) if "updateDimensionGroup" in r]
        assert updated[0]["updateDimensionGroup"]["dimensionGroup"]["collapsed"] is True

    def test_existing_groups_are_removed_first_so_they_do_not_nest(self) -> None:
        worksheet = _worksheet(existing_groups=[
            {"range": {"sheetId": 0, "dimension": "ROWS", "startIndex": 6, "endIndex": 9},
             "depth": 1},
        ])
        RowGroups(worksheet).collapse_label_rows()

        requests = _requests(worksheet)
        deletes = [i for i, r in enumerate(requests) if "deleteDimensionGroup" in r]
        adds = [i for i, r in enumerate(requests) if "addDimensionGroup" in r]
        assert deletes and adds and max(deletes) < min(adds)
