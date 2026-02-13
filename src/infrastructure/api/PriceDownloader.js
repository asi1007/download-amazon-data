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

  getPricesOf(asinList) {
    const BATCH_SIZE = 20;
    const queryParamsList = [];
    for (let i = 0; i < asinList.length; i += BATCH_SIZE) {
      const batch = asinList.slice(i, i + BATCH_SIZE);
      queryParamsList.push([
        this.marketplaceID,
        "ItemType=Asin",
        ...batch.map(asin => "Asins=" + asin)
      ]);
    }
    const responses = this.fetchAll(queryParamsList);
    const asintoPrices = {};
    for (const res of responses) {
      if (!res.payload) continue;
      for (const item of res.payload) {
        const asin = item.ASIN;
        const prices = item.Product.CompetitivePricing.CompetitivePrices;
        if (prices.length > 0) {
          asintoPrices[asin] = prices[0].Price.LandedPrice.Amount;
        }
      }
    }
    return asintoPrices;
  }
}
