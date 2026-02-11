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
    const queryParamsList = asinList.map(asin =>
      this.buildQueryParams(asin, type, startDate, endDate)
    );
    const responses = this.fetchAll(queryParamsList);
    const asinSalesNums = {};
    asinList.forEach((asin, index) => {
      asinSalesNums[asin] = responses[index].payload[0];
    });
    console.log(asinList.length + "商品の売上データを一括取得完了");
    return asinSalesNums;
  }

  getSalesInfoOf(asin, type, startDate, endDate) {
    const queryParams = this.buildQueryParams(asin, type, startDate, endDate);
    this.setQueryParams(queryParams);
    const salesData = this.getData();
    return salesData.payload[0];
  }
}
