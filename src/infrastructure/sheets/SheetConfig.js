const SHEET_ID = '1aAliE0u45YbMwcBMczrLrG82MRMjOVc999L3GWCUENE';

function getSpreadsheet() {
  return SpreadsheetApp.openById(SHEET_ID);
}

function getSheetByName(sheetName) {
  return getSpreadsheet().getSheetByName(sheetName);
}

function getOrCreateSheet(sheetName) {
  const spreadsheet = getSpreadsheet();
  let sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
  }
  return sheet;
}
