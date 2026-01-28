class UpdateInventoryUseCase {
  constructor(inventoryDownloader, inventorySheet) {
    this.inventoryDownloader = inventoryDownloader;
    this.inventorySheet = inventorySheet;
  }

  execute() {
    Logger.log('在庫状況の取得を開始します...');

    const startDate = this._getStartDate();
    Logger.log(`${startDate.toISOString()} 以降に更新された在庫を取得します。`);

    const inventoryData = this.inventoryDownloader.getAllInventorySummaries(startDate);
    Logger.log(`${inventoryData.length}件の在庫データを取得しました。`);

    this.inventorySheet.writeInventoryData(inventoryData);
    Logger.log('在庫状況の更新が完了しました。');
  }

  _getStartDate() {
    const startDate = new Date();
    startDate.setMonth(startDate.getMonth() - 1);
    startDate.setHours(0, 0, 0, 0);
    return startDate;
  }
}
