class UpdateSalesUseCase {
  constructor(salesSheet, salesDownloader, priceDownloader, adDataReader) {
    this.salesSheet = salesSheet;
    this.salesDownloader = salesDownloader;
    this.priceDownloader = priceDownloader;
    this.adDataReader = adDataReader;
  }

  executeDailySales() {
    const asinList = this.salesSheet.getASINList();
    const { startDate, endDate } = this._getDailyDateRange();

    const asinSalesInfos = this.salesDownloader.getSalesInfosOf(asinList, "Day", startDate, endDate);
    this.salesSheet.writeSalesNums(asinSalesInfos);

    if (this.priceDownloader) {
      const asinToPrices = this.priceDownloader.getPricesOf(asinList);
      this.salesSheet.writePrice(asinToPrices);
    }
  }

  executeWeeklySales() {
    const asinList = this.salesSheet.getASINList();
    const { startDate, endDate } = this._getWeeklyDateRange();

    const asinSalesInfos = this.salesDownloader.getSalesInfosOf(asinList, "Week", startDate, endDate);
    const asinToAdSpend = this._getAdSpendByAsin(startDate);
    const data = this._formatWeeklySalesData(asinSalesInfos, startDate, endDate, asinToAdSpend);
    this._writeToSalesDataSheet(data);
  }

  _getDailyDateRange() {
    const today = new Date();
    const startDate = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1, 0);
    const endDate = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 0);
    return { startDate, endDate };
  }

  _getWeeklyDateRange() {
    const today = new Date();
    const endDate = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 0);
    const day = endDate.getDay();
    const diff = day === 0 ? -6 : 1 - day;
    endDate.setDate(endDate.getDate() + diff);
    const startDate = new Date(endDate);
    startDate.setDate(endDate.getDate() - 7);
    return { startDate, endDate };
  }

  _formatWeeklySalesData(asinSalesInfos, startDate, endDate, asinToAdSpend) {
    const asinInfos = Object.entries(asinSalesInfos);
    return asinInfos.map(row => [
      startDate,
      endDate,
      row[0],
      row[1].unitCount,
      row[1].totalSales.amount,
      row[1].orderCount,
      asinToAdSpend[row[0]] || 0
    ]);
  }

  _getAdSpendByAsin(startDate) {
    if (!this.adDataReader) return {};
    const adDataList = this.adDataReader.fetchByPeriod(startDate);
    const asinToAdSpend = {};
    for (const adData of adDataList) {
      asinToAdSpend[adData.asin] = adData.adSpend;
    }
    return asinToAdSpend;
  }

  _writeToSalesDataSheet(data) {
    const dataSheet = getOrCreateSheet("sales_data");
    const lastRow = dataSheet.getLastRow();
    dataSheet.getRange(lastRow + 1, 1, data.length, data[0].length).setValues(data);
  }
}
