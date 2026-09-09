from __future__ import annotations

import time
from typing import Any

from py_src.domain.value_objects.category_rank import (
    ASIN_PATTERN,
    CategoryRank,
    pick_rank,
)
from py_src.infrastructure.api.sp_api_authenticator import SP_API_BASE, SpApiAuthenticator

MARKETPLACE_JP = "A1VC38T7YXB528"
# catalog items は1リクエストにつき識別子20件まで
BATCH_SIZE = 20
INCLUDED_DATA = "summaries,salesRanks"
PAUSE_SECONDS = 2


class SpApiCatalog:
    def __init__(
        self,
        authenticator: SpApiAuthenticator,
        pause_seconds: float = PAUSE_SECONDS,
    ) -> None:
        self._auth = authenticator
        self._pause_seconds = pause_seconds

    def fetch(self, asins: list[str]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for start in range(0, len(asins), BATCH_SIZE):
            if start > 0:
                time.sleep(self._pause_seconds)
            batch = asins[start:start + BATCH_SIZE]
            response = self._auth.request("GET", self._items_url(batch))
            items.extend(response.json().get("items", []))
        return items

    @staticmethod
    def _items_url(asins: list[str]) -> str:
        return (
            f"{SP_API_BASE}/catalog/2022-04-01/items"
            f"?identifiers={','.join(asins)}"
            f"&identifiersType=ASIN"
            f"&marketplaceIds={MARKETPLACE_JP}"
            f"&includedData={INCLUDED_DATA}"
            f"&pageSize={BATCH_SIZE}"
        )


def to_ranks(
    items: list[dict[str, Any]], known_categories: dict[str, str]
) -> dict[str, CategoryRank]:
    ranks: dict[str, CategoryRank] = {}
    for item in items:
        asin = str(item.get("asin", ""))
        if not ASIN_PATTERN.match(asin):
            continue
        ranks[asin] = pick_rank(
            asin, item.get("salesRanks") or [], known_categories.get(asin)
        )
    return ranks
