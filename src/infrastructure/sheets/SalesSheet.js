class SalesSheet {
  constructor(sheetName) {
    this.sheetName = sheetName;
    this._refreshSheet();
    this.asinToRow = {};
    this.asinList = [];
  }

  _refreshSheet() {
    this.sheet = getSheetByName(this.sheetName);
    const HEADER_ROW = 4;
    const headers = this.sheet.getRange(HEADER_ROW, 1, 1, this.sheet.getLastColumn()).getValues()[0];
    const findColumn = (name) => {
      const index = headers.indexOf(name);
      if (index === -1) throw new Error(`ヘッダー「${name}」が見つかりません`);
      return index + 1;
    };
    this.START_COLUMN = findColumn("開始");
    this.PRICE_COLUMN = findColumn("自社価格");
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
    let totalAmount = 0;

    for (let i = 2; i < values.length; i++) {
      const asin = values[i - 1][0];
      if (this.asinList.includes(asin)) {
        writeData.push([salesNums[asin].unitCount]);
        totalAmount += salesNums[asin].totalSales.amount;
      } else {
        writeData.push([""]);
      }
    }

    if (writeData.length > 0) {
      this.sheet.getRange(2, this.START_COLUMN, writeData.length, 1).setValues(writeData);
    }

    this.sheet.getRange(3, this.START_COLUMN).setValue(totalAmount);

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
