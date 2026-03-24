from __future__ import annotations
import time
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator, SP_API_BASE

MARKETPLACE_JP = "A1VC38T7YXB528"


class SpApiPriceRepository:
    def __init__(self, authenticator: SpApiAuthenticator) -> None:
        self._auth = authenticator

    def get_competitive_prices(self, asins: list[str]) -> dict[str, float]:
        prices: dict[str, float] = {}
        for i in range(0, len(asins), 20):
            if i > 0:
                time.sleep(3)
            batch = asins[i:i + 20]
            url = (
                f"{SP_API_BASE}/products/pricing/v0/price"
                f"?MarketplaceId={MARKETPLACE_JP}"
                f"&ItemType=Asin"
                f"&Asins={','.join(batch)}"
            )
            response = self._auth.request("GET", url)
            batch_prices = self._parse_prices(response.json().get("payload", []))
            prices.update(batch_prices)
        return prices

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
