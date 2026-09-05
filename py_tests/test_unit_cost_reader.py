from unittest.mock import Mock

from gspread import Worksheet

from py_src.domain.value_objects.unit_costs import UnitCosts
from py_src.infrastructure.sheets.unit_cost_reader import UnitCostReader


def _worksheet() -> Mock:
    worksheet = Mock(spec=Worksheet)
    worksheet.row_values.return_value = ["ASIN", "商品名", "販売手数料", "FBA手数料", "原価"]
    worksheet.get.return_value = [
        ["ASIN", "商品名", "販売手数料", "FBA手数料", "原価"],
        ["B00EXAMPLE", "ルーペ", "100", "300", "200"],
        ["", "広告経由", "", "", ""],
        ["B00EXAMPLF", "ボール", "", "250", "180"],
    ]
    return worksheet


class TestUnitCostReader:
    def test_reads_per_unit_costs_by_asin(self) -> None:
        costs = UnitCostReader(_worksheet()).read()

        assert costs["B00EXAMPLE"] == UnitCosts(
            selling_fee=100.0, fba_fee=300.0, cost=200.0
        )

    def test_missing_value_becomes_none(self) -> None:
        costs = UnitCostReader(_worksheet()).read()

        assert costs["B00EXAMPLF"].selling_fee is None
        assert costs["B00EXAMPLF"].fba_fee == 250.0

    def test_ignores_non_asin_rows(self) -> None:
        costs = UnitCostReader(_worksheet()).read()

        assert set(costs) == {"B00EXAMPLE", "B00EXAMPLF"}

    def test_strips_currency_formatting(self) -> None:
        worksheet = _worksheet()
        worksheet.get.return_value = [
            ["ASIN", "商品名", "販売手数料", "FBA手数料", "原価"],
            ["B00EXAMPLE", "ルーペ", "¥1,100", "300", "200"],
        ]

        assert UnitCostReader(worksheet).read()["B00EXAMPLE"].selling_fee == 1100.0


class TestMalformedCells:
    def test_ref_error_cell_becomes_none_without_raising(self) -> None:
        worksheet = _worksheet()
        worksheet.get.return_value = [
            ["ASIN", "商品名", "販売手数料", "FBA手数料", "原価"],
            ["B00EXAMPLE", "ルーペ", "100", "300", "#REF!"],
        ]

        costs = UnitCostReader(worksheet).read()

        assert costs["B00EXAMPLE"].cost is None

    def test_div_error_cell_becomes_none_without_raising(self) -> None:
        worksheet = _worksheet()
        worksheet.get.return_value = [
            ["ASIN", "商品名", "販売手数料", "FBA手数料", "原価"],
            ["B00EXAMPLE", "ルーペ", "#DIV/0!", "300", "200"],
        ]

        costs = UnitCostReader(worksheet).read()

        assert costs["B00EXAMPLE"].selling_fee is None

    def test_other_asins_still_read_correctly_when_one_row_is_malformed(self) -> None:
        worksheet = _worksheet()
        worksheet.get.return_value = [
            ["ASIN", "商品名", "販売手数料", "FBA手数料", "原価"],
            ["B00EXAMPLE", "ルーペ", "100", "300", "#REF!"],
            ["B00EXAMPLF", "ボール", "50", "250", "180"],
        ]

        costs = UnitCostReader(worksheet).read()

        assert costs["B00EXAMPLE"].cost is None
        assert costs["B00EXAMPLF"] == UnitCosts(
            selling_fee=50.0, fba_fee=250.0, cost=180.0
        )
