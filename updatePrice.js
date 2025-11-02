function updatePrice() {

  var sheet  = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var row = sheet.getActiveCell().getRow()
  console.log(row)
  const sku = sheet.getRange(row,SpreadsheetApp.getActiveSpreadsheet().getSheetByName("設定").getRange("B8").getValue()).getValue()
  const price = sheet.getRange(row,SpreadsheetApp.getActiveSpreadsheet().getSheetByName("設定").getRange("B5").getValue()).getValue()
  const name = sheet.getRange(row,SpreadsheetApp.getActiveSpreadsheet().getSheetByName("設定").getRange("B9").getValue()).getValue()

  var reason = Browser.inputBox(name  + "\\n" + price + "円に設定します。理由を入力してください");
  
  priceUploader = new PriceUploader(sku, price);
  let response = priceUploader.uploadPrice()
  console.log(response);
  
  var priceSheet  = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("価格改定履歴");
  const lastRow = priceSheet.getLastRow()
  priceSheet.getRange(lastRow+1,1 ).setValue(sku)
  priceSheet.getRange(lastRow+1,2 ).setValue(name)
  priceSheet.getRange(lastRow+1,4 ).setValue(price)
  priceSheet.getRange(lastRow+1,5 ).setValue(reason)
    priceSheet.getRange(lastRow+1,6 ).setValue(new Date())


}

class PriceUploader extends Downloader{

  constructor(sku, price){
    let sellerid = "APS8L6SC4MEPF";
    let path = "/listings/2021-08-01/items/"+sellerid + "/" + sku;
    super(path);

    this.url = this.SP_API_URL + path;
    this.options.method = 'PATCH'
    const payload = {
      "productType": "PRODUCT",
      "patches": [{
        "op": "replace",
        "path": "/attributes/purchasable_offer",
        "value": [{
          "currency": "JPY",
        "our_price": [{
          "schedule": [{
            "value_with_tax": price
          }]
        }]
      }]
    }]}
    this.options.payload = JSON.stringify(payload)
  }

  uploadPrice(){
    this.setQueryParams([this.marketplaceIDs])
    console.log(this.options)
    let response = this.getData();
    return response;
  }
}
