from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from py_src.domain.entities.order import Order
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator, SP_API_BASE

MARKETPLACE_JP = "A1VC38T7YXB528"
JST = timezone(timedelta(hours=9))


class OrdersRepository:
    def __init__(self, authenticator: SpApiAuthenticator) -> None:
        self._auth = authenticator

    def get_orders_with_items(self, created_after: str) -> list[Order]:
        self._auth.authenticate()
        raw_orders = self._fetch_all_orders(created_after)
        if not raw_orders:
            return []
        return [self._build_order(raw) for raw in raw_orders]

    def _fetch_all_orders(self, created_after: str) -> list[dict]:
        all_orders: list[dict] = []
        url = (
            f"{SP_API_BASE}/orders/v0/orders"
            f"?CreatedAfter={created_after}"
            f"&MarketplaceIds={MARKETPLACE_JP}"
        )
        while True:
            payload = self._auth.request("GET", url).json().get("payload", {})
            all_orders.extend(payload.get("Orders", []))
            next_token = payload.get("NextToken")
            if not next_token:
                break
            url = _next_page_url(f"{SP_API_BASE}/orders/v0/orders", next_token)
        return all_orders

    def get_purchase_dates(self, created_after: str, created_before: str) -> dict[str, date]:
        self._auth.authenticate()
        raw_orders = self._fetch_orders_in_range(created_after, created_before)
        return self._to_purchase_date_map(raw_orders)

    def _fetch_orders_in_range(self, created_after: str, created_before: str) -> list[dict]:
        all_orders: list[dict] = []
        url = self._orders_list_url(created_after, created_before)
        while True:
            payload = self._auth.request("GET", url).json().get("payload", {})
            all_orders.extend(payload.get("Orders", []))
            next_token = payload.get("NextToken")
            if not next_token:
                break
            url = _next_page_url(f"{SP_API_BASE}/orders/v0/orders", next_token)
        return all_orders

    @staticmethod
    def _orders_list_url(created_after: str, created_before: str) -> str:
        return (
            f"{SP_API_BASE}/orders/v0/orders"
            f"?CreatedAfter={created_after}"
            f"&CreatedBefore={created_before}"
            f"&MarketplaceIds={MARKETPLACE_JP}"
        )

    @staticmethod
    def _to_purchase_date_map(raw_orders: list[dict]) -> dict[str, date]:
        purchase_dates: dict[str, date] = {}
        for raw_order in raw_orders:
            order_id = raw_order["AmazonOrderId"]
            purchase_dates[order_id] = _to_jst_date(raw_order["PurchaseDate"])
        return purchase_dates

    def _build_order(self, raw_order: dict) -> Order:
        order_id = raw_order["AmazonOrderId"]
        url = f"{SP_API_BASE}/orders/v0/orders/{order_id}/orderItems?marketplaceIds={MARKETPLACE_JP}"
        response = self._auth.request("GET", url)
        items_data = response.json().get("payload", {}).get("OrderItems", [])
        return Order.from_api_response(raw_order, items_data)


def _next_page_url(base_url: str, next_token: str) -> str:
    # NextToken は他のフィルタと排他。PostedAfter/CreatedAfter を併記すると
    # 2ページ目だけが本番で落ちる（tools/check_finances_api.py の実物確認と同じ形にする）
    return f"{base_url}?{urlencode({'NextToken': next_token})}"


def _to_jst_date(purchase_date_utc: str) -> date:
    parsed_utc = datetime.fromisoformat(purchase_date_utc.replace("Z", "+00:00"))
    return parsed_utc.astimezone(JST).date()
