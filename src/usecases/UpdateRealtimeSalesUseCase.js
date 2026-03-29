class UpdateRealtimeSalesUseCase {
  constructor(realtimeSalesSheet, salesDownloader, salesSheet) {
    this.realtimeSalesSheet = realtimeSalesSheet;
    this.salesDownloader = salesDownloader;
    this.salesSheet = salesSheet;
  }

  execute() {
    const asinList = this.realtimeSalesSheet.getAsinList();
    const sellingPrices = this._loadSellingPrices();
    console.log("B0FR3CZRGP sellingPrice: " + sellingPrices['B0FR3CZRGP']);
    console.log("PRICE_COLUMN: " + (this.salesSheet ? this.salesSheet.PRICE_COLUMN : 'N/A'));
    const { startDate, endDate } = this._getTodayRange();

    const asinSalesInfos = this.salesDownloader.getSalesInfosOf(asinList, "Day", startDate, endDate);
    const salesMap = this._buildSalesMap(asinList, asinSalesInfos, sellingPrices);
    this.realtimeSalesSheet.writeRealtimeSales(salesMap);
  }

  _loadSellingPrices() {
    if (!this.salesSheet) return {};
    this.salesSheet.getASINList();
    return this.salesSheet.getSellingPrices();
  }

  _getTodayRange() {
    const now = new Date();
    const startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
    const endDate = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 0);
    return { startDate, endDate };
  }

  _buildSalesMap(asinList, asinSalesInfos, sellingPrices) {
    const salesMap = {};
    for (const asin of asinList) {
      const info = asinSalesInfos[asin];
      const unitCount = info ? info.unitCount : 0;
      const totalAmount = unitCount * (sellingPrices[asin] || 0);
      salesMap[asin] = new RealtimeSalesResult(asin, unitCount, totalAmount);
    }
    return salesMap;
  }
}
