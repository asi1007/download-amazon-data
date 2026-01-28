class WeeklyCostSheet {
  constructor() {
    const SHEET_NAME = '週次集計';
    this.sheet = getOrCreateSheet(SHEET_NAME);
    this.headers = ['ASIN', '年月', '週', '売上個数', '売上金額', 'コスト', '広告費', '粗利益'];

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

  writeWeeklyCostData(weeklyData) {
    const lastRow = this.sheet.getLastRow();

    if (weeklyData.length > 0) {
      this.sheet.getRange(lastRow + 1, 1, weeklyData.length, weeklyData[0].length).setValues(weeklyData);
      Logger.log(`${weeklyData.length}件の週次データを書き込みました。`);
    }
  }
}
