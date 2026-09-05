from unittest.mock import Mock

from gspread import Worksheet

from py_src.infrastructure.sheets.product_index_reader import ProductIndexReader

HEADER = ["ASIN", "商品名", "SKU", "販売手数料", "FBA手数料", "原価"]


def _worksheet(rows: list[list[str]]) -> Mock:
    worksheet = Mock(spec=Worksheet)
    worksheet.row_values.return_value = HEADER
    worksheet.get.return_value = [[], [], [], HEADER] + rows
    return worksheet


class TestProductIndexReader:
    def test_reads_costs_names_and_sku_mapping_in_one_pass(self) -> None:
        index = ProductIndexReader(_worksheet([
            ["B00EXAMPLE", "ルーペ", "SKU-A", "100", "300", "200"],
            ["", "広告経由", "", "", "", ""],
        ])).read()

        assert index.names == {"B00EXAMPLE": "ルーペ"}
        assert index.sku_to_asin == {"SKU-A": "B00EXAMPLE"}
        assert index.costs["B00EXAMPLE"].total_per_unit == 600.0

    def test_two_skus_on_the_same_asin_both_map_back(self) -> None:
        # Finances は SellerSKU しか返さない。ASIN を鍵にすると片方が落ちる
        index = ProductIndexReader(_worksheet([
            ["B0FBSCPJJH", "ボールネット", "SKU-NET", "38.5", "252", "168"],
            ["B0FBSCPJJH", "ボールバッグ", "SKU-BAG", "", "", "168"],
        ])).read()

        assert index.sku_to_asin == {"SKU-NET": "B0FBSCPJJH", "SKU-BAG": "B0FBSCPJJH"}
        assert index.costs["B0FBSCPJJH"].selling_fee == 38.5
        assert index.names["B0FBSCPJJH"] == "ボールネット"

    def test_reads_the_grid_only_once(self) -> None:
        # 3つのリーダーがそれぞれ全グリッドを読むと毎時のジョブで無駄が出る
        worksheet = _worksheet([["B00EXAMPLE", "ルーペ", "SKU-A", "1", "2", "3"]])

        ProductIndexReader(worksheet).read()

        assert worksheet.get.call_count == 1
