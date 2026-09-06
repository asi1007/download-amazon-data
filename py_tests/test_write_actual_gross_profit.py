from datetime import date
from unittest.mock import Mock

from gspread import Worksheet
from gspread.utils import rowcol_to_a1

from py_src.domain.value_objects.actual_profit_cell import ActualProfitCell
from py_src.infrastructure.sheets.label_rows import GROSS_PROFIT_ROW_LABEL, date_serial
from py_src.infrastructure.sheets.sales_sheet import SalesSheet

TARGET_DATE = date(2026, 9, 4)
OTHER_DATE = date(2026, 9, 3)
PROFIT_COLUMN = 3
OTHER_COLUMN = 4


def _worksheet() -> Mock:
    worksheet = Mock(spec=Worksheet)
    worksheet.row_values.return_value = [
        "ASIN", "商品名", date_serial(TARGET_DATE), date_serial(OTHER_DATE)
    ]
    col_a = ["", "", "", "ASIN", "B00EXAMPLE", "", "B00EXAMPLF", ""]
    col_name = [
        "", "", "", "商品名",
        "ルーペ", GROSS_PROFIT_ROW_LABEL,
        "ボール", GROSS_PROFIT_ROW_LABEL,
    ]
    worksheet.col_values.side_effect = lambda col, **kwargs: col_a if col == 1 else col_name
    worksheet.id = 0
    return worksheet


class TestWriteActualGrossProfit:
    def test_writes_the_blended_profit_into_the_date_column(self) -> None:
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        result = sheet.write_actual_gross_profit({
            TARGET_DATE: [ActualProfitCell("B00EXAMPLE", 3750.0, 3900.0, True)],
        })

        assert result.cells_written == 1
        requests = worksheet.batch_update.call_args[0][0]
        assert requests == [{"range": rowcol_to_a1(6, PROFIT_COLUMN), "values": [[3750.0]]}]

    def test_keeps_the_estimate_in_the_cell_note(self) -> None:
        # 乖離シートは直近14日しか持たないので、日ごとの履歴はノートに残す
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        sheet.write_actual_gross_profit({
            TARGET_DATE: [ActualProfitCell("B00EXAMPLE", 3750.0, 3900.0, True)],
        })

        notes = worksheet.update_notes.call_args[0][0]
        assert notes == {rowcol_to_a1(6, PROFIT_COLUMN): "見積 3,900 / 実測 3,750"}

    def test_settled_cell_loses_the_yellow_but_keeps_the_k_format(self) -> None:
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        result = sheet.write_actual_gross_profit({
            TARGET_DATE: [
                ActualProfitCell("B00EXAMPLE", 3750.0, 3900.0, True),
                ActualProfitCell("B00EXAMPLF", 1200.0, 1300.0, False),
            ],
        })

        assert result.cells_cleared == 1
        requests = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]
        by_row = {r["repeatCell"]["range"]["startRowIndex"]: r["repeatCell"] for r in requests}
        settled = by_row[5]["cell"]["userEnteredFormat"]
        assert settled["numberFormat"] == {"type": "NUMBER", "pattern": '#,##0.0,"K"'}
        assert "backgroundColor" not in settled

    def test_unsettled_cell_is_painted_yellow_even_if_it_never_was(self) -> None:
        # 見積を書くのは当日・前日だけ。古いセルは一度も黄色になっていないため、
        # ここで塗り直さないと「白 = 確定」が成り立たない
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        sheet.write_actual_gross_profit({
            TARGET_DATE: [ActualProfitCell("B00EXAMPLF", 1200.0, 1300.0, False)],
        })

        requests = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]
        applied = requests[0]["repeatCell"]["cell"]["userEnteredFormat"]
        assert applied["backgroundColor"] == {"red": 1.0, "green": 0.95, "blue": 0.8}
        assert applied["numberFormat"] == {"type": "NUMBER", "pattern": '#,##0.0,"K"'}

    def test_both_fields_are_rewritten_so_stale_formats_do_not_survive(self) -> None:
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        sheet.write_actual_gross_profit({
            TARGET_DATE: [ActualProfitCell("B00EXAMPLE", 3750.0, 3900.0, True)],
        })

        requests = worksheet.spreadsheet.batch_update.call_args[0][0]["requests"]
        assert requests[0]["repeatCell"]["fields"] == "userEnteredFormat(numberFormat,backgroundColor)"

    def test_reports_dates_whose_column_does_not_exist(self) -> None:
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        result = sheet.write_actual_gross_profit({
            date(2099, 1, 1): [ActualProfitCell("B00EXAMPLE", 1.0, 1.0, True)],
        })

        assert result.skipped_dates == ("2099-01-01",)
        worksheet.batch_update.assert_not_called()

    def test_reports_asins_without_a_gross_profit_row(self) -> None:
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        result = sheet.write_actual_gross_profit({
            TARGET_DATE: [
                ActualProfitCell("B00EXAMPLE", 3750.0, 3900.0, True),
                ActualProfitCell("B00NOROW999", 100.0, 100.0, True),
            ],
        })

        assert result.asins_without_row == ("B00NOROW999",)

    def test_note_and_clear_ranges_survive_batch_update_mutating_the_requests(self) -> None:
        # 実運用の gspread は渡した dict の "range" を "'売上/日'!C6" に書き換える
        def _prefixing(requests: list[dict], **kwargs: object) -> None:
            for request in requests:
                request["range"] = f"'売上/日'!{request['range']}"

        worksheet = _worksheet()
        worksheet.batch_update.side_effect = _prefixing
        sheet = SalesSheet(sales_worksheet=worksheet)

        sheet.write_actual_gross_profit({
            TARGET_DATE: [ActualProfitCell("B00EXAMPLE", 3750.0, 3900.0, True)],
        })

        assert list(worksheet.update_notes.call_args[0][0]) == [rowcol_to_a1(6, PROFIT_COLUMN)]

    def test_writes_across_several_dates_in_one_batch(self) -> None:
        worksheet = _worksheet()
        sheet = SalesSheet(sales_worksheet=worksheet)

        result = sheet.write_actual_gross_profit({
            TARGET_DATE: [ActualProfitCell("B00EXAMPLE", 1.0, 1.0, True)],
            OTHER_DATE: [ActualProfitCell("B00EXAMPLE", 2.0, 2.0, True)],
        })

        assert result.cells_written == 2
        assert worksheet.batch_update.call_count == 1
