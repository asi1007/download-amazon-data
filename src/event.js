function onSelectionChange(e) {
  const sheet = e.source.getActiveSheet();
  const sheetName = sheet.getName();

  if (sheetName === "売上/日") {
    const range = e.range;
    const row = range.getRow();
    const aValue = sheet.getRange(row, 1).getValue();
    sheet.getRange("E2").setValue(aValue);
  }
}
