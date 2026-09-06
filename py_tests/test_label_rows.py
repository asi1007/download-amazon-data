from datetime import date
from unittest.mock import Mock

from gspread import Worksheet

from py_src.infrastructure.sheets.label_rows import (
    AD_COST_ROW_LABEL,
    AD_ROW_LABEL,
    GROSS_PROFIT_ROW_LABEL,
    ROW_LABELS_IN_ORDER,
    bind_label_rows,
    date_serial,
    OPERATING_PROFIT_ROW_LABEL,
    find_column,
    read_date_columns,
)

# 行1〜4は予約。行5以降が ASIN と3本のラベル行の繰り返し
ASIN_VALUES = ["", "", "", "ASIN", "B00EXAMPLE", "", "", "", "見出し", "B00EXAMPLF", "", "", ""]
NAME_VALUES = [
    "", "", "", "商品名", "ルーペ", AD_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL,
    "", "ボールネット", AD_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL,
]


class TestBindLabelRows:
    def test_binds_each_label_to_its_own_rows(self) -> None:
        assert bind_label_rows(ASIN_VALUES, NAME_VALUES, AD_ROW_LABEL) == {
            "B00EXAMPLE": [6], "B00EXAMPLF": [11],
        }
        assert bind_label_rows(ASIN_VALUES, NAME_VALUES, GROSS_PROFIT_ROW_LABEL) == {
            "B00EXAMPLE": [7], "B00EXAMPLF": [12],
        }
        assert bind_label_rows(ASIN_VALUES, NAME_VALUES, AD_COST_ROW_LABEL) == {
            "B00EXAMPLE": [8], "B00EXAMPLF": [13],
        }

    def test_heading_row_breaks_the_binding(self) -> None:
        asin_values = ["", "", "", "ASIN", "見出し", "", ""]
        name_values = ["", "", "", "商品名", "", AD_ROW_LABEL, ""]

        assert bind_label_rows(asin_values, name_values, AD_ROW_LABEL) == {}

    def test_same_asin_twice_gets_both_rows(self) -> None:
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", "", "B00EXAMPLE", ""]
        name_values = ["", "", "", "商品名", "ルーペ", AD_ROW_LABEL, "ルーペ2", AD_ROW_LABEL]

        assert bind_label_rows(asin_values, name_values, AD_ROW_LABEL) == {
            "B00EXAMPLE": [6, 8],
        }

    def test_row_with_asin_is_never_a_label_row(self) -> None:
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", "B00EXAMPLF"]
        name_values = ["", "", "", "商品名", "ルーペ", AD_ROW_LABEL]

        assert bind_label_rows(asin_values, name_values, AD_ROW_LABEL) == {}


class TestRowLabelsInOrder:
    def test_order_matches_the_spec(self) -> None:
        # 営業利益は粗利益の上。marketar/listing-creator 側の LABEL_ROWS_IN_ORDER
        # と一致していなければ、新商品だけ行が足りなくなる
        assert ROW_LABELS_IN_ORDER == (
            AD_ROW_LABEL,
            OPERATING_PROFIT_ROW_LABEL,
            GROSS_PROFIT_ROW_LABEL,
            AD_COST_ROW_LABEL,
        )


class TestDateSerial:
    def test_known_dates(self) -> None:
        assert date_serial(date(2026, 9, 2)) == 46267
        assert date_serial(date(2026, 9, 5)) == 46270


class TestReadDateColumns:
    def test_integers_in_header_row_are_date_columns(self) -> None:
        worksheet = Mock()
        worksheet.row_values.return_value = ["ASIN", "商品名", "目標販売数", 46270, 46269]

        assert read_date_columns(worksheet) == {46270: 4, 46269: 5}


class TestFindColumn:
    def test_finds_by_name(self) -> None:
        assert find_column(["ASIN", "商品名", "SKU"], "SKU") == 3

    def test_missing_raises(self) -> None:
        try:
            find_column(["ASIN"], "SKU")
        except ValueError as error:
            assert "SKU" in str(error)
        else:
            raise AssertionError("ValueError が上がらなかった")


class TestFindColumnNormalization:
    def test_matches_header_with_an_embedded_newline(self) -> None:
        assert find_column(["ASIN", "ライバル\nURL"], "ライバルURL") == 2

    def test_matches_regardless_of_case(self) -> None:
        # 売上/日 は 'SKU'(大文字) と 'fnsku'(小文字) が同居している
        assert find_column(["ASIN", "SKU"], "sku") == 2
        assert find_column(["ASIN", "fnsku"], "FNSKU") == 2

    def test_still_raises_when_absent(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            find_column(["ASIN"], "原価")


class TestReadDateColumnsAmbiguity:
    def test_prefers_the_leftmost_column_when_a_date_appears_twice(self) -> None:
        # 同じ日付が2列にあると、個数と粗利益が別の列へ入る事故が起こりうる。
        # SalesSheet._find_serial_column も左から探すので左を採る
        worksheet = Mock(spec=Worksheet)
        worksheet.row_values.return_value = ["ASIN", "商品名", 46269, 46268, 46269]

        assert read_date_columns(worksheet)[46269] == 3

    def test_boolean_header_is_not_treated_as_a_date(self) -> None:
        worksheet = Mock(spec=Worksheet)
        worksheet.row_values.return_value = ["ASIN", True, 46269]

        assert read_date_columns(worksheet) == {46269: 3}
