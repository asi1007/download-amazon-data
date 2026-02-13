class DownloadTransactionUseCase {
  constructor(transactionDownloader, transactionSheet) {
    this.transactionDownloader = transactionDownloader;
    this.transactionSheet = transactionSheet;
  }

  execute() {
    const { startDate, endDate } = this._getLastWeekRange();
    const transactions = this.transactionDownloader.getAllTransactions(startDate, endDate);
    const aggregated = this._aggregateByAsinAndDate(transactions);
    const rows = this._toSheetRows(aggregated);
    this.transactionSheet.writeTransactionData(rows);
  }

  _getLastWeekRange() {
    const today = new Date();
    const dayOfWeek = today.getDay();
    const daysToLastMonday = dayOfWeek === 0 ? 13 : dayOfWeek + 6;
    const startDate = new Date(today);
    startDate.setDate(today.getDate() - daysToLastMonday);
    startDate.setHours(0, 0, 0, 0);

    const endDate = new Date(startDate);
    endDate.setDate(startDate.getDate() + 7);
    endDate.setHours(0, 0, 0, 0);

    return { startDate, endDate };
  }

  _aggregateByAsinAndDate(transactions) {
    const map = {};

    for (const transaction of transactions) {
      const dateKey = this._formatDate(transaction.postedDate);

      for (const item of transaction.items) {
        const key = dateKey + '_' + item.asin;

        if (!map[key]) {
          map[key] = {
            date: dateKey,
            asin: item.asin,
            quantity: 0,
            sales: 0,
            fees: 0,
            commission: 0,
          };
        }

        map[key].quantity += item.quantity;
        map[key].sales += item.sales;
        map[key].fees += item.fees;
        map[key].commission += item.comission;
      }
    }

    return Object.values(map);
  }

  _formatDate(isoDateString) {
    const date = new Date(isoDateString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return year + '/' + month + '/' + day;
  }

  _toSheetRows(aggregatedData) {
    return aggregatedData
      .sort((a, b) => a.date.localeCompare(b.date) || a.asin.localeCompare(b.asin))
      .map(row => {
        const netProfit = row.sales - row.fees - row.commission;
        return [row.date, row.asin, row.quantity, row.sales, row.fees, row.commission, netProfit];
      });
  }
}
