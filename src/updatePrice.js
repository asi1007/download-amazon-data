function updatePrice() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const row = sheet.getActiveCell().getRow();
  console.log(row);

  const settingSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("設定");
  const sku = sheet.getRange(row, settingSheet.getRange("B8").getValue()).getValue();
  const price = sheet.getRange(row, settingSheet.getRange("B5").getValue()).getValue();
  const name = sheet.getRange(row, settingSheet.getRange("B9").getValue()).getValue();

  const reason = Browser.inputBox(name + "\\n" + price + "円に設定します。理由を入力してください");

  const priceUploader = new PriceUploader(sku, price);
  const response = priceUploader.uploadPrice();
  console.log(response);

  const priceSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("価格改定履歴");
  const lastRow = priceSheet.getLastRow();
  priceSheet.getRange(lastRow + 1, 1).setValue(sku);
  priceSheet.getRange(lastRow + 1, 2).setValue(name);
  priceSheet.getRange(lastRow + 1, 4).setValue(price);
  priceSheet.getRange(lastRow + 1, 5).setValue(reason);
  priceSheet.getRange(lastRow + 1, 6).setValue(new Date());
}
