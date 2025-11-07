// SP-APIの設定
// Script Propertiesから認証情報を取得
// 設定方法: スクリプトエディタ > プロジェクトの設定 > スクリプト プロパティ
// 以下の3つのプロパティを設定してください:
// - API_KEY: Amazon SP-APIのAPIキー
// - API_SECRET: Amazon SP-APIのAPIシークレット
// - REFRESH_TOKEN: Amazon SP-APIのリフレッシュトークン

function getScriptProperty(key) {
  const value = PropertiesService.getScriptProperties().getProperty(key);
  if (!value) {
    throw new Error(`Script Property "${key}" が設定されていません。プロジェクトの設定で設定してください。`);
  }
  return value;
}

const API_KEY = getScriptProperty('API_KEY');
const API_SECRET = getScriptProperty('API_SECRET');
const REFRESH_TOKEN = getScriptProperty('REFRESH_TOKEN');

// OAuth 2.0トークン取得
function getAuthToken() {
  const url = "https://api.amazon.com/auth/o2/token";
  const payload = {
    'grant_type': 'refresh_token',
    'refresh_token': REFRESH_TOKEN,
    'client_id': API_KEY,
    'client_secret': API_SECRET
  };
  const options = {
    method: 'post',
    payload: payload
  };
  const response = UrlFetchApp.fetch(url, options);
  const json = JSON.parse(response.getContentText());
  return json.access_token;  // アクセストークンを返す
}


class Downloader{
  // base class. you must implement buildQueryParams method.
  constructor(path){
    // over ride this.url
    this.SP_API_URL = "https://sellingpartnerapi-fe.amazon.com";
    this.authToken = getAuthToken();
    this.options = {
      muteHttpExceptions : true,
      method: 'get',
      headers: {
      "Accept" : "application/json",
      "Content-Type":"application/json",
      "x-amz-access-token": this.authToken,
      }
    };
    this.marketplaceIDs = "marketplaceIds=A1VC38T7YXB528";
    this.marketplaceID = "MarketplaceId=A1VC38T7YXB528";
    this.url = this.SP_API_URL + path;
  }

  setQueryParams(queryParams){
    this.queryParams = queryParams;
  }

  getData(){
    this.urlquery = this.url + "?" + this.queryParams.join("&");
    Utilities.sleep(4500); // Rate limiting
    console.log(this.urlquery);
    const response = UrlFetchApp.fetch(this.urlquery, this.options);
    const data = JSON.parse(response.getContentText());
    return data
  }
}

function downloadTransactions(){
  const today = new Date();
  const startDate = new Date()
  const endDate = new Date()
  startDate.setDate(today.getDate() - 4); // 2日前＝一昨日
  startDate.setHours(0,0,0,0)
  endDate.setDate(today.getDate()- 3)
  endDate.setHours(0,0,0,0)
  downloader = new TransactionDownloader('/finances/2024-06-19/transactions')
  downloader.getTransactions(startDate, endDate)
}

class TransactionDownloader extends Downloader{

  getTransactions(startDay, endDay){
    let start = "postedAfter="   + startDay.toISOString()
    let end = "postedBefore=" + endDay.toISOString() 
    this.setQueryParams([start, end])
    let data = this.getData()

    let nextToken = data.payload.nextToken
    let transactions = data. payload.transactions
    transactions = transactions.filter((transaction) => transaction.transactionType==="Shipment" && transaction.transactionStatus==="RELEASED")
    let transactionData = transactions.map((transaction)=> new Transaction(transaction))
    console.log(data)
    //"DEFERRED"
  }
}


class Transaction{

  constructor(transaction){
    this.type = transaction.transactionType
    this.transactionStatus = transaction.transactionStatus
    this.transaction = transaction
    console.log(this.type)
    console.log(transaction)
    this.items = transaction.items.map((item)=> new Item(item))
  }
}


class Item{
  constructor(item){
    this.asin = item.contexts[0].asin
    this.quantity = item.contexts[0].quantityShipped
    let productCharge = item.breakdowns[0].breakdownAmount 
    let tax = item.breakdowns[1].breakdownAmount
    this.sales = productCharge + tax

    let amazonFees = item.breakdowns[2]
    console.log(amazonFees)
    this.fees = amazonFees.breakdowns[0].breakdownAmount
    this.comission = amazonFees.breakdowns[1].breakdownAmount

  }
}


class SKUDownloader extends Downloader{

  getASINtoSKUs(){
    const asinToSku = {};
    this.setQueryParams([this.marketplaceIDs]);
    let nextToken;
    do {
      let response = this.getData();
      if (response.items && response.items.length > 0) {
        response.items.forEach(item => {
          asinToSku[item.summaries[0].asin] = item.sku
        });
      }
      nextToken = response.pagination.nextToken;
      this.setQueryParams([this.marketplaceIDs, "pageToken=" + encodeURIComponent(nextToken)]);
    }while(nextToken!==undefined);
    return asinToSku;
  }
}


class PriceDownloader extends Downloader{

  getPriceOf(asin) {
    let queryParams = [
      this.marketplaceID,
      "ItemType=Asin",
      "Asins=" + asin
    ];
    this.setQueryParams(queryParams);
    let data = this.getData();
    return data.payload;
  }

  getPricesOf(asinList, asintoSKU) {
    let asintoPrices = {};
    for (let asin of asinList) {
        let priceData = this.getPriceOf(asin)        
        if (priceData && priceData.length > 0 && priceData[0].Product.CompetitivePricing.CompetitivePrices.length > 0) {
          asintoPrices[asin] = priceData[0].Product.CompetitivePricing.CompetitivePrices[0].Price.LandedPrice.Amount;
        }
    }
    return asintoPrices;
  }
}
  
  
class SalesDownloader extends Downloader{
  
  buildQueryParams(asin, type, startDate, endDate){
    const timeZone = "Asia/Tokyo";
    let queryParams = [this.marketplaceIDs];
    queryParams.push("interval=" + startDate.toISOString() + "--" + endDate.toISOString());
    queryParams.push("granularity=" + type);
    queryParams.push("granularityTimeZone=Asia/Tokyo");
    queryParams.push("asin=" + asin);
    return queryParams;
  }

  getSalesInfosOf(asinList, type,startDate, endDate){
    let a = 0;
    let asinSalesNums = {};
    for (let asin of asinList){
      let salesData = this.getSalesInfoOf(asin, type, startDate, endDate);
      asinSalesNums[asin] = salesData;
      a+=1
      console.log(String(a) + "商品目");
    }
    return asinSalesNums
  }

  getSalesInfoOf(asin, type, startDate, endDate){
    // return .unitCount, .totalSales.amount, .orderCount
    let queryParams = this.buildQueryParams(asin,type, startDate, endDate);
    this.setQueryParams(queryParams)
    let salesData = this.getData()
    return salesData.payload[0]
  }
}

class SalesSheet{
  constructor(sheetName, cell){
    const SHEET_ID = '1aAliE0u45YbMwcBMczrLrG82MRMjOVc999L3GWCUENE';  // Google SheetsのシートIDを入力
    const ASIN_SHEET_NAME = sheetName;
    this.START_COLUMN = SpreadsheetApp.openById(SHEET_ID).getSheetByName("設定").getRange(cell).getValue();
    this.PRICE_COLUMN = SpreadsheetApp.openById(SHEET_ID).getSheetByName("設定").getRange("B5").getValue(); 
    this.sheet = SpreadsheetApp.openById(SHEET_ID).getSheetByName(ASIN_SHEET_NAME);
    let lastRow = this.sheet.getLastRow();
    this.asinRange = this.sheet.getRange(1, 1, lastRow); // A列（1列目）を取得
    this.asinToRow = {};
    this.asinList =[];
  }

  getASINList(){
    let row = 1;
    for(let asinData of this.asinRange.getValues()){
      if(asinData[0].length === 10){
        this.asinList.push(asinData[0]);
        this.asinToRow[asinData[0]] = row;
      }
      row += 1;
    }
    return this.asinList;
  }

  writeSalesNums(salesNums){
    this.sheet.insertColumnBefore(this.START_COLUMN);
    this.sheet.getRange(1,this.START_COLUMN).setValue(Utilities.formatDate(new Date,"JST","yyyy/MM/dd"));
    this.sheet.getRange(1,this.START_COLUMN).setNumberFormat("dd");
    for (let i = 1; i < this.asinRange.getValues().length; i++){
      let asin = this.asinRange.getValues()[i-1][0]
      if(this.asinList.includes(asin)){
        this.sheet.getRange(i,this.START_COLUMN).setValue(salesNums[asin].unitCount);
        this.sheet.getRange(i,this.START_COLUMN).setBackground(null)
      }
    }
  }

  writePrice(asintoPrices){

    for (let asin in asintoPrices){
      if (this.asinList.includes(asin)) {
        let row = this.asinToRow[asin];
        this.sheet.getRange(row, this.START_COLUMN).setNote(asintoPrices[asin]);
        this.sheet.getRange(row, this.START_COLUMN).setBackground(null);
        const price = asintoPrices[asin];
        const prevPrice = this.sheet.getRange(row, this.START_COLUMN + 1).getNote();
        if(price < prevPrice){
          this.sheet.getRange(row,this.START_COLUMN).setBackground("red");
        }else if(price> prevPrice){
          this.sheet.getRange(row,this.START_COLUMN).setBackground("aqua");
        }
        this.sheet.getRange(row, this.PRICE_COLUMN).setValue(price)
      }
    }
  }
}

function main(type){
  mainSheet = new SalesSheet("売上/日","B2");
  asinList = mainSheet.getASINList();

  salesDataDownloader = new SalesDownloader( "/sales/v1/orderMetrics");
  let today = new Date();
  let startDate = new Date();
  switch (type){
    case "Day":
      startDate = new Date(today.getFullYear(), today.getMonth(),today.getDate()-1, 0);
      endDate = new Date(today.getFullYear(), today.getMonth(),today.getDate(), 0);
      asinSalesInfos = salesDataDownloader.getSalesInfosOf(asinList, type, startDate, endDate);
      mainSheet.writeSalesNums(asinSalesInfos);
      downloadPrices(mainSheet);
      break;
    case "Week":
      endDate = new Date(today.getFullYear(), today.getMonth(),today.getDate(), 0);
      let day = endDate.getDay();// 0 = 日曜, 1 = 月曜, ..., 6 = 土曜
      const diff = day === 0 ? -6 : 1 - day;
      endDate.setDate(endDate.getDate() + diff);
      startDate.setDate(endDate.getDate()-7)
      //endDate = new Date(2025, 6, 28, 0, 0, 0);  //startDate = new Date(2025, 6, 21, 0, 0, 0);
      startDate = new Date(2025, 9, 20, 0, 0, 0);  
      endDate = new Date(2025, 9, 27, 0, 0, 0);
      asinSalesInfos = salesDataDownloader.getSalesInfosOf(asinList, type, startDate, endDate);
      let asinInfos = Object.entries(asinSalesInfos);
          // return .unitCount, .totalSales.amount, .orderCount
      let data = asinInfos.map(row=>[startDate, endDate, row[0], row[1].unitCount, row[1].totalSales.amount,row[1].orderCount])

      let dataSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("sales_data");
      let lastRow = dataSheet.getLastRow()

      dataSheet.getRange(lastRow+1,1,data.length, data[0].length).setValues(data);
      break;
  }
}

function updateLastWeekSalesNum(){
  main("Week")
}

function updateYesterdaySalesNum(){
  main("Day")
}

function downloadPrices() {
  mainSheet = new SalesSheet("売上/日","B2");
  let path = "/listings/2021-08-01/items/APS8L6SC4MEPF"
  const skuDownloader = new SKUDownloader( path);
  const asintoSKU = skuDownloader.getASINtoSKUs();
  const asinList = mainSheet.getASINList(); // Assuming this returns SKUs
  const priceDownloader = new PriceDownloader("/products/pricing/v0/competitivePrice");
  const asinToPrices = priceDownloader.getPricesOf(asinList, asintoSKU);
  mainSheet.getASINList();
  mainSheet.writePrice(asinToPrices);
}

function deleteOrderNumber() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var lastRow = sheet.getLastRow();
  var values = sheet.getRange(1, 2, lastRow).getValues();
  for (var i = 1; i <= lastRow; i++) {
    var val = values[i - 1][0];
    if (!isNaN(val) && val >= 9) {
      sheet.getRange(i, 2).clearContent(); // B列だけ中身を消す
    }
  }
}

// =====================================
// 在庫状況取得機能
// =====================================

class InventorySummariesDownloader extends Downloader {
  /**
   * 在庫サマリーを取得
   * @param {Date} startDateTime - この日時以降に更新された在庫のみ取得（省略可）
   * @returns {Array} 在庫サマリーデータの配列
   */
  getAllInventorySummaries(startDateTime) {
    let allInventories = [];
    
    // クエリパラメータの構築
    let queryParams = [
      this.marketplaceIDs,
      "granularityType=Marketplace",
      "granularityId=A1VC38T7YXB528",
      "details=true"  // reservedQuantityの詳細を取得
    ];
    
    // startDateTimeが指定されている場合は追加
    if (startDateTime) {
      queryParams.push("startDateTime=" + startDateTime.toISOString());
    }
    
    this.setQueryParams(queryParams);
    let data = this.getData();
    
    if (data.payload && data.payload.inventorySummaries) {
      allInventories = allInventories.concat(data.payload.inventorySummaries);
    }
    
    // nextTokenがある場合は次のページを取得（paginationオブジェクトから取得）
    let nextToken = data.pagination ? data.pagination.nextToken : null;
    while (nextToken) {
      queryParams = [
        this.marketplaceIDs,
        "granularityType=Marketplace",
        "granularityId=A1VC38T7YXB528",
        "details=true",  // reservedQuantityの詳細を取得
        "nextToken=" + encodeURIComponent(nextToken)
      ];
      
      // startDateTimeをnextTokenと一緒に使う
      if (startDateTime) {
        queryParams.push("startDateTime=" + startDateTime.toISOString());
      }
      
      this.setQueryParams(queryParams);
      data = this.getData();
      if (data.payload && data.payload.inventorySummaries) {
        allInventories = allInventories.concat(data.payload.inventorySummaries);
      }
      nextToken = data.pagination ? data.pagination.nextToken : null;
    }
    
    return allInventories;
  }
}

class InventorySheet {
  constructor() {
    const SHEET_ID = '1aAliE0u45YbMwcBMczrLrG82MRMjOVc999L3GWCUENE';
    const SHEET_NAME = '納品状況';
    this.spreadsheet = SpreadsheetApp.openById(SHEET_ID);
    this.sheet = this.spreadsheet.getSheetByName(SHEET_NAME);
    
    // シートが存在しない場合は作成
    if (!this.sheet) {
      this.sheet = this.spreadsheet.insertSheet(SHEET_NAME);
      this.initializeSheet();
    }
  }
  
  /**
   * シートの初期化（ヘッダー行を設定）
   */
  initializeSheet() {
    const headers = [
      'ASIN',
      'SKU',
      '販売可能\n(fulfillableQuantity)',
      '納品準備中\n(inboundWorkingQuantity)',
      '納品中\n(inboundShippedQuantity)',
      '受領中\n(inboundReceivingQuantity)',
      '予約済合計\n(totalReservedQuantity)',
      '注文確保\n(pendingCustomerOrderQuantity)',
      '転送中\n(pendingTransshipmentQuantity)',
      '処理中\n(fcProcessingQuantity)',
      '最終更新日時'
    ];
    
    this.sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    
    // ヘッダー行のフォーマット設定
    const headerRange = this.sheet.getRange(1, 1, 1, headers.length);
    headerRange.setFontWeight('bold');
    headerRange.setBackground('#4CAF50');
    headerRange.setFontColor('#FFFFFF');
    headerRange.setHorizontalAlignment('center');
    headerRange.setVerticalAlignment('middle');
    headerRange.setWrap(true);
    
    // 列幅の調整
    this.sheet.setColumnWidth(1, 100); // ASIN
    this.sheet.setColumnWidth(2, 150); // SKU
    for (let i = 3; i <= 10; i++) {
      this.sheet.setColumnWidth(i, 100);
    }
    this.sheet.setColumnWidth(11, 150); // 最終更新日時
    
    // 行の高さを調整
    this.sheet.setRowHeight(1, 60);
  }
  
  /**
   * 在庫データをシートに書き込み
   * @param {Array<Object>} inventoryData - 在庫データの配列
   */
  writeInventoryData(inventoryData) {
    // シート全体をクリア
    this.sheet.clear();
    
    // ヘッダー行を設定
    const headers = [
      'ASIN',
      'SKU',
      '販売可能\n(fulfillableQuantity)',
      '納品準備中\n(inboundWorkingQuantity)',
      '納品中\n(inboundShippedQuantity)',
      '受領中\n(inboundReceivingQuantity)',
      '予約済合計\n(totalReservedQuantity)',
      '注文確保\n(pendingCustomerOrderQuantity)',
      '転送中\n(pendingTransshipmentQuantity)',
      '処理中\n(fcProcessingQuantity)',
      '最終更新日時'
    ];
    
    this.sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    
    // ヘッダー行のフォーマット設定
    const headerRange = this.sheet.getRange(1, 1, 1, headers.length);
    headerRange.setFontWeight('bold');
    headerRange.setBackground('#4CAF50');
    headerRange.setFontColor('#FFFFFF');
    headerRange.setHorizontalAlignment('center');
    headerRange.setVerticalAlignment('middle');
    headerRange.setWrap(true);
    this.sheet.setRowHeight(1, 60);
    
    // データを整形
    const rows = [];
    const now = Utilities.formatDate(new Date(), "JST", "yyyy/MM/dd HH:mm:ss");
    
    for (let inventory of inventoryData) {
      const sku = inventory.sellerSku || '';
      const asin = inventory.asin || '';
      
      // inventoryDetailsから各値を取得
      const inventoryDetails = inventory.inventoryDetails || {};
      const reserved = inventoryDetails.reservedQuantity || {};
      
      rows.push([
        asin,
        sku,
        inventoryDetails.fulfillableQuantity || 0,
        inventoryDetails.inboundWorkingQuantity || 0,
        inventoryDetails.inboundShippedQuantity || 0,
        inventoryDetails.inboundReceivingQuantity || 0,
        reserved.totalReservedQuantity || 0,
        reserved.pendingCustomerOrderQuantity || 0,
        reserved.pendingTransshipmentQuantity || 0,
        reserved.fcProcessingQuantity || 0,
        now
      ]);
    }
    
    // 列幅の調整
    this.sheet.setColumnWidth(1, 100); // ASIN
    this.sheet.setColumnWidth(2, 150); // SKU
    for (let i = 3; i <= 10; i++) {
      this.sheet.setColumnWidth(i, 100);
    }
    this.sheet.setColumnWidth(11, 150); // 最終更新日時
    
    // データをシートに書き込み
    if (rows.length > 0) {
      this.sheet.getRange(2, 1, rows.length, 11).setValues(rows);
      
      // 数値列にフォーマット設定
      for (let i = 3; i <= 10; i++) {
        this.sheet.getRange(2, i, rows.length, 1).setNumberFormat('#,##0');
        this.sheet.getRange(2, i, rows.length, 1).setHorizontalAlignment('right');
      }
      
      // データ行に交互の背景色を設定
      for (let i = 0; i < rows.length; i++) {
        const rowNum = i + 2;
        const color = i % 2 === 0 ? '#F5F5F5' : '#FFFFFF';
        this.sheet.getRange(rowNum, 1, 1, 11).setBackground(color);
      }
    }
    
    Logger.log(`${rows.length}件の在庫データを書き込みました。`);
  }
}

/**
 * 在庫状況を更新するメイン関数
 */
function updateInventoryStatus() {
  try {
    Logger.log('在庫状況の取得を開始します...');
    
    // 1ヶ月前の日時を計算
    const startDate = new Date();
    startDate.setMonth(startDate.getMonth() - 1);
    startDate.setHours(0, 0, 0, 0);
    Logger.log(`${startDate.toISOString()} 以降に更新された在庫を取得します。`);
    
    // 1. 直近1ヶ月に更新された在庫サマリーを取得
    const inventoryDownloader = new InventorySummariesDownloader("/fba/inventory/v1/summaries");
    const inventoryData = inventoryDownloader.getAllInventorySummaries(startDate);
    Logger.log(`${inventoryData.length}件の在庫データを取得しました。`);
    
    // 2. 納品状況シートに書き込み
    const inventorySheet = new InventorySheet();
    inventorySheet.writeInventoryData(inventoryData);
    
    Logger.log('在庫状況の更新が完了しました。');
    
  } catch (error) {
    Logger.log('エラーが発生しました: ' + error.toString());
    throw error;
  }
}

