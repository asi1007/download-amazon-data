class SalesInfo {
  constructor(data) {
    this.unitCount = data.unitCount || 0;
    this.totalSalesAmount = data.totalSales ? data.totalSales.amount : 0;
    this.orderCount = data.orderCount || 0;
  }
}
