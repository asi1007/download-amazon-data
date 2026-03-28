class OrderItem {
  constructor(item) {
    this.asin = item.ASIN;
    this.quantityOrdered = item.QuantityOrdered;
    this.itemPriceAmount = item.ItemPrice ? Number(item.ItemPrice.Amount) : 0;
    console.log(item.ASIN + " qty:" + item.QuantityOrdered + " ItemPrice:" + JSON.stringify(item.ItemPrice) + " ItemTax:" + JSON.stringify(item.ItemTax));
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
