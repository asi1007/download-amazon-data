class RealtimeSalesResult {
  constructor(asin, unitCount, totalAmount) {
    this.asin = asin;
    this.unitCount = unitCount || 0;
    this.totalAmount = totalAmount || 0;
  }

  addSale(quantity, amount) {
    this.unitCount += quantity;
    this.totalAmount += amount;
  }
}
