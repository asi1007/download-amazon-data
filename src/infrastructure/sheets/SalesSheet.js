class SalesSheet {
  constructor(sheetName, cell) {
    this.sheetName = sheetName;
    this.configCell = cell;
    this._refreshSheet();
    this.asinToRow = {};
    this.asinList = [];
  }

  _refreshSheet() {
    this.START_COLUMN = getSheetByName("設定").getRange(this.configCell).getValue();
    this.PRICE_COLUMN = getSheetByName("設定").getRange("B5").getValue();
    this.sheet = getSheetByName(this.sheetName);
    const lastRow = this.sheet.getLastRow();
    this.asinRange = this.sheet.getRange(1, 1, lastRow);
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
    this._refreshSheet();
    const filter = this.sheet.getFilter();
    let filterRange = null;
    if (filter) {
      filterRange = filter.getRange();
      filter.remove();
    }

    const HEADER_ROW = 4;
    const date = Utilities.formatDate(new Date(), "JST", "yyyy/MM/dd");
    this.sheet.insertColumnBefore(this.START_COLUMN);
    this.sheet.getRange(1, this.START_COLUMN).setValue(date);
    this.sheet.getRange(1, this.START_COLUMN).setNumberFormat("dd");
    this.sheet.getRange(HEADER_ROW, this.START_COLUMN).setValue(date);
    this.sheet.getRange(HEADER_ROW, this.START_COLUMN).setNumberFormat("dd");

    const values = this.asinRange.getValues();
    const writeData = [];

    for (let i = 2; i < values.length; i++) {
      const asin = values[i - 1][0];
      if (this.asinList.includes(asin)) {
        writeData.push([salesNums[asin].unitCount]);
      } else {
        writeData.push([""]);
      }
    }

    if (writeData.length > 0) {
      this.sheet.getRange(2, this.START_COLUMN, writeData.length, 1).setValues(writeData);
    }

    if (filterRange) {
      this.sheet.getRange(
        filterRange.getRow(),
        filterRange.getColumn(),
        filterRange.getNumRows(),
        filterRange.getNumColumns() + 1
      ).createFilter();
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
