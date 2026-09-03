from unittest.mock import Mock
from gspread.utils import rowcol_to_a1
from py_src.infrastructure.sheets.sales_sheet import SalesSheet
from py_src.domain.value_objects.sales_info import SalesInfo


def _create_mock_worksheet() -> Mock:
    sales_ws = Mock()
    sales_ws.row_values.return_value = ["", "目標販売数", "", "", "自社価格"]
    sales_ws.col_values.return_value = [
        "header", "B00EXAMPLE", "B00EXAMPLF", "", "header2", "B00EXAMPLG",
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
        assert rowcol_to_a1(2, 3) in written_ranges
        assert rowcol_to_a1(6, 3) not in written_ranges

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
        sales_ws.get.return_value = [[""], ["3"], ["1"]]
        sales_ws.get_notes.return_value = [[""], ["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        sheet.write_prices({"B00EXAMPLE": 2000.0, "B00EXAMPLF": 3500.0})

        assert _colored_cells(sales_ws, CHEAPER_COLOR) == {rowcol_to_a1(2, 3)}
        assert _colored_cells(sales_ws, PRICIER_COLOR) == {rowcol_to_a1(3, 3)}

    def test_ignores_previous_day_cell_value(self) -> None:
        sales_ws = _create_mock_worksheet()
        sales_ws.get.return_value = [[""], ["3"], ["1"]]
        sales_ws.get_notes.return_value = [[""], [""], [""]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        sheet.write_prices({"B00EXAMPLE": 2000.0, "B00EXAMPLF": 3500.0})

        assert _colored_cells(sales_ws, CHEAPER_COLOR) == set()
        assert _colored_cells(sales_ws, PRICIER_COLOR) == set()

    def test_clears_background_of_cells_without_price_change(self) -> None:
        sales_ws = _create_mock_worksheet()
        sales_ws.get_notes.return_value = [[""], ["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        sheet.write_prices({"B00EXAMPLE": 2800.0, "B00EXAMPLF": 3500.0})

        cleared = _cleared_background_ranges(sales_ws)
        assert rowcol_to_a1(2, 3) in cleared
        assert rowcol_to_a1(3, 3) in cleared

    def test_clears_background_before_applying_new_color(self) -> None:
        sales_ws = _create_mock_worksheet()
        sales_ws.get_notes.return_value = [[""], ["2800"], ["2800"]]
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
            sales_ws = Mock()
            sales_ws.row_values.return_value = ["", "目標販売数", "", "", "自社価格"]
            asins = [f"B00EXAM{i:03d}" for i in range(asin_count)]
            sales_ws.col_values.return_value = ["header", *asins]
            sales_ws.get_notes.return_value = [["2800"] for _ in range(asin_count + 1)]
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
    sales_ws = Mock()
    sales_ws.row_values.return_value = ["", "目標販売数", "", "", "自社価格"]
    sales_ws.col_values.return_value = [
        "header", "B00EXAMPLE", "合計", "B00EXAMPLE", "B00EXAMPLF",
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
        assert written[rowcol_to_a1(2, 3)] == [[4]]
        assert written[rowcol_to_a1(4, 3)] == [[4]]

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
        sales_ws.get_notes.return_value = [["2800"], ["2800"], ["2800"], ["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()
        sheet.write_sales_nums({})

        sheet.write_prices({"B00EXAMPLE": 3000.0})

        requests = sales_ws.batch_update.call_args_list[-1][0][0]
        written_ranges = {r["range"] for r in requests}
        assert rowcol_to_a1(2, 5) in written_ranges
        assert rowcol_to_a1(4, 5) in written_ranges

    def test_get_selling_prices_reads_duplicated_asin_once(self) -> None:
        sales_ws = _create_mock_worksheet_with_duplicates()
        sales_ws.get.return_value = [["header"], ["500"], ["合計"], ["500"], ["800"]]
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
