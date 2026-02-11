class Downloader {
  constructor(path) {
    this.SP_API_URL = "https://sellingpartnerapi-fe.amazon.com";
    this.authToken = getAuthToken();
    this.options = {
      muteHttpExceptions: true,
      method: 'get',
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-amz-access-token": this.authToken,
      }
    };
    this.marketplaceIDs = "marketplaceIds=A1VC38T7YXB528";
    this.marketplaceID = "MarketplaceId=A1VC38T7YXB528";
    this.url = this.SP_API_URL + path;
  }

  setQueryParams(queryParams) {
    this.queryParams = queryParams;
  }

  buildRequestUrl(queryParams) {
    return this.url + "?" + queryParams.join("&");
  }

  getData() {
    this.urlquery = this.url + "?" + this.queryParams.join("&");
    Utilities.sleep(4500);
    console.log(this.urlquery);
    const response = UrlFetchApp.fetch(this.urlquery, this.options);
    const data = JSON.parse(response.getContentText());
    return data;
  }

  fetchAll(queryParamsList, batchSize = 5) {
    const results = [];
    for (let i = 0; i < queryParamsList.length; i += batchSize) {
      if (i > 0) {
        Utilities.sleep(4000);
      }
      const batch = queryParamsList.slice(i, i + batchSize);
      const requests = batch.map(params => ({
        url: this.buildRequestUrl(params),
        method: this.options.method,
        headers: this.options.headers,
        muteHttpExceptions: this.options.muteHttpExceptions
      }));
      console.log("Batch " + (Math.floor(i / batchSize) + 1) + ": " + batch.length + "件リクエスト");
      const responses = UrlFetchApp.fetchAll(requests);
      for (const response of responses) {
        results.push(JSON.parse(response.getContentText()));
      }
    }
    return results;
  }
}
