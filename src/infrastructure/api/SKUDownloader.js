class SKUDownloader extends Downloader {
  getASINtoSKUs() {
    const asinToSku = {};
    this.setQueryParams([this.marketplaceIDs]);
    let nextToken;
    do {
      const response = this.getData();
      if (response.items && response.items.length > 0) {
        response.items.forEach(item => {
          asinToSku[item.summaries[0].asin] = item.sku;
        });
      }
      nextToken = response.pagination.nextToken;
      this.setQueryParams([this.marketplaceIDs, "pageToken=" + encodeURIComponent(nextToken)]);
    } while (nextToken !== undefined);
    return asinToSku;
  }
}
