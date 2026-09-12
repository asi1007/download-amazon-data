from insert_label_rows import (
    BLACK,
    build_format_requests,
    build_insert_requests,
    find_label_rows,
    label_row_numbers,
    plan_label_insertions,
)
from sales_data.infrastructure.sheets.layout import ROW_LABELS_IN_ORDER

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
        # 営業利益より上に別のラベルがある形。「不足分は末尾」だと既存行が孤児になる
        asin, name = _sheet([
            ("B00EXAMPLE", "ルーペ"),
            ("", "広告経由"),
            ("", "粗利益"),
            ("", "広告費"),
            ("", "順位"),
        ])

        assert plan_label_insertions(asin, name) == [(6, ["営業利益"])]

    def test_two_products_are_planned_from_the_bottom_up(self) -> None:
        asin, name = _sheet([
            ("B00EXAMPLE", "ルーペ"),
            ("", "広告経由"),
            ("", "粗利益"),
            ("", "広告費"),
            ("", "順位"),
            ("B00EXAMPLF", "ボール"),
            ("", "広告経由"),
            ("", "粗利益"),
            ("", "広告費"),
            ("", "順位"),
        ])

        assert plan_label_insertions(asin, name) == [(11, ["営業利益"]), (6, ["営業利益"])]


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


class TestRankRowIsNotDuplicated:
    def test_existing_rank_row_with_category_is_not_inserted_again(self) -> None:
        # 完全一致で突き合わせると、カテゴリ名付きの順位行を「無い」と判定して
        # 実行のたびに1本ずつ増える
        asin, name = _sheet([
            ("B00EXAMPLE", "ルーペ"),
            ("", "営業利益"),
            ("", "広告経由"),
            ("", "粗利益"),
            ("", "広告費"),
            ("", "順位（ジュエリー収納）"),
        ])

        assert plan_label_insertions(asin, name) == []

    def test_missing_rank_row_is_appended_after_the_ad_cost_row(self) -> None:
        asin, name = _sheet([
            ("B00EXAMPLE", "ルーペ"),
            ("", "営業利益"),
            ("", "広告経由"),
            ("", "粗利益"),
            ("", "広告費"),
        ])

        assert plan_label_insertions(asin, name) == [(10, ["順位"])]


class TestLabelRowFormat:
    def test_label_rows_get_black_text_over_the_grey_background(self) -> None:
        # 挿入した行は直前の商品行から文字色を受け継ぐ。黄色を付けた商品ブロックでは
        # うすい灰色の背景に黄色の文字が乗って読めなくなる
        requests = build_format_requests(551300985, 7, [(10, "順位")])

        cell = requests[0]["repeatCell"]["cell"]["userEnteredFormat"]
        assert cell["textFormat"]["foregroundColor"] == BLACK
        assert cell["textFormat"]["foregroundColorStyle"] == {"rgbColor": BLACK}
        assert cell["backgroundColor"] == {"red": 0.95, "green": 0.95, "blue": 0.95}

    def test_format_fields_cover_both_the_background_and_the_text_colour(self) -> None:
        # foregroundColorStyle を書かないと、既にスタイル側で黄色が指定されている
        # セルはそちらが勝って黄色のまま残る
        fields = build_format_requests(551300985, 7, [(10, "順位")])[0]["repeatCell"]["fields"]

        assert "userEnteredFormat.backgroundColor" in fields
        assert "userEnteredFormat.textFormat.foregroundColor" in fields
        assert "userEnteredFormat.textFormat.foregroundColorStyle" in fields


class TestFindLabelRows:
    def test_finds_every_label_row_including_the_rank_row_with_a_category(self) -> None:
        asin, name = _sheet([
            ("B00EXAMPLE", "ルーペ"),
            ("", "営業利益"),
            ("", "広告経由"),
            ("", "粗利益"),
            ("", "広告費"),
            ("", "順位（ジュエリー収納）"),
        ])

        assert find_label_rows(asin, name) == [
            (6, "営業利益"), (7, "広告経由"), (8, "粗利益"), (9, "広告費"),
            (10, "順位（ジュエリー収納）"),
        ]

    def test_product_rows_and_free_notes_are_not_label_rows(self) -> None:
        # A列に手書きのメモが入るだけの行がある。ラベル行と混ぜると塗ってしまう
        asin, name = _sheet([
            ("B00EXAMPLE", "ルーペ"),
            ("", "営業利益"),
            ("やめる", ""),
        ])

        assert find_label_rows(asin, name) == [(6, "営業利益")]
