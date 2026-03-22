class OrdersDownloader extends Downloader {
  getOrdersWithItems(startDate) {
    const allOrders = [];
    const createdAfter = "CreatedAfter=" + startDate.toISOString();
    const marketplaceIds = "MarketplaceIds=" + "A1VC38T7YXB528";
    let queryParams = [createdAfter, marketplaceIds];

    while (true) {
      this.setQueryParams(queryParams);
      const data = this.getData();
      const pageOrders = data.payload.Orders;

      if (pageOrders.length > 0) {
        const orderIds = pageOrders.map(o => o.AmazonOrderId);
        const itemsMap = this._fetchOrderItemsBatch(orderIds);
        for (const rawOrder of pageOrders) {
          const items = itemsMap[rawOrder.AmazonOrderId] || [];
          allOrders.push(new Order(rawOrder, items));
        }
      }

      const nextToken = data.payload.NextToken;
      if (!nextToken) {
        break;
      }
      queryParams = [createdAfter, marketplaceIds, "NextToken=" + encodeURIComponent(nextToken)];
    }

    return allOrders;
  }

  _fetchOrderItemsBatch(orderIds) {
    const orderItemsUrl = this.SP_API_URL + "/orders/v0/orders/";
    const requests = orderIds.map(orderId => ({
      url: orderItemsUrl + orderId + "/orderItems?" + this.marketplaceIDs,
      method: this.options.method,
      headers: this.options.headers,
      muteHttpExceptions: this.options.muteHttpExceptions,
    }));

    const batchSize = 5;
    const burstLimit = 30;
    const allResults = {};

    for (let i = 0; i < requests.length; i += batchSize) {
      const requestsSoFar = i;
      if (requestsSoFar === 0) {
        Utilities.sleep(2000);
      } else if (requestsSoFar < burstLimit) {
        Utilities.sleep(3000);
      } else {
        Utilities.sleep(15000);
      }

      const batch = requests.slice(i, i + batchSize);
      const batchOrderIds = orderIds.slice(i, i + batchSize);
      const responses = this._fetchBatchWithRetry(batch);

      for (let j = 0; j < responses.length; j++) {
        allResults[batchOrderIds[j]] = responses[j].payload.OrderItems;
      }
    }

    return allResults;
  }
}
