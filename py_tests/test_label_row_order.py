from unittest.mock import Mock

from gspread import Worksheet

from py_src.infrastructure.sheets.label_row_order import (
    LabelRowOrder,
    build_move_requests,
    plan_block_moves,
)

CURRENT = ["広告経由", "営業利益", "粗利益", "広告費", "順位"]
EXPECTED = ["営業利益", "広告経由", "粗利益", "広告費", "順位"]


class TestPlanBlockMoves:
    def test_swaps_the_first_two_rows(self) -> None:
        # 営業利益を広告経由の上へ引き上げる
        assert plan_block_moves(8, CURRENT) == [(9, 8)]

    def test_nothing_to_do_when_already_in_order(self) -> None:
        assert plan_block_moves(8, EXPECTED) == []

    def test_reversed_block_is_sorted_in_place(self) -> None:
        moves = plan_block_moves(8, ["広告費", "粗利益", "広告経由", "営業利益"])

        # 1本引き上げるたびに残りが1つ下へずれるので、移動元は毎回末尾になる
        assert moves == [(11, 8), (11, 9), (11, 10)]

    def test_unknown_label_is_left_alone(self) -> None:
        assert plan_block_moves(8, ["営業利益", "広告経由", "メモ", "広告費"]) == []


class TestBuildMoveRequests:
    def test_uses_zero_based_indexes(self) -> None:
        request = build_move_requests(0, [(9, 8)])[0]["moveDimension"]

        assert request["source"]["startIndex"] == 8
        assert request["source"]["endIndex"] == 9
        assert request["destinationIndex"] == 7


def _worksheet(labels: list[str]) -> Mock:
    worksheet = Mock(spec=Worksheet)
    worksheet.id = 0
    worksheet.row_values.return_value = ["ASIN", "商品名"]
    col_a = ["", "", "", "ASIN", "B00EXAMPLE"] + [""] * 5
    col_name = ["", "", "", "商品名", "ルーペ"] + labels
    worksheet.col_values.side_effect = lambda col, **kwargs: col_a if col == 1 else col_name
    return worksheet


class TestLabelRowOrder:
    def test_moves_only_when_the_block_is_out_of_order(self) -> None:
        worksheet = _worksheet(CURRENT)

        assert LabelRowOrder(worksheet).reorder() == 1

    def test_does_nothing_when_already_in_order(self) -> None:
        worksheet = _worksheet(EXPECTED)

        assert LabelRowOrder(worksheet).reorder() == 0
        worksheet.spreadsheet.batch_update.assert_not_called()

    def test_block_with_a_missing_label_is_skipped(self) -> None:
        # 4本そろっていないブロックは insert_label_rows の担当。ここでは触らない
        worksheet = _worksheet(["広告経由", "粗利益", "広告費", ""])

        assert LabelRowOrder(worksheet).reorder() == 0
