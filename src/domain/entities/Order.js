class OrderItem {
  constructor(item) {
    this.asin = item.ASIN;
    this.quantityOrdered = item.QuantityOrdered;
    this.itemPriceAmount = item.ItemPrice ? Number(item.ItemPrice.Amount) : 0;
  }
}

class Order {
  constructor(orderData, orderItemsData) {
    this.orderId = orderData.AmazonOrderId;
    this.orderStatus = orderData.OrderStatus;
    this.purchaseDate = orderData.PurchaseDate;
    this.items = orderItemsData.map(item => new OrderItem(item));
  }

  isCanceled() {
    return this.orderStatus === 'Canceled';
  }
}
