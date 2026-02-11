class UpdateInventoryUseCase {
  constructor(inventoryDownloader, inventorySheet, priceDownloader) {
    this.inventoryDownloader = inventoryDownloader;
    this.inventorySheet = inventorySheet;
    this.priceDownloader = priceDownloader;
  }

  execute() {
    Logger.log('在庫状況の取得を開始します...');

    const startDate = this._getStartDate();
    Logger.log(`${startDate.toISOString()} 以降に更新された在庫を取得します。`);

    const inventoryData = this.inventoryDownloader.getAllInventorySummaries(startDate);
    Logger.log(`${inventoryData.length}件の在庫データを取得しました。`);

    const inventoryDataWithPrices = this._addPricesToInventoryData(inventoryData);

    this.inventorySheet.writeInventoryData(inventoryDataWithPrices);
    Logger.log('在庫状況の更新が完了しました。');
  }

  _addPricesToInventoryData(inventoryData) {
    const asinList = inventoryData.map(item => item.asin);
    const asinToPrices = this.priceDownloader.getPricesOf(asinList, {});
    Logger.log(`${Object.keys(asinToPrices).length}件の価格データを取得しました。`);

    return inventoryData.map(item => ({
      ...item,
      price: asinToPrices[item.asin] || ''
    }));
  }

  _getStartDate() {
    const startDate = new Date();
    startDate.setMonth(startDate.getMonth() - 1);
    startDate.setHours(0, 0, 0, 0);
    return startDate;
  }
}
