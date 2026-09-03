from unittest.mock import Mock

from gspread.utils import rowcol_to_a1

from py_src.infrastructure.sheets.ad_sales_sheet import AD_ROW_LABEL, AdSalesSheet

# 4行目がヘッダー。A列=ASIN, B列=商品名, C列以降が日付列
HEADER = ["ASIN", "商品名", 46266, 46265]
# 行1..3 はラベル行、行4 がヘッダー、行5 以降がデータ
COL_A = ["", "", "", "ASIN", "新商品", "B00EXAMPLE", "", "B00EXAMPLF", "", "B00EXAMPLE", ""]
COL_NAME = [
    "", "", "", "商品名", "", "ルーペ", AD_ROW_LABEL, "ボールネット", AD_ROW_LABEL,
    "ルーペ 2個組", AD_ROW_LABEL,
]


def _make_worksheet(
    col_a: list[str] | None = None, col_name: list[str] | None = None
) -> Mock:
    worksheet = Mock()
    worksheet.row_values.return_value = HEADER
    worksheet.col_values.side_effect = lambda col, **kwargs: (
        (col_a if col_a is not None else COL_A)
        if col == 1
        else (col_name if col_name is not None else COL_NAME)
    )
    return worksheet


class TestAdSalesSheet:
    def test_ad_row_is_bound_to_the_asin_above_it(self) -> None:
        sheet = AdSalesSheet(worksheet=_make_worksheet())

        assert sheet.get_ad_rows() == {"B00EXAMPLE": [7, 11], "B00EXAMPLF": [9]}

    def test_label_row_without_asin_above_is_ignored(self) -> None:
        col_a = ["", "", "", "ASIN", "新商品", "", "B00EXAMPLE", ""]
        col_name = ["", "", "", "商品名", "", AD_ROW_LABEL, "ルーペ", AD_ROW_LABEL]
        sheet = AdSalesSheet(worksheet=_make_worksheet(col_a, col_name))

        assert sheet.get_ad_rows() == {"B00EXAMPLE": [8]}

    def test_row_with_asin_in_column_a_is_never_an_ad_row(self) -> None:
        col_a = ["", "", "", "ASIN", "B00EXAMPLE", "B00EXAMPLF"]
        col_name = ["", "", "", "商品名", "ルーペ", AD_ROW_LABEL]
        sheet = AdSalesSheet(worksheet=_make_worksheet(col_a, col_name))

        assert sheet.get_ad_rows() == {}

    def test_writes_units_to_matching_date_column(self) -> None:
        worksheet = _make_worksheet()
        sheet = AdSalesSheet(worksheet=worksheet)
        sheet.get_ad_rows()

        result = sheet.write_ad_units({"2026-09-01": {"B00EXAMPLE": 3, "B00EXAMPLF": 1}})

        assert result.cells_written == 3
        assert result.skipped_dates == ()
        requests = worksheet.batch_update.call_args[0][0]
        by_range = {r["range"]: r["values"] for r in requests}
        assert by_range[rowcol_to_a1(7, 3)] == [[3]]
        assert by_range[rowcol_to_a1(11, 3)] == [[3]]
        assert by_range[rowcol_to_a1(9, 3)] == [[1]]

    def test_skips_dates_without_a_column(self) -> None:
        worksheet = _make_worksheet()
        sheet = AdSalesSheet(worksheet=worksheet)
        sheet.get_ad_rows()

        result = sheet.write_ad_units({"2026-08-01": {"B00EXAMPLE": 3}})

        assert result.cells_written == 0
        assert result.skipped_dates == ("2026-08-01",)
        worksheet.batch_update.assert_not_called()

    def test_reports_skipped_dates_alongside_written_dates(self) -> None:
        worksheet = _make_worksheet()
        sheet = AdSalesSheet(worksheet=worksheet)
        sheet.get_ad_rows()

        result = sheet.write_ad_units({
            "2026-09-01": {"B00EXAMPLE": 3},
            "2026-08-01": {"B00EXAMPLE": 1},
        })

        assert result.cells_written == 3
        assert result.skipped_dates == ("2026-08-01",)

    def test_writes_zero_for_asins_absent_from_the_report(self) -> None:
        worksheet = _make_worksheet()
        sheet = AdSalesSheet(worksheet=worksheet)
        sheet.get_ad_rows()

        sheet.write_ad_units({"2026-09-01": {"B00EXAMPLE": 3}})

        requests = worksheet.batch_update.call_args[0][0]
        by_range = {r["range"]: r["values"] for r in requests}
        assert by_range[rowcol_to_a1(9, 3)] == [[0]]

    def test_writes_zero_to_every_ad_row_when_the_day_has_no_ad_sales(self) -> None:
        worksheet = _make_worksheet()
        sheet = AdSalesSheet(worksheet=worksheet)
        sheet.get_ad_rows()

        result = sheet.write_ad_units({"2026-09-01": {}})

        assert result.cells_written == 3
        requests = worksheet.batch_update.call_args[0][0]
        assert all(r["values"] == [[0]] for r in requests)

    def test_writes_all_dates_in_one_batch(self) -> None:
        worksheet = _make_worksheet()
        sheet = AdSalesSheet(worksheet=worksheet)
        sheet.get_ad_rows()

        sheet.write_ad_units(
            {"2026-09-01": {"B00EXAMPLF": 1}, "2026-08-31": {"B00EXAMPLF": 2}}
        )

        assert worksheet.batch_update.call_count == 1
        requests = worksheet.batch_update.call_args[0][0]
        by_range = {r["range"]: r["values"] for r in requests}
        assert by_range[rowcol_to_a1(9, 3)] == [[1]]
        assert by_range[rowcol_to_a1(9, 4)] == [[2]]
