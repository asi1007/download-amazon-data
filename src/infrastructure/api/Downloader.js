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

  fetchAll(queryParamsList, batchSize = 2) {
    const results = [];
    for (let i = 0; i < queryParamsList.length; i += batchSize) {
      if (i > 0) {
        Utilities.sleep(6000);
      }
      const batch = queryParamsList.slice(i, i + batchSize);
      const requests = batch.map(params => ({
        url: this.buildRequestUrl(params),
        method: this.options.method,
        headers: this.options.headers,
        muteHttpExceptions: this.options.muteHttpExceptions
      }));
      console.log("Batch " + (Math.floor(i / batchSize) + 1) + ": " + batch.length + "件リクエスト");
      const batchResults = this._fetchBatchWithRetry(requests);
      results.push(...batchResults);
    }
    return results;
  }

  _fetchBatchWithRetry(requests, maxRetries = 3) {
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const responses = UrlFetchApp.fetchAll(requests);
        const results = [];
        for (const response of responses) {
          const text = response.getContentText();
          if (text.includes("Bandwidth quota exceeded") || text.includes("QuotaExceeded")) {
            console.log("Rate limit response: " + text.substring(0, 500));
            throw new Error("Rate limit exceeded");
          }
          results.push(JSON.parse(text));
        }
        return results;
      } catch (e) {
        const waitTime = Math.pow(2, attempt) * 5000;
        console.log("リトライ " + (attempt + 1) + "/" + maxRetries + " - " + waitTime + "ms待機: " + e.message);
        if (attempt === maxRetries - 1) {
          throw e;
        }
        Utilities.sleep(waitTime);
      }
    }
  }
}
