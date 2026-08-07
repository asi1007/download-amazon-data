from __future__ import annotations
import time
from urllib.parse import urlencode
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator, SP_API_BASE
from py_src.domain.value_objects.inventory_summary import InventorySummary

MARKETPLACE_JP = "A1VC38T7YXB528"


class SpApiInventoryRepository:
    def __init__(self, authenticator: SpApiAuthenticator) -> None:
        self._auth = authenticator

    def get_all_summaries(self, start_date_time: str | None = None) -> list[InventorySummary]:
        base_params = {
            "marketplaceIds": MARKETPLACE_JP,
            "granularityType": "Marketplace",
            "granularityId": MARKETPLACE_JP,
            "details": "true",
        }
        if start_date_time:
            base_params["startDateTime"] = start_date_time

        summaries: list[InventorySummary] = []
        next_token: str | None = None
        while True:
            params = dict(base_params)
            if next_token:
                params["nextToken"] = next_token
            url = f"{SP_API_BASE}/fba/inventory/v1/summaries?{urlencode(params)}"
            response = self._auth.request("GET", url)
            data = response.json()
            payload = data.get("payload") or {}
            items = payload.get("inventorySummaries") or []
            summaries.extend(InventorySummary.from_api_payload(item) for item in items)
            next_token = (data.get("pagination") or {}).get("nextToken")
            if not next_token:
                break
            time.sleep(2)
        return summaries
