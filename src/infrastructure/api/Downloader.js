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

  getData() {
    this.urlquery = this.url + "?" + this.queryParams.join("&");
    Utilities.sleep(4500);
    console.log(this.urlquery);
    const response = UrlFetchApp.fetch(this.urlquery, this.options);
    const data = JSON.parse(response.getContentText());
    return data;
  }
}
