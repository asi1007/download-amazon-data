from unittest.mock import Mock

from gspread import Worksheet

from py_src.infrastructure.sheets.sku_asin_reader import SkuAsinReader

HEADER = ["ASIN", "SKU", "商品名"]


def _worksheet(rows: list[list[str]]) -> Mock:
    worksheet = Mock(spec=Worksheet)
    worksheet.row_values.return_value = HEADER
    worksheet.get.return_value = [[], [], [], HEADER] + rows
    return worksheet


class TestSkuAsinReader:
    def test_maps_each_sku_to_its_asin(self) -> None:
        reader = SkuAsinReader(_worksheet([
            ["B00EXAMPLE", "SKU-A", "ルーペ"],
            ["B00EXAMPLF", "SKU-B", "ボール"],
        ]))

        assert reader.read() == {"SKU-A": "B00EXAMPLE", "SKU-B": "B00EXAMPLF"}

    def test_ignores_label_rows_and_rows_without_a_sku(self) -> None:
        reader = SkuAsinReader(_worksheet([
            ["B00EXAMPLE", "SKU-A", "ルーペ"],
            ["", "", "広告経由"],
            ["B00EXAMPLF", "", "ボール"],
        ]))

        assert reader.read() == {"SKU-A": "B00EXAMPLE"}

    def test_same_asin_on_two_rows_contributes_both_skus(self) -> None:
        # 同じ ASIN が複数行にあり、行ごとに別の SKU が振られていることがある
        reader = SkuAsinReader(_worksheet([
            ["B0FBSCPJJH", "SKU-NET", "ボールネット"],
            ["B0FBSCPJJH", "SKU-BAG", "ボールバッグ"],
        ]))

        assert reader.read() == {"SKU-NET": "B0FBSCPJJH", "SKU-BAG": "B0FBSCPJJH"}
