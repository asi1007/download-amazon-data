import pytest
from unittest.mock import Mock, call
from py_src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet
from py_src.domain.value_objects.realtime_sales_result import RealtimeSalesResult


class TestRealtimeSalesSheet:
    def _make_worksheet(self, header: list[str], col_a: list[str]) -> Mock:
        mock_worksheet = Mock()
        mock_worksheet.row_values.return_value = header
        mock_worksheet.col_values.return_value = col_a
        return mock_worksheet

    def test_get_asin_list(self) -> None:
        ws = self._make_worksheet(
            ["ASIN", "個数", "売上"],
            ["ASIN", "B00EXAMPLE", "B00EXAMPLF", "B00EXAMPLG"],
        )
        sheet = RealtimeSalesSheet(worksheet=ws)
        asin_list = sheet.get_asin_list()

        assert asin_list == ["B00EXAMPLE", "B00EXAMPLF", "B00EXAMPLG"]

    def test_get_asin_list_filters_empty(self) -> None:
        ws = self._make_worksheet(
            ["ASIN", "個数", "売上"],
            ["ASIN", "B00EXAMPLE", "", " ", "B00EXAMPLF"],
        )
        sheet = RealtimeSalesSheet(worksheet=ws)
        asin_list = sheet.get_asin_list()

        assert asin_list == ["B00EXAMPLE", "B00EXAMPLF"]

    def test_write_realtime_sales(self) -> None:
        ws = self._make_worksheet(
            ["ASIN", "個数", "売上"],
            ["ASIN", "B00EXAMPLE", "B00EXAMPLF"],
        )
        sheet = RealtimeSalesSheet(worksheet=ws)
        sheet.get_asin_list()

        sales_map: dict[str, RealtimeSalesResult] = {
            "B00EXAMPLE": RealtimeSalesResult(asin="B00EXAMPLE", unit_count=5, total_amount=10000.0),
        }
        sheet.write_realtime_sales(sales_map)

        ws.update.assert_any_call("B2", [[5], [0]])
        ws.update.assert_any_call("C2", [[10000.0], [0.0]])

    def test_write_to_non_adjacent_columns(self) -> None:
        ws = self._make_worksheet(
            ["ASIN", "商品名", "個数", "単価", "売上"],
            ["ASIN", "B00EXAMPLE"],
        )
        sheet = RealtimeSalesSheet(worksheet=ws)
        sheet.get_asin_list()

        sales_map: dict[str, RealtimeSalesResult] = {
            "B00EXAMPLE": RealtimeSalesResult(asin="B00EXAMPLE", unit_count=3, total_amount=6000.0),
        }
        sheet.write_realtime_sales(sales_map)

        ws.update.assert_any_call("C2", [[3]])
        ws.update.assert_any_call("E2", [[6000.0]])

    def test_missing_header_raises(self) -> None:
        ws = self._make_worksheet(
            ["ASIN", "商品名"],
            ["ASIN", "B00EXAMPLE"],
        )
        sheet = RealtimeSalesSheet(worksheet=ws)

        with pytest.raises(ValueError, match="個数"):
            sheet.get_asin_list()
