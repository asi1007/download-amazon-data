class InventorySummary {
  constructor(data) {
    this.asin = data.asin || '';
    this.sellerSku = data.sellerSku || '';
    this.price = data.price || '';

    const inventoryDetails = data.inventoryDetails || {};
    const reserved = inventoryDetails.reservedQuantity || {};

    this.fulfillableQuantity = inventoryDetails.fulfillableQuantity || 0;
    this.inboundWorkingQuantity = inventoryDetails.inboundWorkingQuantity || 0;
    this.inboundShippedQuantity = inventoryDetails.inboundShippedQuantity || 0;
    this.inboundReceivingQuantity = inventoryDetails.inboundReceivingQuantity || 0;
    this.totalReservedQuantity = reserved.totalReservedQuantity || 0;
    this.pendingCustomerOrderQuantity = reserved.pendingCustomerOrderQuantity || 0;
    this.pendingTransshipmentQuantity = reserved.pendingTransshipmentQuantity || 0;
    this.fcProcessingQuantity = reserved.fcProcessingQuantity || 0;
  }

  toArray(timestamp) {
    return [
      this.asin,
      this.sellerSku,
      this.price,
      this.fulfillableQuantity,
      this.inboundWorkingQuantity,
      this.inboundShippedQuantity,
      this.inboundReceivingQuantity,
      this.totalReservedQuantity,
      this.pendingCustomerOrderQuantity,
      this.pendingTransshipmentQuantity,
      this.fcProcessingQuantity,
      timestamp
    ];
  }
}
