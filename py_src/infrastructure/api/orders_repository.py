from __future__ import annotations
import time
import requests
from py_src.domain.entities.order import Order

SP_API_BASE = "https://sellingpartnerapi-fe.amazon.com"
LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
MARKETPLACE_JP = "A1VC38T7YXB528"


class OrdersRepository:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        session: requests.Session | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._session = session or requests.Session()
        self._access_token: str | None = None

    def get_orders_with_items(self, created_after: str) -> list[Order]:
        self._authenticate()
        raw_orders = self._fetch_all_orders(created_after)
        if not raw_orders:
            return []
        return [self._build_order(raw) for raw in raw_orders]

    def get_prices(self, asins: list[str]) -> dict[str, float]:
        self._authenticate()
        prices: dict[str, float] = {}
        for i in range(0, len(asins), 20):
            if i > 0:
                time.sleep(3)
            batch = asins[i:i + 20]
            batch_prices = self._fetch_prices(batch)
            prices.update(batch_prices)
        return prices

    def _fetch_prices(self, asins: list[str]) -> dict[str, float]:
        url = (
            f"{SP_API_BASE}/products/pricing/v0/price"
            f"?MarketplaceId={MARKETPLACE_JP}"
            f"&ItemType=Asin"
            f"&Asins={','.join(asins)}"
        )
        for attempt in range(5):
            time.sleep(2 if attempt == 0 else 10)
            response = self._session.get(url, headers=self._headers())
            if response.status_code == 429:
                continue
            if response.status_code == 403:
                self._authenticate()
                continue
            response.raise_for_status()
            return self._parse_prices(response.json().get("payload", []))
        response.raise_for_status()
        return {}

    @staticmethod
    def _parse_prices(payload: list[dict]) -> dict[str, float]:
        prices: dict[str, float] = {}
        for item in payload:
            if item.get("status") != "Success":
                continue
            asin = item.get("ASIN", "")
            offers = item.get("Product", {}).get("Offers", [])
            if offers:
                listing_price = offers[0].get("BuyingPrice", {}).get("ListingPrice", {})
                amount = float(listing_price.get("Amount", 0))
                if amount > 0:
                    prices[asin] = amount
        return prices

    def _authenticate(self) -> None:
        response = self._session.post(LWA_TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        })
        response.raise_for_status()
        self._access_token = response.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-amz-access-token": self._access_token or "",
            "User-Agent": "download-amazon-data/0.1.0",
        }

    def _fetch_all_orders(self, created_after: str) -> list[dict]:
        all_orders: list[dict] = []
        url = (
            f"{SP_API_BASE}/orders/v0/orders"
            f"?CreatedAfter={created_after}"
            f"&MarketplaceIds={MARKETPLACE_JP}"
        )

        while True:
            time.sleep(2)
            response = self._session.get(url, headers=self._headers())
            if response.status_code == 403:
                self._authenticate()
                continue
            response.raise_for_status()
            payload = response.json().get("payload", {})
            all_orders.extend(payload.get("Orders", []))

            next_token = payload.get("NextToken")
            if not next_token:
                break
            url = (
                f"{SP_API_BASE}/orders/v0/orders"
                f"?CreatedAfter={created_after}"
                f"&MarketplaceIds={MARKETPLACE_JP}"
                f"&NextToken={requests.utils.quote(next_token)}"
            )

        return all_orders

    def _build_order(self, raw_order: dict) -> Order:
        order_id = raw_order["AmazonOrderId"]
        url = f"{SP_API_BASE}/orders/v0/orders/{order_id}/orderItems?marketplaceIds={MARKETPLACE_JP}"

        for attempt in range(5):
            time.sleep(3 if attempt == 0 else 15)
            response = self._session.get(url, headers=self._headers())
            if response.status_code == 429:
                continue
            if response.status_code == 403:
                self._authenticate()
                continue
            response.raise_for_status()
            items_data = response.json().get("payload", {}).get("OrderItems", [])
            return Order.from_api_response(raw_order, items_data)

        response.raise_for_status()
        return Order.from_api_response(raw_order, [])
