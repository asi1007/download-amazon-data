class UpdateRealtimeSalesUseCase {
  constructor(realtimeSalesSheet, ordersDownloader) {
    this.realtimeSalesSheet = realtimeSalesSheet;
    this.ordersDownloader = ordersDownloader;
  }

  execute() {
    const asinList = this.realtimeSalesSheet.getAsinList();
    const startDate = this._getTodayStart();

    let orders;
    try {
      orders = this.ordersDownloader.getOrdersWithItems(startDate);
    } catch (error) {
      console.log('注文データの取得に失敗しました: ' + error.message);
      return;
    }

    const salesMap = this._aggregateByAsin(orders, asinList);
    this.realtimeSalesSheet.writeRealtimeSales(salesMap);
  }

  _getTodayStart() {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
  }

  _aggregateByAsin(orders, asinList) {
    const salesMap = {};
    for (const asin of asinList) {
      salesMap[asin] = new RealtimeSalesResult(asin);
    }

    const activeOrders = orders.filter(order => !order.isCanceled());

    for (const order of activeOrders) {
      for (const item of order.items) {
        if (salesMap[item.asin]) {
          salesMap[item.asin].addSale(item.quantityOrdered, item.itemPriceAmount);
        }
      }
    }

    return salesMap;
  }
}
