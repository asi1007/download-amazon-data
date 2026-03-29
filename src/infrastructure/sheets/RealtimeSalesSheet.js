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
    for (let i = 1; i < values.length; i++) {
      const asin = values[i][0];
      if (asin && asin.length === 10) {
        this.asinList.push(asin);
        this.asinToRow[asin] = i + 1;
      }
    }
    return this.asinList;
  }

  writeRealtimeSales(salesMap) {
    const lastRow = this.sheet.getLastRow();
    const writeData = [];
    for (let row = 2; row <= lastRow; row++) {
      writeData.push([null, null]);
    }

    for (const asin of this.asinList) {
      const sales = salesMap[asin] || { unitCount: 0, totalAmount: 0 };
      const row = this.asinToRow[asin];
      writeData[row - 2] = [sales.unitCount, sales.totalAmount];
    }

    if (writeData.length > 0) {
      this.sheet.getRange(2, 3, writeData.length, 2).setValues(writeData);
    }
  }
}
