class CostDataReader {
  constructor() {
    const SHEET_NAME = '売上/日';
    this.sheet = getSheetByName(SHEET_NAME);
    this.HEADER_ROW = 4;

    this.COLUMNS = {
      ASIN: 1,
      LOCAL_PRICE: 57,
      SHIP: 58,
      TAX: 59,
      EXTRA: 60,
      VARIABLE_FEE: 72,
      FIXED_FEE: 73,
      PROFIT: 75
    };
  }

  getASINList() {
    const lastRow = this.sheet.getLastRow();
    const asinRange = this.sheet.getRange(1, this.COLUMNS.ASIN, lastRow);
    const asinValues = asinRange.getValues();

    const asinList = [];
    const asinToRow = {};

    for (let i = 0; i < asinValues.length; i++) {
      const asin = asinValues[i][0];
      if (asin && asin.length === 10) {
        asinList.push(asin);
        asinToRow[asin] = i + 1;
      }
    }

    this.asinList = asinList;
    this.asinToRow = asinToRow;
    return asinList;
  }

  getCostDataForASIN(asin) {
    if (!this.asinToRow) {
      this.getASINList();
    }

    const row = this.asinToRow[asin];
    if (!row) {
      return null;
    }

    return new CostData({
      asin: asin,
      localPrice: this.sheet.getRange(row, this.COLUMNS.LOCAL_PRICE).getValue() || 0,
      shipCost: this.sheet.getRange(row, this.COLUMNS.SHIP).getValue() || 0,
      taxCost: this.sheet.getRange(row, this.COLUMNS.TAX).getValue() || 0,
      extraCost: this.sheet.getRange(row, this.COLUMNS.EXTRA).getValue() || 0,
      variableFee: this.sheet.getRange(row, this.COLUMNS.VARIABLE_FEE).getValue() || 0,
      fixedFee: this.sheet.getRange(row, this.COLUMNS.FIXED_FEE).getValue() || 0,
      profit: this.sheet.getRange(row, this.COLUMNS.PROFIT).getValue() || 0
    });
  }

  getAllCostData() {
    if (!this.asinList) {
      this.getASINList();
    }

    const lastRow = this.sheet.getLastRow();

    const localPriceData = this.sheet.getRange(1, this.COLUMNS.LOCAL_PRICE, lastRow).getValues();
    const shipData = this.sheet.getRange(1, this.COLUMNS.SHIP, lastRow).getValues();
    const taxData = this.sheet.getRange(1, this.COLUMNS.TAX, lastRow).getValues();
    const extraData = this.sheet.getRange(1, this.COLUMNS.EXTRA, lastRow).getValues();
    const variableFeeData = this.sheet.getRange(1, this.COLUMNS.VARIABLE_FEE, lastRow).getValues();
    const fixedFeeData = this.sheet.getRange(1, this.COLUMNS.FIXED_FEE, lastRow).getValues();
    const profitData = this.sheet.getRange(1, this.COLUMNS.PROFIT, lastRow).getValues();

    const result = {};

    for (const asin of this.asinList) {
      const row = this.asinToRow[asin];
      const idx = row - 1;

      result[asin] = new CostData({
        asin: asin,
        localPrice: localPriceData[idx][0] || 0,
        shipCost: shipData[idx][0] || 0,
        taxCost: taxData[idx][0] || 0,
        extraCost: extraData[idx][0] || 0,
        variableFee: variableFeeData[idx][0] || 0,
        fixedFee: fixedFeeData[idx][0] || 0,
        profit: profitData[idx][0] || 0
      });
    }

    return result;
  }
}
