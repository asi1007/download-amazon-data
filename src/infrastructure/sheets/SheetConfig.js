const SHEET_ID = '1Z3P0iL19r3gA9-NG8x2e_42pGhrEs_wFMLWLbFvReAw';

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
