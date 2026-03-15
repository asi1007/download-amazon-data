class OrdersDownloader extends Downloader {
  searchOrders(startDate) {
    const allOrders = [];
    const createdAfter = "CreatedAfter=" + startDate.toISOString();
    const marketplaceIds = "MarketplaceIds=" + "A1VC38T7YXB528";
    let queryParams = [createdAfter, marketplaceIds];

    while (true) {
      this.setQueryParams(queryParams);
      const data = this.getData();
      const orders = data.payload.Orders;
      allOrders.push(...orders);

      const nextToken = data.payload.NextToken;
      if (!nextToken) {
        break;
      }
      queryParams = [createdAfter, marketplaceIds, "NextToken=" + nextToken];
    }

    return allOrders;
  }

  getOrderItemsForOrders(orderIds) {
    const orderItemsUrl = this.SP_API_URL + "/orders/v0/orders/";

    const requests = orderIds.map(orderId => ({
      url: orderItemsUrl + orderId + "/orderItems?" + this.marketplaceIDs,
      method: this.options.method,
      headers: this.options.headers,
      muteHttpExceptions: this.options.muteHttpExceptions,
    }));

    const batchSize = 10;
    const allResults = {};

    for (let i = 0; i < requests.length; i += batchSize) {
      if (i > 0) {
        Utilities.sleep(6000);
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

  getOrdersWithItems(startDate) {
    const rawOrders = this.searchOrders(startDate);
    const orderIds = rawOrders.map(order => order.AmazonOrderId);

    if (orderIds.length === 0) {
      return [];
    }

    const orderItemsMap = this.getOrderItemsForOrders(orderIds);

    return rawOrders.map(rawOrder => {
      const items = orderItemsMap[rawOrder.AmazonOrderId] || [];
      return new Order(rawOrder, items);
    });
  }
}
