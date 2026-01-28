class InventorySummariesDownloader extends Downloader {
  getAllInventorySummaries(startDateTime) {
    let allInventories = [];

    let queryParams = [
      this.marketplaceIDs,
      "granularityType=Marketplace",
      "granularityId=A1VC38T7YXB528",
      "details=true"
    ];

    if (startDateTime) {
      queryParams.push("startDateTime=" + startDateTime.toISOString());
    }

    this.setQueryParams(queryParams);
    let data = this.getData();

    if (data.payload && data.payload.inventorySummaries) {
      allInventories = allInventories.concat(data.payload.inventorySummaries);
    }

    let nextToken = data.pagination ? data.pagination.nextToken : null;
    while (nextToken) {
      queryParams = [
        this.marketplaceIDs,
        "granularityType=Marketplace",
        "granularityId=A1VC38T7YXB528",
        "details=true",
        "nextToken=" + encodeURIComponent(nextToken)
      ];

      if (startDateTime) {
        queryParams.push("startDateTime=" + startDateTime.toISOString());
      }

      this.setQueryParams(queryParams);
      data = this.getData();
      if (data.payload && data.payload.inventorySummaries) {
        allInventories = allInventories.concat(data.payload.inventorySummaries);
      }
      nextToken = data.pagination ? data.pagination.nextToken : null;
    }

    return allInventories;
  }
}
