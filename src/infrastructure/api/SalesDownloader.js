class SalesDownloader extends Downloader {
  buildQueryParams(asin, type, startDate, endDate) {
    const queryParams = [this.marketplaceIDs];
    queryParams.push("interval=" + startDate.toISOString() + "--" + endDate.toISOString());
    queryParams.push("granularity=" + type);
    queryParams.push("granularityTimeZone=Asia/Tokyo");
    queryParams.push("asin=" + asin);
    return queryParams;
  }

  getSalesInfosOf(asinList, type, startDate, endDate) {
    let count = 0;
    const asinSalesNums = {};
    for (const asin of asinList) {
      const salesData = this.getSalesInfoOf(asin, type, startDate, endDate);
      asinSalesNums[asin] = salesData;
      count += 1;
      console.log(String(count) + "商品目");
    }
    return asinSalesNums;
  }

  getSalesInfoOf(asin, type, startDate, endDate) {
    const queryParams = this.buildQueryParams(asin, type, startDate, endDate);
    this.setQueryParams(queryParams);
    const salesData = this.getData();
    return salesData.payload[0];
  }
}
