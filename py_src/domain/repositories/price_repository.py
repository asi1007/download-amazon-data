from __future__ import annotations
from typing import Protocol


class PriceRepository(Protocol):
    def get_competitive_prices(self, asins: list[str]) -> dict[str, float]: ...
