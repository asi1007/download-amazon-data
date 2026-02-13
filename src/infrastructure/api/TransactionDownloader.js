class TransactionDownloader extends Downloader {
  getTransactions(startDay, endDay) {
    const start = "postedAfter=" + startDay.toISOString();
    const end = "postedBefore=" + endDay.toISOString();
    this.setQueryParams([start, end]);
    const data = this.getData();

    const nextToken = data.payload.nextToken;
    let transactions = data.payload.transactions;
    transactions = transactions.filter(
      transaction => transaction.transactionType === "Shipment" && transaction.transactionStatus === "RELEASED"
    );
    const transactionData = transactions.map(transaction => new Transaction(transaction));
    console.log(data);
    return transactionData;
  }

  getAllTransactions(startDay, endDay) {
    const allTransactions = [];
    const start = "postedAfter=" + startDay.toISOString();
    const end = "postedBefore=" + endDay.toISOString();
    let queryParams = [start, end];

    while (true) {
      this.setQueryParams(queryParams);
      const data = this.getData();

      const transactions = data.payload.transactions.filter(
        transaction => transaction.transactionType === "Shipment" && transaction.transactionStatus === "RELEASED"
      );
      const transactionData = transactions.map(transaction => new Transaction(transaction));
      allTransactions.push(...transactionData);

      const nextToken = data.payload.nextToken;
      if (!nextToken) {
        break;
      }
      queryParams = [start, end, "nextToken=" + nextToken];
    }

    return allTransactions;
  }
}
