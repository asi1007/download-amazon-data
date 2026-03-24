from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class OrderItem:
    asin: str
    quantity_ordered: int
    item_price_amount: float

    @staticmethod
    def from_api_response(data: dict) -> OrderItem:
        price = data.get("ItemPrice")
        amount = float(price["Amount"]) if price else 0.0
        return OrderItem(
            asin=data["ASIN"],
            quantity_ordered=data["QuantityOrdered"],
            item_price_amount=amount,
        )


@dataclass(frozen=True)
class Order:
    order_id: str
    order_status: str
    items: list[OrderItem]

    @property
    def is_canceled(self) -> bool:
        return self.order_status == "Canceled"

    @staticmethod
    def from_api_response(order_data: dict, items_data: list[dict]) -> Order:
        return Order(
            order_id=order_data["AmazonOrderId"],
            order_status=order_data["OrderStatus"],
            items=[OrderItem.from_api_response(item) for item in items_data],
        )
