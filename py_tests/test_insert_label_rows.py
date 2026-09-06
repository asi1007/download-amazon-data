from insert_label_rows import (
    build_insert_requests,
    label_row_numbers,
    plan_label_insertions,
)
from py_src.infrastructure.sheets.label_rows import ROW_LABELS_IN_ORDER

HEADER_ROWS = ["", "", "", "ASIN"]


def _sheet(rows: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    asin = HEADER_ROWS + [a for a, _ in rows]
    name = ["", "", "", "商品名"] + [n for _, n in rows]
    return asin, name


class TestPlanLabelInsertions:
    def test_product_with_no_label_rows_gets_all_of_them(self) -> None:
        asin, name = _sheet([("B00EXAMPLE", "ルーペ")])

        assert plan_label_insertions(asin, name) == [(6, list(ROW_LABELS_IN_ORDER))]

    def test_nothing_to_do_when_every_label_is_present(self) -> None:
        asin, name = _sheet(
            [("B00EXAMPLE", "ルーペ")] + [("", label) for label in ROW_LABELS_IN_ORDER]
        )

        assert plan_label_insertions(asin, name) == []

    def test_label_missing_in_the_middle_is_inserted_in_place(self) -> None:
        # 既存シートは 広告経由 / 粗利益 / 広告費 の3行。営業利益は広告経由の
        # 直後（粗利益の上）へ入れる。「不足分は末尾」だと既存行が孤児になる
        asin, name = _sheet([
            ("B00EXAMPLE", "ルーペ"),
            ("", "広告経由"),
            ("", "粗利益"),
            ("", "広告費"),
        ])

        assert plan_label_insertions(asin, name) == [(7, ["営業利益"])]

    def test_two_products_are_planned_from_the_bottom_up(self) -> None:
        asin, name = _sheet([
            ("B00EXAMPLE", "ルーペ"),
            ("", "広告経由"),
            ("", "粗利益"),
            ("", "広告費"),
            ("B00EXAMPLF", "ボール"),
            ("", "広告経由"),
            ("", "粗利益"),
            ("", "広告費"),
        ])

        assert plan_label_insertions(asin, name) == [(11, ["営業利益"]), (7, ["営業利益"])]


class TestRowArithmetic:
    def test_inserts_are_sent_bottom_up_so_earlier_rows_keep_their_numbers(self) -> None:
        plan = [(11, ["営業利益"]), (7, ["営業利益"])]

        ranges = [r["insertDimension"]["range"] for r in build_insert_requests(0, plan)]

        assert [(r["startIndex"], r["endIndex"]) for r in ranges] == [(10, 11), (6, 7)]

    def test_label_rows_account_for_inserts_made_above_them(self) -> None:
        plan = [(11, ["営業利益"]), (7, ["営業利益"])]

        assert label_row_numbers(plan) == [(7, "営業利益"), (12, "営業利益")]

    def test_several_labels_at_one_position_keep_their_order(self) -> None:
        plan = [(6, ["広告経由", "営業利益", "粗利益", "広告費"])]

        assert label_row_numbers(plan) == [
            (6, "広告経由"), (7, "営業利益"), (8, "粗利益"), (9, "広告費"),
        ]
