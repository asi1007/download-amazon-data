from unittest.mock import Mock

from gspread import Worksheet

from py_src.infrastructure.sheets.label_rows import (
    AD_COST_ROW_LABEL,
    AD_ROW_LABEL,
    GROSS_PROFIT_ROW_LABEL,
    OPERATING_PROFIT_ROW_LABEL,
)
from py_src.infrastructure.sheets.row_heights import (
    MINIMUM_LABEL_ROW_HEIGHT,
    RowHeights,
    plan_label_row_heights,
)


class TestPlanLabelRowHeights:
    def test_label_rows_take_half_of_their_own_asin_row(self) -> None:
        assert plan_label_row_heights({"B00EXAMPLE": [6]}, {5: 39}) == [(6, 9, 19)]

    def test_each_product_uses_its_own_asin_height(self) -> None:
        plan = plan_label_row_heights({"A": [6], "B": [11]}, {5: 38, 10: 60})

        assert plan == [(6, 9, 19), (11, 14, 30)]

    def test_never_goes_below_a_readable_minimum(self) -> None:
        assert plan_label_row_heights({"A": [6]}, {5: 4})[0][2] == MINIMUM_LABEL_ROW_HEIGHT

    def test_asin_row_on_a_reserved_row_is_skipped(self) -> None:
        assert plan_label_row_heights({"A": [5]}, {4: 39}) == []


def _worksheet() -> Mock:
    worksheet = Mock(spec=Worksheet)
    worksheet.id = 0
    worksheet.title = "売上/日"
    worksheet.row_values.return_value = ["ASIN", "商品名"]
    col_a = ["", "", "", "ASIN", "B00EXAMPLE", "", "", "", ""]
    col_name = [
        "", "", "", "商品名", "ルーペ",
        AD_ROW_LABEL, OPERATING_PROFIT_ROW_LABEL,
        GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL,
    ]
    worksheet.col_values.side_effect = lambda col, **kwargs: col_a if col == 1 else col_name
    worksheet.spreadsheet.fetch_sheet_metadata.return_value = {
        "sheets": [{"properties": {"sheetId": 0},
                    "data": [{"rowMetadata": [{"pixelSize": 39} for _ in range(9)]}]}]
    }
    return worksheet


class TestRowHeights:
    def test_shrinks_the_four_label_rows_in_one_request_per_product(self) -> None:
        worksheet = _worksheet()

        assert RowHeights(worksheet).shrink_label_rows() == 4
        requests = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]
        assert len(requests) == 1
        target = requests[0]["updateDimensionProperties"]
        assert target["range"]["startIndex"] == 5
        assert target["range"]["endIndex"] == 9
        assert target["properties"]["pixelSize"] == 19

    def test_asin_row_itself_is_left_alone(self) -> None:
        worksheet = _worksheet()
        RowHeights(worksheet).shrink_label_rows()

        target = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"][0]
        assert target["updateDimensionProperties"]["range"]["startIndex"] >= 5
