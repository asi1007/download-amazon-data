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

    const values = this.asinRange.getValues();
    const writeData = [];

    for (let i = 1; i < values.length; i++) {
      const asin = values[i - 1][0];
      if (this.asinList.includes(asin)) {
        writeData.push([salesNums[asin].unitCount]);
      } else if (i === 1) {
        writeData.push([Utilities.formatDate(new Date(), "JST", "yyyy/MM/dd")]);
      } else {
        writeData.push([""]);
      }
    }

    if (writeData.length > 0) {
      this.sheet.getRange(1, this.START_COLUMN, writeData.length, 1).setValues(writeData);
    }
    this.sheet.getRange(1, this.START_COLUMN).setNumberFormat("dd");
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
