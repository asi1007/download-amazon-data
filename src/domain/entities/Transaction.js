class Transaction {
  constructor(transaction) {
    this.type = transaction.transactionType;
    this.transactionStatus = transaction.transactionStatus;
    this.transaction = transaction;
    this.items = transaction.items.map(item => new Item(item));
  }
}

class Item {
  constructor(item) {
    this.asin = item.contexts[0].asin;
    this.quantity = item.contexts[0].quantityShipped;
    const productCharge = item.breakdowns[0].breakdownAmount;
    const tax = item.breakdowns[1].breakdownAmount;
    this.sales = productCharge + tax;

    const amazonFees = item.breakdowns[2];
    this.fees = amazonFees.breakdowns[0].breakdownAmount;
    this.comission = amazonFees.breakdowns[1].breakdownAmount;
  }
}
