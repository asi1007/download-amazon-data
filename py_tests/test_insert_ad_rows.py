from unittest.mock import Mock

from insert_ad_rows import (
    _apply_label_row_plan,
    build_background_requests,
    build_insert_requests,
    build_label_requests,
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

    def test_multiple_asins_all_with_zero_labels(self) -> None:
        # 複数ASINがそれぞれラベル0本のケース（従来は1ASIN×0本しかテストが無かった）
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", "", "B00EXAMPLF", ""]
        name_values = ["", "", "", "商品名", "ルーペ", "", "ボール", ""]

        assert plan_label_row_insertions(asin_values, name_values) == [(7, 3), (5, 3)]


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


class TestBuildLabelRequests:
    def test_converts_one_indexed_rows_to_zero_indexed_grid_range(self) -> None:
        # label_row_numbers は1起点、GridRange は0起点。行6・列5(E列)なら
        # startRowIndex=5/endRowIndex=6、startColumnIndex=4/endColumnIndex=5になる
        requests = build_label_requests(
            sheet_id=551300985, name_column=5, labeled_rows=[(6, AD_ROW_LABEL)]
        )

        assert requests == [
            {
                "updateCells": {
                    "range": {
                        "sheetId": 551300985,
                        "startRowIndex": 5,
                        "endRowIndex": 6,
                        "startColumnIndex": 4,
                        "endColumnIndex": 5,
                    },
                    "rows": [
                        {"values": [{"userEnteredValue": {"stringValue": AD_ROW_LABEL}}]}
                    ],
                    "fields": "userEnteredValue",
                }
            }
        ]

    def test_preserves_label_order_across_multiple_rows(self) -> None:
        labeled_rows = [
            (6, AD_ROW_LABEL),
            (7, GROSS_PROFIT_ROW_LABEL),
            (8, AD_COST_ROW_LABEL),
        ]

        requests = build_label_requests(sheet_id=1, name_column=5, labeled_rows=labeled_rows)

        written_labels = [
            r["updateCells"]["rows"][0]["values"][0]["userEnteredValue"]["stringValue"]
            for r in requests
        ]
        assert written_labels == [AD_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL]


class TestBuildBackgroundRequests:
    def test_spans_from_column_a_through_the_name_column(self) -> None:
        requests = build_background_requests(
            sheet_id=1, name_column=5, labeled_rows=[(6, AD_ROW_LABEL)]
        )

        assert requests[0]["repeatCell"]["range"] == {
            "sheetId": 1,
            "startRowIndex": 5,
            "endRowIndex": 6,
            "startColumnIndex": 0,
            "endColumnIndex": 5,
        }
        assert requests[0]["repeatCell"]["fields"] == "userEnteredFormat.backgroundColor"


class TestApplyLabelRowPlan:
    def _worksheet_with(self, asin_values: list[str], name_values: list[str]) -> Mock:
        worksheet = Mock()
        worksheet.id = 551300985
        worksheet.col_values.side_effect = [asin_values, name_values]
        return worksheet

    def test_no_plan_makes_no_api_calls(self) -> None:
        worksheet = self._worksheet_with(
            asin_values=["", "", "", "ASIN", "B00EXAMPLE", "", "", ""],
            name_values=[
                "", "", "", "商品名", "ルーペ",
                AD_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL,
            ],
        )

        result = _apply_label_row_plan(worksheet, name_column=5)

        assert result == []
        worksheet.spreadsheet.batch_update.assert_not_called()

    def test_insertion_and_labeling_are_sent_as_a_single_batch_update_call(self) -> None:
        worksheet = self._worksheet_with(
            asin_values=["", "", "", "ASIN", "B00EXAMPLE"],
            name_values=["", "", "", "商品名", "ルーペ"],
        )

        _apply_label_row_plan(worksheet, name_column=5)

        assert worksheet.spreadsheet.batch_update.call_count == 1
        assert worksheet.batch_update.call_count == 0
        assert worksheet.batch_format.call_count == 0

    def test_insert_dimension_precedes_update_cells_in_the_single_request(self) -> None:
        worksheet = self._worksheet_with(
            asin_values=["", "", "", "ASIN", "B00EXAMPLE"],
            name_values=["", "", "", "商品名", "ルーペ"],
        )

        _apply_label_row_plan(worksheet, name_column=5)

        requests = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]
        request_kinds = [next(iter(r)) for r in requests]
        assert request_kinds.index("insertDimension") < request_kinds.index("updateCells")

    def test_labels_are_written_at_the_rows_and_order_label_row_numbers_produces(self) -> None:
        worksheet = self._worksheet_with(
            asin_values=["", "", "", "ASIN", "B00EXAMPLE"],
            name_values=["", "", "", "商品名", "ルーペ"],
        )

        result = _apply_label_row_plan(worksheet, name_column=5)

        assert result == [
            (6, AD_ROW_LABEL),
            (7, GROSS_PROFIT_ROW_LABEL),
            (8, AD_COST_ROW_LABEL),
        ]
        requests = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]
        update_cells_requests = [r["updateCells"] for r in requests if "updateCells" in r]
        written = [
            (r["range"]["startRowIndex"] + 1, r["rows"][0]["values"][0]["userEnteredValue"]["stringValue"])
            for r in update_cells_requests
        ]
        assert written == [
            (6, AD_ROW_LABEL),
            (7, GROSS_PROFIT_ROW_LABEL),
            (8, AD_COST_ROW_LABEL),
        ]
