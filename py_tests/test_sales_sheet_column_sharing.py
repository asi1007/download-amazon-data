from datetime import date
from unittest.mock import Mock

import pytest
from gspread.utils import rowcol_to_a1

from py_src.infrastructure.sheets.sales_sheet import SalesSheet, _date_serial
from py_src.domain.value_objects.sales_info import SalesInfo

TODAY = date(2026, 9, 3)
YESTERDAY = date(2026, 9, 2)
TODAY_SERIAL = _date_serial(TODAY)
YESTERDAY_SERIAL = _date_serial(YESTERDAY)


TEXT_HEADERS = ["", "目標販売数", "", "", "自社価格"]
SERIAL_HEADERS = ["", "目標販売数", TODAY_SERIAL, YESTERDAY_SERIAL, "自社価格"]


def _create_mock_worksheet_with_today_and_yesterday_columns(
    unformatted_calls: int = 1,
) -> Mock:
    # 実運用の行構成（行1〜4は予約行、ASINは行5以降）を再現する。
    sales_ws = Mock()
    sales_ws.row_values.side_effect = [TEXT_HEADERS, *([SERIAL_HEADERS] * unformatted_calls)]
    sales_ws.col_values.return_value = ["header", "", "合計", "header4", "B00EXAMPLE"]
    return sales_ws


class TestWriteSalesNumsTargetDateResolution:
    def test_writes_today_target_date_to_today_column(self) -> None:
        sales_ws = _create_mock_worksheet_with_today_and_yesterday_columns()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=5)}, target_date=TODAY)

        sales_ws.insert_cols.assert_not_called()
        requests = sales_ws.batch_update.call_args_list[0][0][0]
        written_ranges = {r["range"] for r in requests}
        assert rowcol_to_a1(5, 3) in written_ranges

    def test_writes_yesterday_target_date_to_yesterday_column(self) -> None:
        sales_ws = _create_mock_worksheet_with_today_and_yesterday_columns()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=5)}, target_date=YESTERDAY)

        sales_ws.insert_cols.assert_not_called()
        requests = sales_ws.batch_update.call_args_list[0][0][0]
        written_ranges = {r["range"] for r in requests}
        assert rowcol_to_a1(5, 4) in written_ranges

    def test_inserts_column_when_target_date_absent(self) -> None:
        sales_ws = Mock()
        sales_ws.row_values.return_value = ["", "目標販売数", "", "", "自社価格"]
        sales_ws.col_values.return_value = ["header", "", "合計", "header4", "B00EXAMPLE"]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=1)}, target_date=TODAY)

        sales_ws.insert_cols.assert_called_once_with(
            [[TODAY_SERIAL, "", "", TODAY_SERIAL]], 3
        )


class TestWritePricesUsesSalesResolvedColumn:
    def test_writes_price_to_yesterday_column_when_today_column_is_leftmost(self) -> None:
        sales_ws = _create_mock_worksheet_with_today_and_yesterday_columns()
        sales_ws.get_notes.return_value = [[""], [""], [""], [""], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=3)}, target_date=YESTERDAY)
        sheet.write_prices({"B00EXAMPLE": 3000.0})

        note_cells = list(sales_ws.update_notes.call_args_list[0][0][0].keys())
        assert note_cells == [rowcol_to_a1(5, 4)]

    def test_does_not_write_price_to_today_leftmost_column(self) -> None:
        sales_ws = _create_mock_worksheet_with_today_and_yesterday_columns()
        sales_ws.get_notes.return_value = [[""], [""], [""], [""], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=3)}, target_date=YESTERDAY)
        sheet.write_prices({"B00EXAMPLE": 3000.0})

        note_cells = list(sales_ws.update_notes.call_args_list[0][0][0].keys())
        assert rowcol_to_a1(5, 3) not in note_cells


class TestWritePricesRequiresPriorWriteSalesNums:
    def test_raises_when_write_sales_nums_not_called_first(self) -> None:
        sales_ws = _create_mock_worksheet_with_today_and_yesterday_columns()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        with pytest.raises(RuntimeError):
            sheet.write_prices({"B00EXAMPLE": 3000.0})
