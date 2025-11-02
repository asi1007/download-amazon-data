function onSelectionChange(e) {
  const sheet = e.source.getActiveSheet();  // アクティブなシートを取得
  const sheetName = sheet.getName();

  if (sheetName === "売上/日") {
    const range = e.range;                    // 選択されたセル範囲
    const row = range.getRow();               // 行番号を取得

    // A列の値を取得
    const aValue = sheet.getRange(row, 1).getValue();

    // E2セルに値を設定
    sheet.getRange("E2").setValue(aValue);
  }
}