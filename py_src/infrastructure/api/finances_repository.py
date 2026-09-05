from __future__ import annotations
import time
from urllib.parse import quote

from py_src.domain.value_objects.item_fee import ItemFee
from py_src.infrastructure.api.sp_api_authenticator import (
    SpApiAuthenticator,
    SP_API_BASE,
    SP_API_REQUEST_TIMEOUT_SECONDS,
)

DEFAULT_PAUSE_SECONDS = 2


class FinancesRepository:
    def __init__(
        self,
        authenticator: SpApiAuthenticator,
        pause_seconds: float = DEFAULT_PAUSE_SECONDS,
    ) -> None:
        self._auth = authenticator
        self._pause_seconds = pause_seconds

    def get_item_fees(self, posted_after: str, posted_before: str) -> list[ItemFee]:
        self._auth.authenticate()
        raw_events = self._fetch_all_shipment_events(posted_after, posted_before)
        return self._flatten_item_fees(raw_events)

    def _fetch_all_shipment_events(self, posted_after: str, posted_before: str) -> list[dict]:
        all_events: list[dict] = []
        url = self._events_url(posted_after, posted_before)
        while True:
            response = self._auth._session.get(
                url, headers=self._auth.headers(), timeout=SP_API_REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code == 403:
                self._auth.authenticate()
                continue
            response.raise_for_status()
            payload = response.json().get("payload", {})
            financial_events = payload.get("FinancialEvents", {})
            all_events.extend(financial_events.get("ShipmentEventList", []))
            next_token = payload.get("NextToken")
            if not next_token:
                break
            time.sleep(self._pause_seconds)
            url = self._events_url(posted_after, posted_before, next_token)
        return all_events

    @staticmethod
    def _events_url(posted_after: str, posted_before: str, next_token: str | None = None) -> str:
        url = (
            f"{SP_API_BASE}/finances/v0/financialEvents"
            f"?PostedAfter={posted_after}"
            f"&PostedBefore={posted_before}"
        )
        if next_token:
            url += f"&NextToken={quote(next_token)}"
        return url

    @staticmethod
    def _flatten_item_fees(shipment_events: list[dict]) -> list[ItemFee]:
        item_fees: list[ItemFee] = []
        for event in shipment_events:
            order_id = event["AmazonOrderId"]
            for shipment_item in event.get("ShipmentItemList", []):
                fee_list = shipment_item.get("ItemFeeList", [])
                if not fee_list:
                    continue
                negative_total = sum(
                    fee["FeeAmount"]["CurrencyAmount"] for fee in fee_list
                )
                item_fees.append(
                    ItemFee(
                        order_id=order_id,
                        seller_sku=shipment_item["SellerSKU"],
                        fee_amount=-negative_total,
                    )
                )
        return item_fees
