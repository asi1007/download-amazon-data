class UpdatePriceUseCase {
  constructor(salesSheet, skuDownloader, priceDownloader) {
    this.salesSheet = salesSheet;
    this.skuDownloader = skuDownloader;
    this.priceDownloader = priceDownloader;
  }

  execute() {
    const asintoSKU = this.skuDownloader.getASINtoSKUs();
    const asinList = this.salesSheet.getASINList();
    const asinToPrices = this.priceDownloader.getPricesOf(asinList, asintoSKU);
    this.salesSheet.getASINList();
    this.salesSheet.writePrice(asinToPrices);
  }
}
