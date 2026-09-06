from unittest.mock import Mock

from gspread import Worksheet

from py_src.infrastructure.sheets.label_rows import ROW_LABELS_IN_ORDER
from py_src.infrastructure.sheets.row_heights import (
    ASIN_ROW_HEIGHT,
    LABEL_ROW_HEIGHT,
    RowHeights,
    plan_row_heights,
)


class TestPlanRowHeights:
    def test_asin_row_keeps_full_height_and_labels_take_half(self) -> None:
        assert plan_row_heights({"B00EXAMPLE": [8]}) == [
            (7, 7, ASIN_ROW_HEIGHT),
            (8, 11, LABEL_ROW_HEIGHT),
        ]

    def test_block_is_anchored_on_the_first_label_not_on_a_fixed_label(self) -> None:
        # 「広告経由の1つ上が ASIN 行」と決め打つと、並べ替えたときに次の商品の
        # ASIN 行まで縮めてしまう
        plan = plan_row_heights({"A": [8], "B": [13]})

        assert [(first, last) for first, last, _ in plan] == [(7, 7), (8, 11), (12, 12), (13, 16)]

    def test_label_height_is_half_of_the_asin_row(self) -> None:
        assert LABEL_ROW_HEIGHT * 2 in (ASIN_ROW_HEIGHT, ASIN_ROW_HEIGHT - 1)

    def test_reserved_rows_are_skipped(self) -> None:
        assert plan_row_heights({"A": [4]}) == []


def _worksheet() -> Mock:
    worksheet = Mock(spec=Worksheet)
    worksheet.id = 0
    worksheet.row_values.return_value = ["ASIN", "商品名"]
    col_a = ["", "", "", "ASIN", "B00EXAMPLE", "", "", "", ""]
    col_name = ["", "", "", "商品名", "ルーペ"] + list(ROW_LABELS_IN_ORDER)
    worksheet.col_values.side_effect = lambda col, **kwargs: col_a if col == 1 else col_name
    return worksheet


class TestRowHeights:
    def test_sets_both_the_asin_row_and_the_label_rows(self) -> None:
        worksheet = _worksheet()

        assert RowHeights(worksheet).shrink_label_rows() == 5
        requests = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]
        sizes = [r["updateDimensionProperties"]["properties"]["pixelSize"] for r in requests]
        assert sizes == [ASIN_ROW_HEIGHT, LABEL_ROW_HEIGHT]

    def test_asin_row_is_restored_to_full_height(self) -> None:
        # 一度潰してしまった行を戻せるよう、ASIN行にも明示的に高さを書く
        worksheet = _worksheet()
        RowHeights(worksheet).shrink_label_rows()

        first = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"][0]
        assert first["updateDimensionProperties"]["range"]["startIndex"] == 4
        assert first["updateDimensionProperties"]["range"]["endIndex"] == 5
