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

        sales_ws.insert_cols.assert_called_once_with([[""]], 3)
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

        sales_ws.format.assert_called_once_with(
            [rowcol_to_a1(1, 3), rowcol_to_a1(4, 3)],
            {"numberFormat": {"type": "DATE", "pattern": "dd"}},
        )

    def test_write_prices_updates_cells(self) -> None:
        sales_ws = _create_mock_worksheet()
        sales_ws.get.return_value = [["2800"], ["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        prices = {"B00EXAMPLE": 3000.0}
        sheet.write_prices(prices)

        sales_ws.batch_update.assert_called()


class TestWritePricesQuota:
    def test_does_not_call_per_asin_write_apis(self) -> None:
        sales_ws = _create_mock_worksheet()
        sales_ws.get.return_value = [["2800"], ["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_prices({"B00EXAMPLE": 3000.0, "B00EXAMPLF": 2000.0, "B00EXAMPLG": 2800.0})

        sales_ws.update_cell.assert_not_called()
        sales_ws.update_note.assert_not_called()
        sales_ws.cell.assert_not_called()

    def test_write_calls_stay_constant_as_asins_grow(self) -> None:
        def count_write_calls(asin_count: int) -> int:
            sales_ws = Mock()
            sales_ws.row_values.return_value = ["", "目標販売数", "", "", "自社価格"]
            asins = [f"B00EXAMPL{i:02d}" for i in range(asin_count)]
            sales_ws.col_values.return_value = ["header", *asins]
            sales_ws.get.return_value = [["2800"] for _ in range(asin_count + 1)]
            sheet = SalesSheet(sales_worksheet=sales_ws)
            sheet.get_asin_list()
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
        sales_ws.get.return_value = [["2800"], ["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_prices({"B00EXAMPLE": 3000.0, "B00EXAMPLF": 2000.0})

        assert len(sales_ws.update_notes.call_args_list) == 1
        notes = sales_ws.update_notes.call_args_list[0][0][0]
        assert set(notes.values()) == {"3000.0", "2000.0"}

    def test_colors_cheaper_and_pricier_cells_in_two_calls(self) -> None:
        sales_ws = _create_mock_worksheet()
        sales_ws.get.return_value = [["2800"], ["2800"], ["2800"]]
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_prices(
            {"B00EXAMPLE": 2000.0, "B00EXAMPLF": 3000.0, "B00EXAMPLG": 2800.0}
        )

        assert len(sales_ws.format.call_args_list) <= 2

    def test_skips_all_writes_when_no_matching_asin(self) -> None:
        sales_ws = _create_mock_worksheet()
        sheet = SalesSheet(sales_worksheet=sales_ws)
        sheet.get_asin_list()

        sheet.write_prices({"UNKNOWN": 3000.0})

        sales_ws.batch_update.assert_not_called()
        sales_ws.update_notes.assert_not_called()


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
