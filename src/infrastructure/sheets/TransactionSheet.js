class TransactionSheet {
  constructor() {
    const SHEET_NAME = 'transaction';
    this.sheet = getOrCreateSheet(SHEET_NAME);
    this.headers = ['日付', 'ASIN', '数量', '売上', '手数料', 'コミッション', '純利益'];

    if (this.sheet.getLastRow() === 0) {
      this.initializeSheet();
    }
  }

  initializeSheet() {
    this.sheet.getRange(1, 1, 1, this.headers.length).setValues([this.headers]);
    const headerRange = this.sheet.getRange(1, 1, 1, this.headers.length);
    headerRange.setFontWeight('bold');
    headerRange.setBackground('#4CAF50');
    headerRange.setFontColor('#FFFFFF');
  }

  writeTransactionData(rows) {
    const lastRow = this.sheet.getLastRow();

    if (rows.length > 0) {
      this.sheet.getRange(lastRow + 1, 1, rows.length, rows[0].length).setValues(rows);
      Logger.log(`${rows.length}件のトランザクションデータを書き込みました。`);
    }
  }
}
