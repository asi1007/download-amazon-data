from __future__ import annotations

from gspread import Worksheet

from py_src.domain.value_objects.unit_costs import UnitCosts
from py_src.infrastructure.sheets.label_rows import (
    ASIN_COLUMN,
    ASIN_LENGTH,
    HEADER_ROW,
    find_column,
)

SELLING_FEE_HEADER = "販売手数料"
FBA_FEE_HEADER = "FBA手数料"
COST_HEADER = "原価"


class UnitCostReader:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet

    def read(self) -> dict[str, UnitCosts]:
        headers = self._worksheet.row_values(HEADER_ROW)
        selling_fee_column = find_column(headers, SELLING_FEE_HEADER)
        fba_fee_column = find_column(headers, FBA_FEE_HEADER)
        cost_column = find_column(headers, COST_HEADER)

        # 同じ ASIN が複数行にあるとき（同一商品を2回登録している行が実在する）、
        # 素朴な dict 内包表記は最後の行で上書きする。実データでは片方の行にだけ
        # 手数料が入っており、空の行が勝って粗利益が丸ごと書かれていなかった。
        # 3つとも揃っている行を優先する
        costs: dict[str, UnitCosts] = {}
        for row in self._worksheet.get():
            asin = self._asin_of(row)
            if not asin:
                continue
            candidate = UnitCosts(
                selling_fee=self._parse_amount(row, selling_fee_column),
                fba_fee=self._parse_amount(row, fba_fee_column),
                cost=self._parse_amount(row, cost_column),
            )
            existing = costs.get(asin)
            if existing is not None and existing.total_per_unit is not None:
                continue
            costs[asin] = candidate
        return costs

    @staticmethod
    def _asin_of(row: list[str]) -> str:
        if len(row) < ASIN_COLUMN:
            return ""
        candidate = row[ASIN_COLUMN - 1].strip()
        return candidate if len(candidate) == ASIN_LENGTH else ""

    @staticmethod
    def _parse_amount(row: list[str], column: int) -> float | None:
        if len(row) < column:
            return None
        cleaned = row[column - 1].replace("¥", "").replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
