class UpdateRealtimeSalesUseCase {
  constructor(realtimeSalesSheet, ordersDownloader, salesSheet) {
    this.realtimeSalesSheet = realtimeSalesSheet;
    this.ordersDownloader = ordersDownloader;
    this.salesSheet = salesSheet;
  }

  execute() {
    const asinList = this.realtimeSalesSheet.getAsinList();
    const sellingPrices = this._loadSellingPrices();
    console.log("sellingPrices keys: " + Object.keys(sellingPrices).length);
    const startDate = this._getTodayStart();

    let orders;
    try {
      orders = this.ordersDownloader.getOrdersWithItems(startDate);
    } catch (error) {
      console.log('注文データの取得に失敗しました: ' + error.message);
      return;
    }

    const salesMap = this._aggregateByAsin(orders, asinList, sellingPrices);
    this.realtimeSalesSheet.writeRealtimeSales(salesMap);
  }

  _loadSellingPrices() {
    if (!this.salesSheet) return {};
    this.salesSheet.getASINList();
    return this.salesSheet.getSellingPrices();
  }

  _getTodayStart() {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
  }

  _aggregateByAsin(orders, asinList, sellingPrices) {
    const salesMap = {};
    for (const asin of asinList) {
      salesMap[asin] = new RealtimeSalesResult(asin);
    }

    const activeOrders = orders.filter(order => !order.isCanceled());

    for (const order of activeOrders) {
      for (const item of order.items) {
        if (salesMap[item.asin]) {
          const amount = item.itemPriceAmount > 0
            ? item.itemPriceAmount
            : (sellingPrices[item.asin] || 0) * item.quantityOrdered;
          if (item.itemPriceAmount === 0) {
            console.log("FALLBACK " + item.asin + " qty:" + item.quantityOrdered + " sellingPrice:" + sellingPrices[item.asin] + " amount:" + amount);
          }
          salesMap[item.asin].addSale(item.quantityOrdered, amount);
        }
      }
    }

    return salesMap;
  }
}
