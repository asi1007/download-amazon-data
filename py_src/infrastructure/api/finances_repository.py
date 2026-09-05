from __future__ import annotations
from urllib.parse import urlencode

from py_src.domain.value_objects.item_fee import ItemFee
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator, SP_API_BASE


class FinancesRepository:
    def __init__(self, authenticator: SpApiAuthenticator) -> None:
        self._auth = authenticator

    def get_item_fees(self, posted_after: str, posted_before: str) -> list[ItemFee]:
        self._auth.authenticate()
        raw_events = self._fetch_all_shipment_events(posted_after, posted_before)
        return self._flatten_item_fees(raw_events)

    def _fetch_all_shipment_events(self, posted_after: str, posted_before: str) -> list[dict]:
        all_events: list[dict] = []
        url = self._events_url(posted_after, posted_before)
        while True:
            payload = self._auth.request("GET", url).json().get("payload", {})
            financial_events = payload.get("FinancialEvents", {})
            all_events.extend(financial_events.get("ShipmentEventList", []))
            next_token = payload.get("NextToken")
            if not next_token:
                break
            url = self._next_page_url(next_token)
        return all_events

    @staticmethod
    def _events_url(posted_after: str, posted_before: str) -> str:
        return (
            f"{SP_API_BASE}/finances/v0/financialEvents"
            f"?PostedAfter={posted_after}"
            f"&PostedBefore={posted_before}"
        )

    @staticmethod
    def _next_page_url(next_token: str) -> str:
        # NextToken は PostedAfter/PostedBefore と排他。併記すると2ページ目だけが
        # 本番で落ちる。tools/check_finances_api.py で実物を確認した形に揃える
        return f"{SP_API_BASE}/finances/v0/financialEvents?{urlencode({'NextToken': next_token})}"

    @staticmethod
    def _flatten_item_fees(shipment_events: list[dict]) -> list[ItemFee]:
        item_fees: list[ItemFee] = []
        for event in shipment_events:
            order_id = event.get("AmazonOrderId")
            if not order_id:
                continue
            for shipment_item in event.get("ShipmentItemList", []):
                fee_list = shipment_item.get("ItemFeeList", [])
                if not fee_list:
                    continue
                # 1件でも形の違うイベントが混ざると14日分の取得が丸ごと死ぬ。
                # 実物を叩いた tools/check_finances_api.py と同じく .get() で通す
                negative_total = sum(
                    fee.get("FeeAmount", {}).get("CurrencyAmount", 0) for fee in fee_list
                )
                seller_sku = shipment_item.get("SellerSKU")
                if not seller_sku:
                    continue
                item_fees.append(
                    ItemFee(
                        order_id=order_id,
                        seller_sku=seller_sku,
                        fee_amount=-negative_total,
                    )
                )
        return item_fees
