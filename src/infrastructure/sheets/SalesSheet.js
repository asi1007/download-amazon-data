class SalesSheet {
  constructor(sheetName, cell) {
    const ASIN_SHEET_NAME = sheetName;
    this.START_COLUMN = getSheetByName("設定").getRange(cell).getValue();
    this.PRICE_COLUMN = getSheetByName("設定").getRange("B5").getValue();
    this.sheet = getSheetByName(ASIN_SHEET_NAME);
    const lastRow = this.sheet.getLastRow();
    this.asinRange = this.sheet.getRange(1, 1, lastRow);
    this.asinToRow = {};
    this.asinList = [];
  }

  getASINList() {
    let row = 1;
    for (const asinData of this.asinRange.getValues()) {
      if (asinData[0].length === 10) {
        this.asinList.push(asinData[0]);
        this.asinToRow[asinData[0]] = row;
      }
      row += 1;
    }
    return this.asinList;
  }

  writeSalesNums(salesNums) {
    this.sheet.insertColumnBefore(this.START_COLUMN);
    this.sheet.getRange(1, this.START_COLUMN).setValue(Utilities.formatDate(new Date, "JST", "yyyy/MM/dd"));
    this.sheet.getRange(1, this.START_COLUMN).setNumberFormat("dd");
    for (let i = 1; i < this.asinRange.getValues().length; i++) {
      const asin = this.asinRange.getValues()[i - 1][0];
      if (this.asinList.includes(asin)) {
        this.sheet.getRange(i, this.START_COLUMN).setValue(salesNums[asin].unitCount);
        this.sheet.getRange(i, this.START_COLUMN).setBackground(null);
      }
    }
  }

  writePrice(asintoPrices) {
    for (const asin in asintoPrices) {
      if (this.asinList.includes(asin)) {
        const row = this.asinToRow[asin];
        this.sheet.getRange(row, this.START_COLUMN).setNote(asintoPrices[asin]);
        this.sheet.getRange(row, this.START_COLUMN).setBackground(null);
        const price = asintoPrices[asin];
        const prevPrice = this.sheet.getRange(row, this.START_COLUMN + 1).getNote();
        if (price < prevPrice) {
          this.sheet.getRange(row, this.START_COLUMN).setBackground("red");
        } else if (price > prevPrice) {
          this.sheet.getRange(row, this.START_COLUMN).setBackground("aqua");
        }
        this.sheet.getRange(row, this.PRICE_COLUMN).setValue(price);
      }
    }
  }
}
