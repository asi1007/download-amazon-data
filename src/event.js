function setupDownloadPricesTrigger() {
  const triggers = ScriptApp.getProjectTriggers();
  for (const trigger of triggers) {
    if (trigger.getHandlerFunction() === 'downloadPrices') {
      ScriptApp.deleteTrigger(trigger);
    }
  }
  ScriptApp.newTrigger('downloadPrices')
    .timeBased()
    .everyDays(1)
    .atHour(7)
    .create();
}

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
