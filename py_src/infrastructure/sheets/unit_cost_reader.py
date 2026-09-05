from __future__ import annotations

from gspread import Worksheet

from py_src.domain.value_objects.unit_costs import UnitCosts
from py_src.infrastructure.sheets.product_index_reader import ProductIndexReader


class UnitCostReader:
    def __init__(self, worksheet: Worksheet) -> None:
        self._reader = ProductIndexReader(worksheet)

    def read(self) -> dict[str, UnitCosts]:
        return self._reader.read().costs
