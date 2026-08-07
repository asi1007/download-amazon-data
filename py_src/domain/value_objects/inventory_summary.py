from __future__ import annotations
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class InventorySummary:
    asin: str
    seller_sku: str
    price: float | str
    fulfillable_quantity: int
    inbound_working_quantity: int
    inbound_shipped_quantity: int
    inbound_receiving_quantity: int
    total_reserved_quantity: int
    pending_customer_order_quantity: int
    pending_transshipment_quantity: int
    fc_processing_quantity: int

    @classmethod
    def from_api_payload(cls, data: dict) -> "InventorySummary":
        details = data.get("inventoryDetails") or {}
        reserved = details.get("reservedQuantity") or {}
        return cls(
            asin=data.get("asin", ""),
            seller_sku=data.get("sellerSku", ""),
            price="",
            fulfillable_quantity=details.get("fulfillableQuantity", 0),
            inbound_working_quantity=details.get("inboundWorkingQuantity", 0),
            inbound_shipped_quantity=details.get("inboundShippedQuantity", 0),
            inbound_receiving_quantity=details.get("inboundReceivingQuantity", 0),
            total_reserved_quantity=reserved.get("totalReservedQuantity", 0),
            pending_customer_order_quantity=reserved.get("pendingCustomerOrderQuantity", 0),
            pending_transshipment_quantity=reserved.get("pendingTransshipmentQuantity", 0),
            fc_processing_quantity=reserved.get("fcProcessingQuantity", 0),
        )

    def with_price(self, price: float | str) -> "InventorySummary":
        return replace(self, price=price)

    def to_row(self, timestamp: str) -> list:
        return [
            self.asin,
            self.seller_sku,
            self.price,
            self.fulfillable_quantity,
            self.inbound_working_quantity,
            self.inbound_shipped_quantity,
            self.inbound_receiving_quantity,
            self.total_reserved_quantity,
            self.pending_customer_order_quantity,
            self.pending_transshipment_quantity,
            self.fc_processing_quantity,
            timestamp,
        ]
