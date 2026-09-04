from unittest.mock import Mock, patch

import pytest
import requests

from insert_ad_rows import (
    build_insert_requests,
    plan_ad_row_insertions,
    plan_ad_row_recovery,
    _apply_ad_row_plan,
    _relabel_row_numbers,
)

AD_LABEL = "広告経由"


class TestPlanAdRowInsertions:
    def test_plans_one_row_under_each_asin_in_descending_order(self) -> None:
        asin_values = ["", "", "", "ASIN", "新商品", "B00EXAMPLE", "B00EXAMPLF"]
        name_values = ["", "", "", "商品名", "", "ルーペ", "ボールネット"]

        assert plan_ad_row_insertions(asin_values, name_values) == [7, 6]

    def test_skips_asins_that_already_have_an_ad_row(self) -> None:
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", "", "B00EXAMPLF"]
        name_values = ["", "", "", "商品名", "ルーペ", AD_LABEL, "ボールネット"]

        assert plan_ad_row_insertions(asin_values, name_values) == [7]

    def test_ignores_heading_rows(self) -> None:
        asin_values = ["", "", "", "ASIN", "様子見", "やめる", "過去"]
        name_values = ["", "", "", "商品名", "", "", ""]

        assert plan_ad_row_insertions(asin_values, name_values) == []

    def test_last_asin_at_the_end_of_the_sheet_gets_a_row(self) -> None:
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE"]
        name_values = ["", "", "", "商品名", "ルーペ"]

        assert plan_ad_row_insertions(asin_values, name_values) == [5]

    def test_excludes_a_previously_inserted_but_unlabeled_row_from_insertion(self) -> None:
        # 前回実行が「行の挿入」までは成功したが「ラベル書き込み」で失敗した状態を再現する。
        # ASIN・商品名ともに空だが、その下にはまだ別のASIN行が続いている(=物理的に行は実在する)。
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", "", "B00EXAMPLF"]
        name_values = ["", "", "", "商品名", "ルーペ", "", "ボールネット"]

        assert plan_ad_row_insertions(asin_values, name_values) == [7]


class TestPlanAdRowRecovery:
    def test_detects_a_previously_inserted_but_unlabeled_row(self) -> None:
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", "", "B00EXAMPLF"]
        name_values = ["", "", "", "商品名", "ルーペ", "", "ボールネット"]

        assert plan_ad_row_recovery(asin_values, name_values) == [5]

    def test_empty_when_ad_row_already_labeled(self) -> None:
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", "", "B00EXAMPLF"]
        name_values = ["", "", "", "商品名", "ルーペ", AD_LABEL, "ボールネット"]

        assert plan_ad_row_recovery(asin_values, name_values) == []

    def test_empty_when_no_data_follows_a_blank_row(self) -> None:
        # 既知の限界: 最終行のASINは col_values() が末尾の空セルを返さないため
        # 「未挿入」との区別ができず、recovery 側には出てこない
        # （plan_ad_row_insertions 側で従来通り needs_insertion として扱われる）。
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE"]
        name_values = ["", "", "", "商品名", "ルーペ"]

        assert plan_ad_row_recovery(asin_values, name_values) == []


class TestBuildInsertRequests:
    def test_inserts_after_each_target_row(self) -> None:
        requests = build_insert_requests(sheet_id=551300985, insert_rows=[7, 6])

        ranges = [r["insertDimension"]["range"] for r in requests]
        assert ranges[0] == {
            "sheetId": 551300985, "dimension": "ROWS", "startIndex": 7, "endIndex": 8,
        }
        assert ranges[1] == {
            "sheetId": 551300985, "dimension": "ROWS", "startIndex": 6, "endIndex": 7,
        }

    def test_does_not_inherit_formatting_from_the_row_above(self) -> None:
        requests = build_insert_requests(sheet_id=1, insert_rows=[5])

        assert requests[0]["insertDimension"]["inheritFromBefore"] is False


from insert_ad_rows import _ad_row_numbers


class TestAdRowNumbers:
    def test_each_insertion_shifts_the_ones_below_it(self) -> None:
        # 行6と行7のASINの直下へ入れると、広告行は7と9になる
        assert _ad_row_numbers([7, 6]) == [7, 9]

    def test_single_insertion(self) -> None:
        assert _ad_row_numbers([5]) == [6]


class TestRelabelRowNumbers:
    def test_no_insertions_above_leaves_the_row_unshifted(self) -> None:
        assert _relabel_row_numbers([10], []) == [11]

    def test_insertion_above_the_recovery_row_shifts_it_down(self) -> None:
        # 行3のASINへ新規挿入すると、行10のASIN(と、その直下の未ラベル広告行)は
        # 1行ずつ下へずれる
        assert _relabel_row_numbers([10], [3]) == [12]

    def test_insertion_below_the_recovery_row_does_not_shift_it(self) -> None:
        assert _relabel_row_numbers([3], [10]) == [4]


class TestApplyAdRowPlanRetrySafety:
    @patch("py_src.infrastructure.sheets.retry.time.sleep")
    def test_rerun_after_label_write_failure_does_not_reinsert_a_row(
        self, mock_sleep: Mock
    ) -> None:
        # シナリオ: B00EXAMPLE(行5)にはまだ広告行が無く、直下のB00EXAMPLF(行6)には
        # 既にラベル済みの広告行(行7)がある。1回目の呼び出しで B00EXAMPLE 用の
        # insertDimension(行挿入)までは成功するが、直後のラベル書き込みが接続断で失敗する。
        # @retry_on_transient_error が関数ごと再試行し、2回目は挿入後の状態
        # (行6が挿入済みだが未ラベル、B00EXAMPLFは行7へ、そのラベルは行8へ、それぞれ
        # ずれている)を読み直し、行を再挿入せずラベルだけを書く。
        # insertDimension が2回呼ばれる(＝B00EXAMPLEの下に広告行が二重に入る)と壊れる。
        worksheet = Mock()
        worksheet.id = 1

        state = {"inserted": False}

        def col_values(col: int) -> list[str]:
            if not state["inserted"]:
                if col == 1:  # ASIN_COLUMN
                    return ["", "", "", "ASIN", "B00EXAMPLE", "B00EXAMPLF", ""]
                return ["", "", "", "商品名", "ルーペ", "ボールネット", AD_LABEL]
            # insertDimension 適用後: 行6に空行が入り、B00EXAMPLFとそのラベルは
            # それぞれ1行下(行7・行8)へずれる。ASIN列は最後の実データ("B00EXAMPLF")
            # までしか返らない一方、商品名列は行8のラベルまで実データが続くため
            # col_values の返す長さが列ごとに異なる(gspreadの実挙動を再現)。
            if col == 1:
                return ["", "", "", "ASIN", "B00EXAMPLE", "", "B00EXAMPLF"]
            return ["", "", "", "商品名", "ルーペ", "", "ボールネット", AD_LABEL]

        worksheet.col_values.side_effect = col_values

        def spreadsheet_batch_update(_body: dict) -> None:
            state["inserted"] = True

        worksheet.spreadsheet.batch_update.side_effect = spreadsheet_batch_update

        worksheet.batch_update.side_effect = [
            requests.exceptions.ConnectionError("Connection reset by peer"), None,
        ]

        ad_rows = _apply_ad_row_plan(worksheet, name_column=5)

        assert worksheet.spreadsheet.batch_update.call_count == 1
        assert worksheet.batch_update.call_count == 2
        assert ad_rows == [6]

    @patch("py_src.infrastructure.sheets.retry.time.sleep")
    def test_no_pending_work_makes_no_writes(self, mock_sleep: Mock) -> None:
        worksheet = Mock()
        worksheet.id = 1
        worksheet.col_values.side_effect = [
            ["", "", "", "ASIN", "B00EXAMPLE", ""],
            ["", "", "", "商品名", "ルーペ", AD_LABEL],
        ]

        ad_rows = _apply_ad_row_plan(worksheet, name_column=5)

        assert ad_rows == []
        worksheet.spreadsheet.batch_update.assert_not_called()
        worksheet.batch_update.assert_not_called()
