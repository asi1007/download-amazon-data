from insert_ad_rows import (
    build_insert_requests,
    existing_label_run,
    label_row_numbers,
    plan_label_row_insertions,
)
from py_src.infrastructure.sheets.label_rows import (
    AD_COST_ROW_LABEL,
    AD_ROW_LABEL,
    GROSS_PROFIT_ROW_LABEL,
)


class TestExistingLabelRun:
    def test_counts_labels_present_in_order(self) -> None:
        names = ["", "", "", "商品名", "ルーペ", AD_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, ""]

        assert existing_label_run(4, names) == 2

    def test_zero_when_next_row_is_not_the_first_label(self) -> None:
        names = ["", "", "", "商品名", "ルーペ", "メモ"]

        assert existing_label_run(4, names) == 0

    def test_stops_at_the_first_mismatch(self) -> None:
        # 順番が違えば、そこで打ち切る
        names = ["", "", "", "商品名", "ルーペ", AD_ROW_LABEL, AD_COST_ROW_LABEL]

        assert existing_label_run(4, names) == 1

    def test_all_three_present(self) -> None:
        names = [
            "", "", "", "商品名", "ルーペ",
            AD_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL,
        ]

        assert existing_label_run(4, names) == 3


class TestPlanLabelRowInsertions:
    def test_adds_the_missing_two_for_the_current_sheet(self) -> None:
        # いまの状態: 各 ASIN の下に 広告経由 が1本だけ
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", "", "B00EXAMPLF", ""]
        name_values = ["", "", "", "商品名", "ルーペ", AD_ROW_LABEL, "ボール", AD_ROW_LABEL]

        assert plan_label_row_insertions(asin_values, name_values) == [(8, 2), (6, 2)]

    def test_adds_all_three_when_none_present(self) -> None:
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE"]
        name_values = ["", "", "", "商品名", "ルーペ"]

        assert plan_label_row_insertions(asin_values, name_values) == [(5, 3)]

    def test_nothing_to_do_when_all_present(self) -> None:
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", "", "", ""]
        name_values = [
            "", "", "", "商品名", "ルーペ",
            AD_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL,
        ]

        assert plan_label_row_insertions(asin_values, name_values) == []

    def test_ignores_heading_rows(self) -> None:
        asin_values = ["", "", "", "ASIN", "様子見", "やめる"]
        name_values = ["", "", "", "商品名", "", ""]

        assert plan_label_row_insertions(asin_values, name_values) == []

    def test_does_not_overwrite_unrelated_content_below_an_asin(self) -> None:
        # 直下に別の文字がある場合、ラベルは0本とみなして上に挿入する（上書きしない）
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", ""]
        name_values = ["", "", "", "商品名", "ルーペ", "メモ"]

        assert plan_label_row_insertions(asin_values, name_values) == [(5, 3)]


class TestBuildInsertRequests:
    def test_inserts_the_missing_count_below_the_run(self) -> None:
        requests = build_insert_requests(sheet_id=551300985, plan=[(8, 2), (6, 2)])

        ranges = [r["insertDimension"]["range"] for r in requests]
        assert ranges[0] == {
            "sheetId": 551300985, "dimension": "ROWS", "startIndex": 8, "endIndex": 10,
        }
        assert ranges[1] == {
            "sheetId": 551300985, "dimension": "ROWS", "startIndex": 6, "endIndex": 8,
        }

    def test_does_not_inherit_formatting(self) -> None:
        requests = build_insert_requests(sheet_id=1, plan=[(5, 3)])

        assert requests[0]["insertDimension"]["inheritFromBefore"] is False


class TestLabelRowNumbers:
    def test_returns_row_and_label_pairs_after_the_shift(self) -> None:
        # 行6の下に2本、行8の下に2本入れると、
        # 1件目は行7=粗利益/行8=広告費、2件目は行11=粗利益/行12=広告費
        assert label_row_numbers([(8, 2), (6, 2)]) == [
            (7, GROSS_PROFIT_ROW_LABEL),
            (8, AD_COST_ROW_LABEL),
            (11, GROSS_PROFIT_ROW_LABEL),
            (12, AD_COST_ROW_LABEL),
        ]

    def test_all_three_labels_when_nothing_existed(self) -> None:
        assert label_row_numbers([(5, 3)]) == [
            (6, AD_ROW_LABEL),
            (7, GROSS_PROFIT_ROW_LABEL),
            (8, AD_COST_ROW_LABEL),
        ]
