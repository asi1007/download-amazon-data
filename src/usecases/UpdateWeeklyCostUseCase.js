class UpdateWeeklyCostUseCase {
  constructor(salesSheet, salesDownloader, costDataReader, weeklyCostSheet) {
    this.salesSheet = salesSheet;
    this.salesDownloader = salesDownloader;
    this.costDataReader = costDataReader;
    this.weeklyCostSheet = weeklyCostSheet;
  }

  execute() {
    Logger.log('週次コスト集計を開始します...');

    const asinList = this.salesSheet.getASINList();
    const { startDate, endDate } = this._getWeeklyDateRange();

    Logger.log(`集計期間: ${startDate.toISOString()} - ${endDate.toISOString()}`);

    const asinSalesInfos = this.salesDownloader.getSalesInfosOf(asinList, "Week", startDate, endDate);
    this.costDataReader.getASINList();
    const costData = this.costDataReader.getAllCostData();

    const weeklyData = this._calculateWeeklyData(asinList, asinSalesInfos, costData, startDate);
    this.weeklyCostSheet.writeWeeklyCostData(weeklyData);

    Logger.log('週次コスト集計が完了しました。');
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

  _calculateWeeklyData(asinList, asinSalesInfos, costData, startDate) {
    const yearMonth = Utilities.formatDate(startDate, "JST", "yyyy-MM");
    const weekOfMonth = Math.ceil(startDate.getDate() / 7);
    const weeklyData = [];

    for (const asin of asinList) {
      const salesInfo = asinSalesInfos[asin];
      const cost = costData[asin];

      if (!salesInfo) continue;

      const unitCount = salesInfo.unitCount || 0;
      const salesAmount = salesInfo.totalSales ? salesInfo.totalSales.amount : 0;

      const totalCost = this._calculateTotalCost(cost, unitCount);
      const imageUrl = cost ? cost.imageUrl : '';
      const adCost = cost ? cost.adCost : 0;
      const grossProfit = salesAmount - totalCost - adCost;

      weeklyData.push([
        asin,
        imageUrl,
        yearMonth,
        weekOfMonth,
        unitCount,
        salesAmount,
        totalCost,
        adCost,
        grossProfit
      ]);
    }

    return weeklyData;
  }

  _calculateTotalCost(cost, unitCount) {
    if (!cost || unitCount <= 0) {
      return 0;
    }
    return cost.getTotalUnitCost() * unitCount;
  }
}
