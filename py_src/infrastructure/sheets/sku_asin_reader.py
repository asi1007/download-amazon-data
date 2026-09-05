from __future__ import annotations

from gspread import Worksheet

from py_src.infrastructure.sheets.label_rows import (
    ASIN_COLUMN,
    ASIN_LENGTH,
    HEADER_ROW,
    find_column,
)

SKU_HEADER = "SKU"


class SkuAsinReader:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet

    def read(self) -> dict[str, str]:
        # Finances は SellerSKU しか返さないため、ASIN へ引き直す辞書が要る。
        # 同じ ASIN が複数行にあり行ごとに別 SKU が振られていることがあるので、
        # SKU を鍵にする（ASIN を鍵にすると片方が落ちる）
        sku_column = find_column(self._worksheet.row_values(HEADER_ROW), SKU_HEADER)
        mapping: dict[str, str] = {}
        for row in self._worksheet.get():
            asin = self._asin_of(row)
            sku = self._sku_of(row, sku_column)
            if asin and sku:
                mapping[sku] = asin
        return mapping

    @staticmethod
    def _asin_of(row: list[str]) -> str:
        if len(row) < ASIN_COLUMN:
            return ""
        candidate = row[ASIN_COLUMN - 1].strip()
        return candidate if len(candidate) == ASIN_LENGTH else ""

    @staticmethod
    def _sku_of(row: list[str], column: int) -> str:
        if len(row) < column:
            return ""
        return row[column - 1].strip()
