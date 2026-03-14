class RealtimeSalesSheet {
  constructor() {
    this.sheet = getSheetByName('売上/今');
    this.asinList = [];
  }

  getAsinList() {
    const lastRow = this.sheet.getLastRow();
    const values = this.sheet.getRange(1, 1, lastRow).getValues();

    this.asinList = [];
    for (let i = 1; i < values.length; i++) {
      const asin = values[i][0];
      if (asin && asin.length === 10) {
        this.asinList.push(asin);
      }
    }
    return this.asinList;
  }

  writeRealtimeSales(salesMap) {
    const writeData = this.asinList.map(asin => {
      const sales = salesMap[asin] || { unitCount: 0, totalAmount: 0 };
      return [sales.unitCount, sales.totalAmount];
    });

    if (writeData.length > 0) {
      this.sheet.getRange(2, 2, writeData.length, 2).setValues(writeData);
    }
  }
}
