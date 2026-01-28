class CostData {
  constructor(data) {
    this.asin = data.asin;
    this.imageUrl = data.imageUrl || '';
    this.localPrice = data.localPrice || 0;
    this.shipCost = data.shipCost || 0;
    this.taxCost = data.taxCost || 0;
    this.extraCost = data.extraCost || 0;
    this.variableFee = data.variableFee || 0;
    this.fixedFee = data.fixedFee || 0;
    this.profit = data.profit || 0;
    this.adCost = data.adCost || 0;
  }

  getTotalUnitCost() {
    return this.localPrice + this.shipCost + this.taxCost +
           this.extraCost + this.variableFee + this.fixedFee;
  }
}
