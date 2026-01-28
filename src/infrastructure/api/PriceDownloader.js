class PriceDownloader extends Downloader {
  getPriceOf(asin) {
    const queryParams = [
      this.marketplaceID,
      "ItemType=Asin",
      "Asins=" + asin
    ];
    this.setQueryParams(queryParams);
    const data = this.getData();
    return data.payload;
  }

  getPricesOf(asinList, asintoSKU) {
    const asintoPrices = {};
    for (const asin of asinList) {
      const priceData = this.getPriceOf(asin);
      if (priceData && priceData.length > 0 && priceData[0].Product.CompetitivePricing.CompetitivePrices.length > 0) {
        asintoPrices[asin] = priceData[0].Product.CompetitivePricing.CompetitivePrices[0].Price.LandedPrice.Amount;
      }
    }
    return asintoPrices;
  }
}
