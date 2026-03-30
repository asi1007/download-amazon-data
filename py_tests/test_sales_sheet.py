from unittest.mock import Mock
from gspread.utils import rowcol_to_a1
from py_src.infrastructure.sheets.sales_sheet import SalesSheet
from py_src.domain.value_objects.sales_info import SalesInfo


def _create_mock_worksheets() -> tuple[Mock, Mock]:
    settings_ws = Mock()
    settings_ws.acell.side_effect = lambda cell: Mock(value="3" if cell == "B2" else "2")

    sales_ws = Mock()
    sales_ws.col_values.return_value = [
        "header", "B00EXAMPLE", "B00EXAMPLF", "", "header2", "B00EXAMPLG",
    ]
    return sales_ws, settings_ws


class TestSalesSheet:
    def test_get_asin_list(self) -> None:
        sales_ws, settings_ws = _create_mock_worksheets()
        sheet = SalesSheet(sales_worksheet=sales_ws, settings_worksheet=settings_ws)
        asin_list = sheet.get_asin_list()
        assert asin_list == ["B00EXAMPLE", "B00EXAMPLF", "B00EXAMPLG"]

    def test_write_sales_nums_total_amount_to_row3(self) -> None:
        sales_ws, settings_ws = _create_mock_worksheets()
        sheet = SalesSheet(sales_worksheet=sales_ws, settings_worksheet=settings_ws)
        sheet.get_asin_list()

        asin_sales = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
            "B00EXAMPLF": SalesInfo(unit_count=1, total_sales_amount=3000.0, order_count=1),
            "B00EXAMPLG": SalesInfo(unit_count=3, total_sales_amount=4500.0, order_count=2),
        }
        sheet.write_sales_nums(asin_sales)

        sales_ws.insert_cols.assert_called_once_with(3)
        row3_range = rowcol_to_a1(3, 3)
        update_calls = sales_ws.update.call_args_list
        row3_call = [c for c in update_calls if c[0][0] == row3_range]
        assert len(row3_call) == 1
        assert row3_call[0][0][1] == [[13500.0]]

    def test_write_sales_nums_missing_asin_uses_default(self) -> None:
        sales_ws, settings_ws = _create_mock_worksheets()
        sheet = SalesSheet(sales_worksheet=sales_ws, settings_worksheet=settings_ws)
        sheet.get_asin_list()

        asin_sales = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
        }
        sheet.write_sales_nums(asin_sales)

        row3_range = rowcol_to_a1(3, 3)
        update_calls = sales_ws.update.call_args_list
        row3_call = [c for c in update_calls if c[0][0] == row3_range]
        assert row3_call[0][0][1] == [[6000.0]]

    def test_write_prices_updates_cells(self) -> None:
        sales_ws, settings_ws = _create_mock_worksheets()
        sales_ws.cell.return_value = Mock(value="2800")
        sheet = SalesSheet(sales_worksheet=sales_ws, settings_worksheet=settings_ws)
        sheet.get_asin_list()

        prices = {"B00EXAMPLE": 3000.0}
        sheet.write_prices(prices)

        sales_ws.update_cell.assert_called()


class TestGetSellingPrices:
    def test_returns_asin_to_price_map(self) -> None:
        sales_ws = Mock()
        settings_ws = Mock()
        settings_ws.acell.side_effect = lambda cell: Mock(value="3" if cell == "B2" else "5")
        sales_ws.col_values.return_value = [
            "header", "header2", "header3", "header4",
            "B00EXAMPLE", "B00EXAMPLF", "B00EXAMPLG",
        ]
        sales_ws.get.return_value = [
            ["header"], ["header2"], ["header3"], ["header4"],
            ["500"], ["800"], [""],
        ]
        sheet = SalesSheet(sales_worksheet=sales_ws, settings_worksheet=settings_ws)
        sheet.get_asin_list()
        prices = sheet.get_selling_prices()
        assert prices == {"B00EXAMPLE": 500.0, "B00EXAMPLF": 800.0}

    def test_returns_empty_when_no_asins(self) -> None:
        sales_ws = Mock()
        settings_ws = Mock()
        settings_ws.acell.side_effect = lambda cell: Mock(value="3" if cell == "B2" else "5")
        sales_ws.col_values.return_value = ["header"]
        sheet = SalesSheet(sales_worksheet=sales_ws, settings_worksheet=settings_ws)
        sheet.get_asin_list()
        prices = sheet.get_selling_prices()
        assert prices == {}
