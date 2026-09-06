from unittest.mock import Mock

from gspread import Worksheet
from gspread.utils import rowcol_to_a1

from py_src.infrastructure.sheets.label_rows import (
    AD_COST_ROW_LABEL,
    AD_ROW_LABEL,
    GROSS_PROFIT_ROW_LABEL,
    OPERATING_PROFIT_ROW_LABEL,
)
from py_src.infrastructure.sheets.sales_sheet import SalesSheet


def _worksheet() -> Mock:
    worksheet = Mock(spec=Worksheet)
    worksheet.row_values.return_value = ["ASIN", "商品名", 46269, 46268]
    col_a = ["", "", "", "ASIN", "B00EXAMPLE", "", "", "", ""]
    col_name = [
        "", "", "", "商品名",
        "ルーペ", AD_ROW_LABEL, OPERATING_PROFIT_ROW_LABEL,
        GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL,
    ]
    worksheet.col_values.side_effect = lambda col, **kwargs: col_a if col == 1 else col_name
    worksheet.id = 0
    return worksheet


class TestOperatingProfitFormulas:
    def test_writes_gross_profit_minus_ad_cost_as_a_formula(self) -> None:
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        written = sheet.write_operating_profit_formulas([3])

        assert written == 1
        request = worksheet.batch_update.call_args[0][0][0]
        assert request["range"] == rowcol_to_a1(7, 3)
        assert request["values"] == [['=IF(C8="","",C8-N(C9))']]

    def test_formulas_are_sent_as_formulas_not_text(self) -> None:
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        sheet.write_operating_profit_formulas([3])

        assert worksheet.batch_update.call_args.kwargs["value_input_option"] == "USER_ENTERED"

    def test_blank_gross_profit_leaves_the_cell_blank(self) -> None:
        # 0 と書くと「利益ゼロ」と「計算できない」の区別がつかなくなる
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        sheet.write_operating_profit_formulas([3])

        formula = worksheet.batch_update.call_args[0][0][0]["values"][0][0]
        assert formula.startswith('=IF(C8="","",')

    def test_missing_ad_cost_counts_as_zero(self) -> None:
        # N() は空セルを 0 として扱う。広告費が未取得の日でも粗利益がそのまま出る
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        sheet.write_operating_profit_formulas([3])

        assert "N(C9)" in worksheet.batch_update.call_args[0][0][0]["values"][0][0]

    def test_writes_every_requested_column(self) -> None:
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        assert sheet.write_operating_profit_formulas([3, 4]) == 2

    def test_applies_the_same_number_format_as_the_other_money_rows(self) -> None:
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        sheet.write_operating_profit_formulas([3])

        request = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"][0]["repeatCell"]
        assert request["cell"]["userEnteredFormat"]["numberFormat"] == {
            "type": "NUMBER", "pattern": "#,##0.0,"
        }


class TestFormulasFollowTheProfitWrites:
    def test_writing_gross_profit_also_ensures_the_formula(self) -> None:
        # 日付列は daily が作る。作られた直後は営業利益の数式が無いので、
        # 粗利益を書くたびに入れ直さないとその列だけ空のまま残る
        from datetime import date

        from py_src.infrastructure.sheets.label_rows import date_serial

        target = date(2026, 9, 4)
        worksheet = Mock(spec=Worksheet)
        worksheet.id = 0
        worksheet.row_values.return_value = ["ASIN", "商品名", date_serial(target)]
        col_a = ["", "", "", "ASIN", "B00EXAMPLE", "", "", "", ""]
        col_name = [
            "", "", "", "商品名",
            "ルーペ", AD_ROW_LABEL, OPERATING_PROFIT_ROW_LABEL,
            GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL,
        ]
        worksheet.col_values.side_effect = lambda col, **kwargs: col_a if col == 1 else col_name
        sheet = SalesSheet(sales_worksheet=worksheet)

        sheet.write_gross_profit({"B00EXAMPLE": 1200.0}, target)

        formulas = [
            call[0][0][0]["values"][0][0]
            for call in worksheet.batch_update.call_args_list
            if str(call[0][0][0]["values"][0][0]).startswith("=")
        ]
        assert formulas == ['=IF(C8="","",C8-N(C9))', '=SUMIF($B$5:$B,"営業利益",C$5:C)']


class TestOperatingProfitTotals:
    def test_row_two_sums_the_operating_profit_rows(self) -> None:
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        assert sheet.write_operating_profit_totals([3]) == 1
        request = worksheet.batch_update.call_args[0][0][0]
        assert request["range"] == "C2"
        assert request["values"] == [['=SUMIF($B$5:$B,"営業利益",C$5:C)']]

    def test_uses_sumif_so_products_can_be_added_without_editing_the_formula(self) -> None:
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        sheet.write_operating_profit_totals([3])

        assert "SUMIF" in worksheet.batch_update.call_args[0][0][0]["values"][0][0]

    def test_shown_in_thousands_like_the_total_sales_row(self) -> None:
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        sheet.write_operating_profit_totals([3])

        assert worksheet.format.call_args[0][1] == {
            "numberFormat": {"type": "NUMBER", "pattern": '#,##0,"千円"'}
        }
