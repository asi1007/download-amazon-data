from __future__ import annotations
from dataclasses import dataclass, field

from gspread import Worksheet

from py_src.domain.value_objects.unit_costs import UnitCosts
from py_src.infrastructure.sheets.label_rows import (
    ASIN_COLUMN,
    ASIN_LENGTH,
    HEADER_ROW,
    PRODUCT_NAME_HEADER,
    find_column,
)

SKU_HEADER = "SKU"
SELLING_FEE_HEADER = "販売手数料"
FBA_FEE_HEADER = "FBA手数料"
COST_HEADER = "原価"


@dataclass(frozen=True)
class ProductIndex:
    costs: dict[str, UnitCosts] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)
    sku_to_asin: dict[str, str] = field(default_factory=dict)


class ProductIndexReader:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet

    def read(self) -> ProductIndex:
        headers = self._worksheet.row_values(HEADER_ROW)
        columns = {
            "sku": find_column(headers, SKU_HEADER),
            "name": find_column(headers, PRODUCT_NAME_HEADER),
            "selling_fee": find_column(headers, SELLING_FEE_HEADER),
            "fba_fee": find_column(headers, FBA_FEE_HEADER),
            "cost": find_column(headers, COST_HEADER),
        }
        costs: dict[str, UnitCosts] = {}
        names: dict[str, str] = {}
        sku_to_asin: dict[str, str] = {}
        for row in self._worksheet.get():
            asin = self._asin_of(row)
            if not asin:
                continue
            # 同じ ASIN が複数行にあるとき、素朴な代入は最後の行で上書きする。
            # 実データでは片方の行にだけ手数料が入っており、空の行が勝って
            # 粗利益が丸ごと書かれていなかった。3つとも揃っている行を優先する
            candidate = UnitCosts(
                selling_fee=self._amount(row, columns["selling_fee"]),
                fba_fee=self._amount(row, columns["fba_fee"]),
                cost=self._amount(row, columns["cost"]),
            )
            existing = costs.get(asin)
            if existing is None or existing.total_per_unit is None:
                costs[asin] = candidate
            if not names.get(asin):
                names[asin] = self._text(row, columns["name"])
            # SKU は行ごとに違うことがある（同一 ASIN の2行に別 SKU）。
            # Finances は SellerSKU しか返さないので SKU 側を鍵にする
            sku = self._text(row, columns["sku"])
            if sku:
                sku_to_asin[sku] = asin
        return ProductIndex(costs=costs, names=names, sku_to_asin=sku_to_asin)

    @staticmethod
    def _asin_of(row: list[str]) -> str:
        if len(row) < ASIN_COLUMN:
            return ""
        candidate = row[ASIN_COLUMN - 1].strip()
        return candidate if len(candidate) == ASIN_LENGTH else ""

    @staticmethod
    def _text(row: list[str], column: int) -> str:
        if len(row) < column:
            return ""
        return row[column - 1].strip()

    @classmethod
    def _amount(cls, row: list[str], column: int) -> float | None:
        cleaned = cls._text(row, column).replace("¥", "").replace(",", "")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
