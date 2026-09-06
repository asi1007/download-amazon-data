import re
from datetime import date
from unittest.mock import Mock
from gspread import Worksheet
from gspread.utils import rowcol_to_a1
from py_src.infrastructure.sheets.label_rows import GROSS_PROFIT_ROW_LABEL, date_serial
from py_src.infrastructure.sheets.sales_sheet import (
    SalesSheet,
    FETCH_TIME_ROW,
    HEADER_ROW,
    TOTAL_AMOUNT_ROW,
)
import pytest
from py_src.domain.value_objects.gross_profit_write_result import (
    GrossProfitRowsNotFoundError,
)
from py_src.domain.value_objects.sales_info import SalesInfo


def _create_mock_worksheet() -> Mock:
    # 実運用の行構成（行1〜4はヘッダー・合計・取得時刻の予約行、ASINは行5以降）を再現する。
    sales_ws = Mock()
    sales_ws.row_values.return_value = ["", "目標販売数", "", "", "自社価格"]
    sales_ws.col_values.return_value = [
        "header", "", "合計", "header4",
        "B00EXAMPLE", "B00EXAMPLF", "", "header2", "B00EXAMPLG",
    ]
    return sales_ws


class TestSalesSheet:
    def test_get_asin_list(self) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        asin_list = sheet.get_asin_list()
        assert asin_list == ["B00EXAMPLE", "B00EXAMPLF", "B00EXAMPLG"]

    def test_write_sales_nums_total_amount_to_row3(self) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        asin_sales = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
            "B00EXAMPLF": SalesInfo(unit_count=1, total_sales_amount=3000.0, order_count=1),
            "B00EXAMPLG": SalesInfo(unit_count=3, total_sales_amount=4500.0, order_count=2),
        }
        sheet.write_sales_nums(asin_sales)

        assert sales_ws.insert_cols.call_count == 1
        assert sales_ws.insert_cols.call_args[0][1] == 3
        row3_range = rowcol_to_a1(3, 3)
        requests = sales_ws.batch_update.call_args_list[0][0][0]
        row3_request = [r for r in requests if r["range"] == row3_range]
        assert len(row3_request) == 1
        assert row3_request[0]["values"] == [[13500.0]]

    def test_write_sales_nums_totals_only_fetched_asins(self) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        asin_sales = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
        }
        sheet.write_sales_nums(asin_sales)

        row3_range = rowcol_to_a1(3, 3)
        requests = sales_ws.batch_update.call_args_list[0][0][0]
        row3_request = [r for r in requests if r["range"] == row3_range]
        assert row3_request[0]["values"] == [[6000.0]]

    def test_write_sales_nums_leaves_unfetched_asin_cell_empty(self) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        asin_sales = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
        }
        sheet.write_sales_nums(asin_sales)

        requests = sales_ws.batch_update.call_args_list[0][0][0]
        written_ranges = {r["range"] for r in requests}
        assert rowcol_to_a1(5, 3) in written_ranges  # B00EXAMPLE (fetched)
        assert rowcol_to_a1(9, 3) not in written_ranges  # B00EXAMPLG (not fetched)

    def test_write_sales_nums_applies_date_format_to_label_cells(self) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=2)})

        formats = sales_ws.batch_format.call_args[0][0]
        date_format = {"numberFormat": {"type": "DATE", "pattern": "dd"}}
        applied = {f["range"]: f["format"] for f in formats}
        assert applied[rowcol_to_a1(1, 3)] == date_format
        assert applied[rowcol_to_a1(4, 3)] == date_format

    def test_write_sales_nums_applies_thousand_yen_format_to_total_row(self) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0)})

        formats = sales_ws.batch_format.call_args[0][0]
        applied = {f["range"]: f["format"] for f in formats}
        assert applied[rowcol_to_a1(3, 3)] == {
            "numberFormat": {"type": "NUMBER", "pattern": '#,##0,"千円"'}
        }

    def test_write_sales_nums_keeps_total_amount_in_yen(self) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=502166.0)})

        requests = sales_ws.batch_update.call_args_list[0][0][0]
        row3_request = [r for r in requests if r["range"] == rowcol_to_a1(3, 3)]
        assert row3_request[0]["values"] == [[502166.0]]

    def test_write_sales_nums_skips_total_row_when_include_total_is_false(self) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        asin_sales = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
        }
        sheet.write_sales_nums(asin_sales, include_total=False)

        requests = sales_ws.batch_update.call_args_list[0][0][0]
        row3_range = rowcol_to_a1(3, 3)
        assert not any(r["range"] == row3_range for r in requests)

    def test_write_sales_nums_still_writes_fetched_cells_when_include_total_is_false(self) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        asin_sales = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
        }
        sheet.write_sales_nums(asin_sales, include_total=False)

        requests = sales_ws.batch_update.call_args_list[0][0][0]
        written_ranges = {r["range"] for r in requests}
        assert rowcol_to_a1(5, 3) in written_ranges  # B00EXAMPLE (fetched, still written)

    def test_write_sales_nums_includes_total_row_by_default(self) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums(
            {"B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0)}
        )

        requests = sales_ws.batch_update.call_args_list[0][0][0]
        row3_range = rowcol_to_a1(3, 3)
        assert any(r["range"] == row3_range for r in requests)

    def test_write_prices_updates_cells(self) -> None:
        sales_ws = _create_mock_worksheet()
        sales_ws.get_notes.return_value = [["2800"], ["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        prices = {"B00EXAMPLE": 3000.0}
        sheet.write_prices(prices)

        sales_ws.batch_update.assert_called()


CHEAPER_COLOR = {"backgroundColor": {"red": 1, "green": 0, "blue": 0}}
PRICIER_COLOR = {"backgroundColor": {"red": 0, "green": 1, "blue": 1}}


def _colored_cells(sales_ws: Mock, color: dict) -> set[str]:
    cells: set[str] = set()
    for call in sales_ws.format.call_args_list:
        if call[0][1] == color:
            cells.update(call[0][0])
    return cells


class TestPriceChangeColoring:
    def test_compares_today_price_against_previous_day_note(self) -> None:
        sales_ws = _create_mock_worksheet()
        sales_ws.get_notes.return_value = [[""], [""], [""], [""], ["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        sheet.write_prices({"B00EXAMPLE": 2000.0, "B00EXAMPLF": 3500.0})

        assert _colored_cells(sales_ws, CHEAPER_COLOR) == {rowcol_to_a1(5, 3)}
        assert _colored_cells(sales_ws, PRICIER_COLOR) == {rowcol_to_a1(6, 3)}

    def test_ignores_previous_day_cell_value(self) -> None:
        sales_ws = _create_mock_worksheet()
        sales_ws.get_notes.return_value = [[""], [""], [""], [""], [""], [""]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        sheet.write_prices({"B00EXAMPLE": 2000.0, "B00EXAMPLF": 3500.0})

        assert _colored_cells(sales_ws, CHEAPER_COLOR) == set()
        assert _colored_cells(sales_ws, PRICIER_COLOR) == set()

    def test_clears_background_of_cells_without_price_change(self) -> None:
        sales_ws = _create_mock_worksheet()
        sales_ws.get_notes.return_value = [[""], [""], [""], [""], ["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        sheet.write_prices({"B00EXAMPLE": 2800.0, "B00EXAMPLF": 3500.0})

        cleared = _cleared_background_ranges(sales_ws)
        assert rowcol_to_a1(5, 3) in cleared
        assert rowcol_to_a1(6, 3) in cleared

    def test_clears_background_before_applying_new_color(self) -> None:
        sales_ws = _create_mock_worksheet()
        sales_ws.get_notes.return_value = [[""], [""], [""], [""], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        sheet.write_prices({"B00EXAMPLE": 2000.0})

        assert sales_ws.spreadsheet.batch_update.called
        assert sales_ws.format.called


def _cleared_background_ranges(sales_ws: Mock) -> set[str]:
    cleared: set[str] = set()
    for call in sales_ws.spreadsheet.batch_update.call_args_list:
        for request in call[0][0]["requests"]:
            repeat_cell = request.get("repeatCell")
            if not repeat_cell:
                continue
            if repeat_cell["fields"] != "userEnteredFormat.backgroundColor":
                continue
            grid = repeat_cell["range"]
            cleared.add(
                rowcol_to_a1(grid["startRowIndex"] + 1, grid["startColumnIndex"] + 1)
            )
    return cleared


class TestWritePricesQuota:
    def test_does_not_call_per_asin_write_apis(self) -> None:
        sales_ws = _create_mock_worksheet()
        sales_ws.get_notes.return_value = [["2800"], ["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        sheet.write_prices({"B00EXAMPLE": 3000.0, "B00EXAMPLF": 2000.0, "B00EXAMPLG": 2800.0})

        sales_ws.update_cell.assert_not_called()
        sales_ws.update_note.assert_not_called()
        sales_ws.cell.assert_not_called()

    def test_write_calls_stay_constant_as_asins_grow(self) -> None:
        def count_write_calls(asin_count: int) -> int:
            # 実運用の行構成（行1〜4は予約行、ASINは行5以降）を再現する。
            sales_ws = Mock()
            sales_ws.row_values.return_value = ["", "目標販売数", "", "", "自社価格"]
            asins = [f"B00EXAM{i:03d}" for i in range(asin_count)]
            sales_ws.col_values.return_value = ["header", "", "合計", "header4", *asins]
            sales_ws.get_notes.return_value = [["2800"] for _ in range(4 + asin_count)]
            sheet = SalesSheet(sales_worksheet=sales_ws)
            sheet.get_asin_list()
            sheet.write_sales_nums({})
            sheet.write_prices({asin: 3000.0 for asin in asins})
            return (
                len(sales_ws.batch_update.call_args_list)
                + len(sales_ws.update_notes.call_args_list)
                + len(sales_ws.format.call_args_list)
                + len(sales_ws.update_cell.call_args_list)
                + len(sales_ws.update_note.call_args_list)
            )

        assert count_write_calls(3) == count_write_calls(60)

    def test_writes_all_notes_in_one_call(self) -> None:
        sales_ws = _create_mock_worksheet()
        sales_ws.get_notes.return_value = [["2800"], ["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        sheet.write_prices({"B00EXAMPLE": 3000.0, "B00EXAMPLF": 2000.0})

        assert len(sales_ws.update_notes.call_args_list) == 1
        notes = sales_ws.update_notes.call_args_list[0][0][0]
        assert set(notes.values()) == {"3000.0", "2000.0"}

    def test_colors_cheaper_and_pricier_cells_in_two_calls(self) -> None:
        sales_ws = _create_mock_worksheet()
        sales_ws.get_notes.return_value = [["2800"], ["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        sheet.write_prices(
            {"B00EXAMPLE": 2000.0, "B00EXAMPLF": 3000.0, "B00EXAMPLG": 2800.0}
        )

        assert len(sales_ws.format.call_args_list) <= 2

    def test_skips_all_writes_when_no_matching_asin(self) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        batch_update_calls_before = sales_ws.batch_update.call_count
        sheet.write_prices({"UNKNOWN": 3000.0})

        assert sales_ws.batch_update.call_count == batch_update_calls_before
        sales_ws.update_notes.assert_not_called()


def _create_mock_worksheet_with_duplicates() -> Mock:
    # 実運用の行構成に合わせ、重複ASIN(B00EXAMPLE)は行5・行7に、単独ASIN(B00EXAMPLF)は行8に置く。
    sales_ws = Mock()
    sales_ws.row_values.return_value = ["", "目標販売数", "", "", "自社価格"]
    sales_ws.col_values.return_value = [
        "header", "", "合計", "header4",
        "B00EXAMPLE", "", "B00EXAMPLE", "B00EXAMPLF",
    ]
    return sales_ws


class TestDuplicatedAsinRows:
    def test_get_asin_list_deduplicates_preserving_order(self) -> None:
        sheet = SalesSheet(sales_worksheet=_create_mock_worksheet_with_duplicates())
        assert sheet.get_asin_list() == ["B00EXAMPLE", "B00EXAMPLF"]

    def test_write_sales_nums_fills_every_duplicated_row(self) -> None:
        sales_ws = _create_mock_worksheet_with_duplicates()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums({"B00EXAMPLE": SalesInfo(unit_count=4, total_sales_amount=12000.0)})

        requests = sales_ws.batch_update.call_args_list[0][0][0]
        written = {r["range"]: r["values"] for r in requests}
        assert written[rowcol_to_a1(5, 3)] == [[4]]
        assert written[rowcol_to_a1(7, 3)] == [[4]]

    def test_write_sales_nums_counts_duplicated_asin_once_in_total(self) -> None:
        sales_ws = _create_mock_worksheet_with_duplicates()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums({
            "B00EXAMPLE": SalesInfo(unit_count=4, total_sales_amount=12000.0),
            "B00EXAMPLF": SalesInfo(unit_count=1, total_sales_amount=3000.0),
        })

        requests = sales_ws.batch_update.call_args_list[0][0][0]
        row3_request = [r for r in requests if r["range"] == rowcol_to_a1(3, 3)]
        assert row3_request[0]["values"] == [[15000.0]]

    def test_write_prices_fills_every_duplicated_row(self) -> None:
        sales_ws = _create_mock_worksheet_with_duplicates()
        sales_ws.get_notes.return_value = [["2800"] for _ in range(8)]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        sheet.write_prices({"B00EXAMPLE": 3000.0})

        requests = sales_ws.batch_update.call_args_list[-1][0][0]
        written_ranges = {r["range"] for r in requests}
        assert rowcol_to_a1(5, 5) in written_ranges
        assert rowcol_to_a1(7, 5) in written_ranges

    def test_get_selling_prices_reads_duplicated_asin_once(self) -> None:
        sales_ws = _create_mock_worksheet_with_duplicates()
        sales_ws.get.return_value = [
            ["header"], [""], ["合計"], ["header4"], ["500"], [""], ["500"], ["800"],
        ]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        assert sheet.get_selling_prices() == {"B00EXAMPLE": 500.0, "B00EXAMPLF": 800.0}


class TestGetSellingPrices:
    def test_returns_asin_to_price_map(self) -> None:
        sales_ws = Mock()
        sales_ws.row_values.return_value = ["", "目標販売数", "", "", "自社価格"]
        sales_ws.col_values.return_value = [
            "header", "header2", "header3", "header4",
            "B00EXAMPLE", "B00EXAMPLF", "B00EXAMPLG",
        ]
        sales_ws.get.return_value = [
            ["header"], ["header2"], ["header3"], ["header4"],
            ["500"], ["800"], [""],
        ]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        prices = sheet.get_selling_prices()
        assert prices == {"B00EXAMPLE": 500.0, "B00EXAMPLF": 800.0}

    def test_returns_empty_when_no_asins(self) -> None:
        sales_ws = Mock()
        sales_ws.row_values.return_value = ["", "目標販売数", "", "", "自社価格"]
        sales_ws.col_values.return_value = ["header"]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        prices = sheet.get_selling_prices()
        assert prices == {}


class TestFetchTimeRow:
    def test_writes_hh_mm_shaped_value_to_row2(self) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums(
            {"B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0)}
        )

        requests = sales_ws.batch_update.call_args_list[0][0][0]
        row2_requests = [r for r in requests if r["range"] == rowcol_to_a1(FETCH_TIME_ROW, 3)]
        assert len(row2_requests) == 1
        value = row2_requests[0]["values"][0][0]
        assert isinstance(value, str)
        assert re.fullmatch(r"\d{2}:\d{2}", value)

    def test_rows_1_3_4_still_populated_alongside_row2(self) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums(
            {"B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0)}
        )

        requests = sales_ws.batch_update.call_args_list[0][0][0]
        written = {r["range"]: r["values"] for r in requests}
        assert written[rowcol_to_a1(1, 3)] == written[rowcol_to_a1(HEADER_ROW, 3)]
        assert written[rowcol_to_a1(TOTAL_AMOUNT_ROW, 3)] == [[6000.0]]

    def test_labeled_column_insertion_leaves_row2_empty_before_batch_update_fills_it(
        self,
    ) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums(
            {"B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0)}
        )

        inserted_label_column = sales_ws.insert_cols.call_args[0][0][0]
        assert inserted_label_column[FETCH_TIME_ROW - 1] == ""


def _create_mock_worksheet_with_asin_on_reserved_row(row: int) -> Mock:
    # get_asin_list は「A列が10文字の文字列」というだけでASIN行を判定しており、
    # ASINが5行目以降にあることをコードとしては一切保証していない（実運用上の慣習に過ぎない）。
    # ここではその慣習が破られた場合に write_sales_nums / write_prices のガード
    # (`row > HEADER_ROW`) が実際に機能することを確かめるため、
    # あえてASINを予約行（1〜4行目のいずれか）に置く。
    col_values = ["filler1", "filler2", "filler3", "filler4"]
    col_values[row - 1] = "B00EXAMPLE"
    sales_ws = Mock()
    sales_ws.row_values.return_value = ["", "目標販売数", "", "", "自社価格"]
    sales_ws.col_values.return_value = col_values
    return sales_ws


class TestReservedRowGuard:
    def test_skips_writing_unit_count_when_asin_lands_on_row1(self) -> None:
        sales_ws = _create_mock_worksheet_with_asin_on_reserved_row(1)
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums(
            {"B00EXAMPLE": SalesInfo(unit_count=9, total_sales_amount=100.0)}
        )

        requests = sales_ws.batch_update.call_args_list[0][0][0]
        row1_requests = [r for r in requests if r["range"] == rowcol_to_a1(1, 3)]
        # ASINの個数書き込みがガードで抑止され、日付ラベルの1件だけが残る。
        assert len(row1_requests) == 1

    def test_skips_writing_unit_count_when_asin_lands_on_fetch_time_row(self) -> None:
        sales_ws = _create_mock_worksheet_with_asin_on_reserved_row(FETCH_TIME_ROW)
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums(
            {"B00EXAMPLE": SalesInfo(unit_count=9, total_sales_amount=100.0)}
        )

        requests = sales_ws.batch_update.call_args_list[0][0][0]
        row2_requests = [r for r in requests if r["range"] == rowcol_to_a1(FETCH_TIME_ROW, 3)]
        # ASINの個数書き込みがガードで抑止され、取得時刻の1件だけが残る。
        assert len(row2_requests) == 1
        assert re.fullmatch(r"\d{2}:\d{2}", row2_requests[0]["values"][0][0])

    def test_skips_writing_unit_count_when_asin_lands_on_total_amount_row(self) -> None:
        sales_ws = _create_mock_worksheet_with_asin_on_reserved_row(TOTAL_AMOUNT_ROW)
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums(
            {"B00EXAMPLE": SalesInfo(unit_count=9, total_sales_amount=100.0)}
        )

        requests = sales_ws.batch_update.call_args_list[0][0][0]
        row3_requests = [r for r in requests if r["range"] == rowcol_to_a1(TOTAL_AMOUNT_ROW, 3)]
        # ASINの個数書き込みがガードで抑止され、総売上の1件だけが残る。
        assert len(row3_requests) == 1
        assert row3_requests[0]["values"] == [[100.0]]

    def test_skips_writing_unit_count_when_asin_lands_on_header_row(self) -> None:
        sales_ws = _create_mock_worksheet_with_asin_on_reserved_row(HEADER_ROW)
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_sales_nums(
            {"B00EXAMPLE": SalesInfo(unit_count=9, total_sales_amount=100.0)}
        )

        requests = sales_ws.batch_update.call_args_list[0][0][0]
        row4_requests = [r for r in requests if r["range"] == rowcol_to_a1(HEADER_ROW, 3)]
        # ASINの個数書き込みがガードで抑止され、日付ラベル（行4）の1件だけが残る。
        assert len(row4_requests) == 1

    def test_write_prices_skips_note_and_color_when_asin_lands_on_reserved_row(self) -> None:
        # write_prices は write_sales_nums と同じ self._asin_to_rows を回すため、
        # 同じ罠（予約行にノート・背景色が付く）を踏みうる。write_sales_nums 側と
        # 同じガード(`row > HEADER_ROW`)が効いていることを直接確認する。
        sales_ws = _create_mock_worksheet_with_asin_on_reserved_row(TOTAL_AMOUNT_ROW)
        sales_ws.get_notes.return_value = [["2800"], ["2800"], ["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        batch_update_calls_before = sales_ws.batch_update.call_count
        sheet.write_prices({"B00EXAMPLE": 3000.0})

        # 予約行(行3)のASINは対象から除外され、価格書き込み自体が発生しない。
        assert sales_ws.batch_update.call_count == batch_update_calls_before
        sales_ws.update_notes.assert_not_called()
        sales_ws.spreadsheet.batch_update.assert_not_called()
        sales_ws.format.assert_not_called()


TARGET_DATE = date(2026, 9, 3)
GROSS_PROFIT_COLUMN = 3


def _create_mock_worksheet_for_gross_profit() -> Mock:
    # 4行目がヘッダー（A列=ASIN, B列=商品名, C列が対象日の日付列）。
    # 行5「ASIN行」の直後（行6）が粗利益行。B00EXAMPLF側は行8が粗利益行。
    sales_ws = Mock(spec=Worksheet)
    sales_ws.row_values.return_value = ["ASIN", "商品名", date_serial(TARGET_DATE)]
    col_a = ["", "", "", "ASIN", "B00EXAMPLE", "", "B00EXAMPLF", ""]
    col_name = [
        "", "", "", "商品名",
        "ルーペ", GROSS_PROFIT_ROW_LABEL,
        "ボール", GROSS_PROFIT_ROW_LABEL,
    ]
    sales_ws.col_values.side_effect = lambda col, **kwargs: (
        col_a if col == 1 else col_name
    )
    return sales_ws


class TestWriteGrossProfit:
    def test_writes_estimated_profit_to_resolved_date_column(self) -> None:
        sales_ws = _create_mock_worksheet_for_gross_profit()
        sheet = SalesSheet(sales_worksheet=sales_ws)

        result = sheet.write_gross_profit({"B00EXAMPLE": 1200.0}, TARGET_DATE)

        assert result.cells_written == 1
        requests = sales_ws.batch_update.call_args_list[0][0][0]
        assert requests == [
            {"range": rowcol_to_a1(6, GROSS_PROFIT_COLUMN), "values": [[1200.0]]}
        ]

    def test_does_not_touch_cell_for_asin_missing_from_profit_dict(self) -> None:
        sales_ws = _create_mock_worksheet_for_gross_profit()
        sheet = SalesSheet(sales_worksheet=sales_ws)

        sheet.write_gross_profit({"B00EXAMPLE": 1200.0}, TARGET_DATE)

        requests = sales_ws.batch_update.call_args_list[0][0][0]
        written_ranges = {r["range"] for r in requests}
        assert rowcol_to_a1(8, GROSS_PROFIT_COLUMN) not in written_ranges

    def test_applies_light_yellow_background_only_to_written_cells(self) -> None:
        sales_ws = _create_mock_worksheet_for_gross_profit()
        sheet = SalesSheet(sales_worksheet=sales_ws)

        sheet.write_gross_profit({"B00EXAMPLE": 1200.0}, TARGET_DATE)

        sales_ws.format.assert_called_once_with(
            [rowcol_to_a1(6, GROSS_PROFIT_COLUMN)],
            {
                "backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.8},
                "numberFormat": {"type": "NUMBER", "pattern": "#,##0.0,"},
            },
        )

    def test_applies_k_number_format_alongside_the_background(self) -> None:
        # 千円単位・小数点1桁（1,240 -> "1.2"）。整数だと1日あたり数百円の
        # 広告費が 0 に潰れて見えなくなる。単位の文字は付けない
        sales_ws = _create_mock_worksheet_for_gross_profit()
        sheet = SalesSheet(sales_worksheet=sales_ws)

        sheet.write_gross_profit({"B00EXAMPLE": 1200.0}, TARGET_DATE)

        applied_format = sales_ws.format.call_args[0][1]
        assert applied_format["numberFormat"] == {"type": "NUMBER", "pattern": "#,##0.0,"}

    def test_format_range_has_no_sheet_name_after_batch_update_mutates_requests(
        self,
    ) -> None:
        # 実運用の gspread.Worksheet.batch_update は渡した dict の "range" を
        # in-place で "'売上/日'!CS9" のようなシート名付きに書き換える。この
        # side_effect でそれを再現し、format() に渡る範囲がその汚染を受けない
        # ことを確認する。
        def _prefixing_batch_update(requests: list[dict], **kwargs: object) -> None:
            for request in requests:
                request["range"] = f"'売上/日'!{request['range']}"

        sales_ws = _create_mock_worksheet_for_gross_profit()
        sales_ws.batch_update.side_effect = _prefixing_batch_update
        sheet = SalesSheet(sales_worksheet=sales_ws)

        sheet.write_gross_profit({"B00EXAMPLE": 1200.0}, TARGET_DATE)

        formatted_ranges = sales_ws.format.call_args[0][0]
        assert formatted_ranges == [rowcol_to_a1(6, GROSS_PROFIT_COLUMN)]
        assert all("!" not in cell for cell in formatted_ranges)

    def test_raises_when_date_column_missing(self) -> None:
        # 黙って0件を返すと launchd の失敗通知が鳴らず、粗利益が空のまま
        # 何週間も気づかれない。日付列は直前の write_sales_nums が作るので、
        # 無いこと自体が異常
        sales_ws = _create_mock_worksheet_for_gross_profit()
        sheet = SalesSheet(sales_worksheet=sales_ws)

        with pytest.raises(GrossProfitRowsNotFoundError):
            sheet.write_gross_profit({"B00EXAMPLE": 1200.0}, date(2099, 1, 1))

        sales_ws.batch_update.assert_not_called()
        sales_ws.format.assert_not_called()

    def test_returns_empty_result_without_raising_when_no_profit_to_write(self) -> None:
        # 全 ASIN で原価が欠けている日は書くものが無いだけで異常ではない
        sales_ws = _create_mock_worksheet_for_gross_profit()
        sheet = SalesSheet(sales_worksheet=sales_ws)

        result = sheet.write_gross_profit({}, TARGET_DATE)

        assert result.cells_written == 0
        sales_ws.batch_update.assert_not_called()

    def test_reports_asins_that_have_no_gross_profit_row(self) -> None:
        # 新商品の行が3行しか入っていない等でラベル行が欠けた場合、
        # 書けた分は書きつつ、書けなかった ASIN を呼び出し元へ返す
        sales_ws = _create_mock_worksheet_for_gross_profit()
        sheet = SalesSheet(sales_worksheet=sales_ws)

        result = sheet.write_gross_profit(
            {"B00EXAMPLE": 1200.0, "B00NOROW999": 800.0}, TARGET_DATE
        )

        assert result.cells_written == 1
        assert result.asins_without_row == ("B00NOROW999",)

    def test_skips_writing_when_asin_lands_on_reserved_row(self) -> None:
        sales_ws = _create_mock_worksheet_for_gross_profit()
        # ASIN行(行3)の直後、予約行である行4(=HEADER_ROW)に粗利益ラベルが来ても
        # 書き込まれないことを確認する。
        col_a = ["", "", "B00EXAMPLE", ""]
        col_name = ["", "", "", GROSS_PROFIT_ROW_LABEL]
        sales_ws.col_values.side_effect = lambda col, **kwargs: (
            col_a if col == 1 else col_name
        )
        sheet = SalesSheet(sales_worksheet=sales_ws)

        with pytest.raises(GrossProfitRowsNotFoundError):
            sheet.write_gross_profit({"B00EXAMPLE": 1200.0}, TARGET_DATE)

        sales_ws.batch_update.assert_not_called()

    def test_none_profit_blanks_the_cell_and_gets_no_yellow(self) -> None:
        # 原価が #REF! になった等で計算できなくなった日は、前回の見積を
        # 残さず空にする。黄色のまま残ると最新の数字のように見える
        sales_ws = _create_mock_worksheet_for_gross_profit()
        sheet = SalesSheet(sales_worksheet=sales_ws)

        result = sheet.write_gross_profit({"B00EXAMPLE": None}, TARGET_DATE)

        assert result.cells_written == 1
        requests = sales_ws.batch_update.call_args_list[0][0][0]
        assert requests[0]["values"] == [[""]]
        sales_ws.format.assert_not_called()
