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
}

function downloadTransactions() {
  const today = new Date();
  const startDate = new Date();
  const endDate = new Date();
  startDate.setDate(today.getDate() - 4);
  startDate.setHours(0, 0, 0, 0);
  endDate.setDate(today.getDate() - 3);
  endDate.setHours(0, 0, 0, 0);
  const downloader = new TransactionDownloader('/finances/2024-06-19/transactions');
  downloader.getTransactions(startDate, endDate);
}
