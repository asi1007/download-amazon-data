from insert_ad_rows import build_insert_requests, plan_ad_row_insertions

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
