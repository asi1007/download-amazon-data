function updateYesterdaySalesNum() {
  const salesSheet = new SalesSheet("売上/日");
  const salesDownloader = new SalesDownloader("/sales/v1/orderMetrics");
  const priceDownloader = new PriceDownloader("/products/pricing/v0/competitivePrice");
  const useCase = new UpdateSalesUseCase(salesSheet, salesDownloader, priceDownloader);
  useCase.executeDailySales();
}

function updateLastWeekSalesNum() {
  const salesSheet = new SalesSheet("売上/日");
  const salesDownloader = new SalesDownloader("/sales/v1/orderMetrics");
  const adDataReader = new AmazonAdDataReader();
  const useCase = new UpdateSalesUseCase(salesSheet, salesDownloader, null, adDataReader);
  useCase.executeWeeklySales();
}

function downloadPrices() {
  const salesSheet = new SalesSheet("売上/日");
  const skuDownloader = new SKUDownloader("/listings/2021-08-01/items/APS8L6SC4MEPF");
  const priceDownloader = new PriceDownloader("/products/pricing/v0/competitivePrice");
  const useCase = new UpdatePriceUseCase(salesSheet, skuDownloader, priceDownloader);
  useCase.execute();
}

function updateInventoryStatus() {
  try {
    const inventoryDownloader = new InventorySummariesDownloader("/fba/inventory/v1/summaries");
    const inventorySheet = new InventorySheet();
    const priceDownloader = new PriceDownloader("/products/pricing/v0/competitivePrice");
    const useCase = new UpdateInventoryUseCase(inventoryDownloader, inventorySheet, priceDownloader);
    useCase.execute();
  } catch (error) {
    Logger.log('エラーが発生しました: ' + error.toString());
    throw error;
  }
}

function updateWeeklyCostSummary() {
  try {
    const salesSheet = new SalesSheet("売上/日");
    const salesDownloader = new SalesDownloader("/sales/v1/orderMetrics");
    const costDataReader = new CostDataReader();
    const weeklyCostSheet = new WeeklyCostSheet();

    const useCase = new UpdateWeeklyCostUseCase(
      salesSheet,
      salesDownloader,
      costDataReader,
      weeklyCostSheet
    );
    useCase.execute();
  } catch (error) {
    Logger.log('エラーが発生しました: ' + error.toString());
    throw error;
  }
}

function getCostData() {
  const reader = new CostDataReader();
  const asinList = reader.getASINList();
  const costData = reader.getAllCostData();

  Logger.log(`${asinList.length}件のASINのコストデータを取得しました。`);

  let count = 0;
  for (const asin in costData) {
    if (count >= 3) break;
    Logger.log(JSON.stringify(costData[asin]));
    count++;
  }

  return costData;
}

function getAmazonAdData() {
  const adDataReader = new AmazonAdDataReader();
  const useCase = new GetAdDataUseCase(adDataReader);
  return useCase.executeLatest();
}

function getAmazonAdDataByDate(dateString) {
  const adDataReader = new AmazonAdDataReader();
  const useCase = new GetAdDataUseCase(adDataReader);
  return useCase.executeByDate(dateString);
}

function downloadTransactions() {
  try {
    const transactionDownloader = new TransactionDownloader('/finances/2024-06-19/transactions');
    const transactionSheet = new TransactionSheet();
    const useCase = new DownloadTransactionUseCase(transactionDownloader, transactionSheet);
    useCase.execute();
  } catch (error) {
    Logger.log('エラーが発生しました: ' + error.toString());
    throw error;
  }
}

function deleteOrderNumber() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const lastRow = sheet.getLastRow();
  const values = sheet.getRange(1, 2, lastRow).getValues();
  for (let i = 1; i <= lastRow; i++) {
    const val = values[i - 1][0];
    if (!isNaN(val) && val >= 9) {
      sheet.getRange(i, 2).clearContent();
    }
  }
}

function updateRealtimeSales() {
  try {
    const realtimeSalesSheet = new RealtimeSalesSheet();
    const ordersDownloader = new OrdersDownloader('/orders/v0/orders');
    const salesSheet = new SalesSheet("売上/日");
    const useCase = new UpdateRealtimeSalesUseCase(realtimeSalesSheet, ordersDownloader, salesSheet);
    useCase.execute();
  } catch (error) {
    Logger.log('エラーが発生しました: ' + error.toString());
    throw error;
  }
}

function setupRealtimeSalesTrigger() {
  ScriptApp.newTrigger('updateRealtimeSales')
    .timeBased()
    .everyMinutes(10)
    .create();
  Logger.log('リアルタイム売上更新トリガーを設定しました（10分間隔）');
}
