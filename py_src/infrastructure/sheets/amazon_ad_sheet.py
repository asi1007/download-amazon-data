from __future__ import annotations
from gspread import Worksheet

PERIOD_START_COL = 1
ASIN_COL = 3
AD_SPEND_COL = 4


class AmazonAdSheet:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet

    def get_ad_spend_by_period_start(self, period_start: str) -> dict[str, float]:
        all_values = self._worksheet.get_all_values()
        if len(all_values) <= 1:
            return {}
        result: dict[str, float] = {}
        for row in all_values[1:]:
            if len(row) <= AD_SPEND_COL:
                continue
            if row[PERIOD_START_COL] != period_start:
                continue
            asin = row[ASIN_COL]
            if not asin:
                continue
            result[asin] = float(row[AD_SPEND_COL]) if row[AD_SPEND_COL] else 0.0
        return result
