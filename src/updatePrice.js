function updatePrice() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const row = sheet.getActiveCell().getRow();
  console.log(row);

  const HEADER_ROW = 4;
  const headers = sheet.getRange(HEADER_ROW, 1, 1, sheet.getLastColumn()).getValues()[0];
  const findColumn = (name) => {
    const index = headers.indexOf(name);
    if (index === -1) throw new Error(`ヘッダー「${name}」が見つかりません`);
    return index + 1;
  };

  const sku = sheet.getRange(row, findColumn("SKU")).getValue();
  const price = sheet.getRange(row, findColumn("自社価格")).getValue();
  const name = sheet.getRange(row, findColumn("商品名")).getValue();

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
