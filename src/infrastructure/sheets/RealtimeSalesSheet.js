class RealtimeSalesSheet {
  constructor() {
    this.sheet = getSheetByName('売上/今');
    this.asinList = [];
    this.asinToRow = {};
  }

  getAsinList() {
    const lastRow = this.sheet.getLastRow();
    const values = this.sheet.getRange(1, 1, lastRow).getValues();

    this.asinList = [];
    this.asinToRow = {};
    for (let i = 0; i < values.length; i++) {
      const asin = values[i][0];
      if (asin && String(asin).length === 10) {
        this.asinList.push(String(asin));
        this.asinToRow[String(asin)] = i + 1;
      }
    }
    return this.asinList;
  }

  writeRealtimeSales(salesMap) {
    const lastRow = this.sheet.getLastRow();
    const asinValues = this.sheet.getRange(1, 1, lastRow).getValues();
    const writeData = [];

    for (let i = 0; i < asinValues.length; i++) {
      const asin = String(asinValues[i][0]);
      if (salesMap[asin]) {
        writeData.push([salesMap[asin].unitCount, salesMap[asin].totalAmount]);
      } else {
        writeData.push(["", ""]);
      }
    }

    if (writeData.length > 0) {
      this.sheet.getRange(1, 3, writeData.length, 2).setValues(writeData);
    }
  }
}
