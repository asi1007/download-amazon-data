class AmazonAdData {
  constructor(row) {
    this.periodStart = row[0];
    this.asin = row[1];
    this.adSpend = row[2] || 0;
    this.impressions = row[3] || 0;
    this.clicks = row[4] || 0;
    this.sales = row[5] || 0;
    this.orders = row[6] || 0;
    this.acos = row[7] || 0;
    this.cpc = row[8] || 0;
    this.ctr = row[9] || 0;
  }

  toArray() {
    return [
      this.periodStart,
      this.asin,
      this.adSpend,
      this.impressions,
      this.clicks,
      this.sales,
      this.orders,
      this.acos,
      this.cpc,
      this.ctr
    ];
  }

  toObject() {
    return {
      periodStart: this.periodStart,
      asin: this.asin,
      adSpend: this.adSpend,
      impressions: this.impressions,
      clicks: this.clicks,
      sales: this.sales,
      orders: this.orders,
      acos: this.acos,
      cpc: this.cpc,
      ctr: this.ctr
    };
  }
}
