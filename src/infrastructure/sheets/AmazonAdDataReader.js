class AmazonAdDataReader {
  constructor() {
    const SHEET_NAME = 'Amazon広告';
    this.sheet = getSheetByName(SHEET_NAME);
    this.HEADER_ROW = 1;

    this.COLUMNS = {
      ACQUISITION_DATE: 0,
      PERIOD_START: 1,
      PERIOD_END: 2,
      ASIN: 3,
      AD_SPEND: 4,
      IMPRESSIONS: 5,
      CLICKS: 6,
      SALES: 7,
      ORDERS: 8,
      ACOS: 9,
      CPC: 10,
      CTR: 11
    };
  }

  _getAllData() {
    if (!this.sheet) {
      return [];
    }
    const lastRow = this.sheet.getLastRow();
    if (lastRow <= this.HEADER_ROW) {
      return [];
    }
    const dataRange = this.sheet.getRange(
      this.HEADER_ROW + 1,
      1,
      lastRow - this.HEADER_ROW,
      12
    );
    return dataRange.getValues();
  }

  _rowToAmazonAdData(row) {
    const dataColumns = [
      row[this.COLUMNS.PERIOD_START],
      row[this.COLUMNS.ASIN],
      row[this.COLUMNS.AD_SPEND],
      row[this.COLUMNS.IMPRESSIONS],
      row[this.COLUMNS.CLICKS],
      row[this.COLUMNS.SALES],
      row[this.COLUMNS.ORDERS],
      row[this.COLUMNS.ACOS],
      row[this.COLUMNS.CPC],
      row[this.COLUMNS.CTR]
    ];
    return new AmazonAdData(dataColumns);
  }

  fetchAll() {
    const allData = this._getAllData();
    return allData
      .filter(row => row[this.COLUMNS.PERIOD_START])
      .map(row => this._rowToAmazonAdData(row));
  }

  fetchByPeriod(periodStart) {
    const allData = this.fetchAll();
    const targetDate = periodStart instanceof Date
      ? Utilities.formatDate(periodStart, 'Asia/Tokyo', 'yyyy-MM-dd')
      : periodStart;

    return allData.filter(data => {
      const dataDate = data.periodStart instanceof Date
        ? Utilities.formatDate(data.periodStart, 'Asia/Tokyo', 'yyyy-MM-dd')
        : data.periodStart;
      return dataDate === targetDate;
    });
  }

  fetchLatest() {
    const allData = this.fetchAll();
    if (allData.length === 0) {
      return [];
    }

    let latestDate = null;
    for (const data of allData) {
      const currentDate = data.periodStart instanceof Date
        ? data.periodStart
        : new Date(data.periodStart);
      if (!latestDate || currentDate > latestDate) {
        latestDate = currentDate;
      }
    }

    return this.fetchByPeriod(latestDate);
  }

  fetchByAsin(asin) {
    const allData = this.fetchAll();
    return allData.filter(data => data.asin === asin);
  }

  fetchLatestByAsin(asin) {
    const latestData = this.fetchLatest();
    return latestData.find(data => data.asin === asin) || null;
  }

  getAsinList() {
    const allData = this.fetchAll();
    const asinSet = new Set(allData.map(data => data.asin));
    return Array.from(asinSet);
  }

  getLatestPeriodDate() {
    const allData = this.fetchAll();
    if (allData.length === 0) {
      return null;
    }

    let latestDate = null;
    for (const data of allData) {
      const currentDate = data.periodStart instanceof Date
        ? data.periodStart
        : new Date(data.periodStart);
      if (!latestDate || currentDate > latestDate) {
        latestDate = currentDate;
      }
    }
    return latestDate;
  }
}
