class InventorySheet {
  constructor() {
    const SHEET_NAME = '納品状況';
    this.sheet = getOrCreateSheet(SHEET_NAME);
    this.headers = [
      'ASIN',
      'SKU',
      '販売可能\n(fulfillableQuantity)',
      '納品準備中\n(inboundWorkingQuantity)',
      '納品中\n(inboundShippedQuantity)',
      '受領中\n(inboundReceivingQuantity)',
      '予約済合計\n(totalReservedQuantity)',
      '注文確保\n(pendingCustomerOrderQuantity)',
      '転送中\n(pendingTransshipmentQuantity)',
      '処理中\n(fcProcessingQuantity)',
      '最終更新日時'
    ];
  }

  initializeSheet() {
    this.sheet.getRange(1, 1, 1, this.headers.length).setValues([this.headers]);
    this._formatHeaderRow();
    this._setColumnWidths();
    this.sheet.setRowHeight(1, 60);
  }

  _formatHeaderRow() {
    const headerRange = this.sheet.getRange(1, 1, 1, this.headers.length);
    headerRange.setFontWeight('bold');
    headerRange.setBackground('#4CAF50');
    headerRange.setFontColor('#FFFFFF');
    headerRange.setHorizontalAlignment('center');
    headerRange.setVerticalAlignment('middle');
    headerRange.setWrap(true);
  }

  _setColumnWidths() {
    this.sheet.setColumnWidth(1, 100);
    this.sheet.setColumnWidth(2, 150);
    for (let i = 3; i <= 10; i++) {
      this.sheet.setColumnWidth(i, 100);
    }
    this.sheet.setColumnWidth(11, 150);
  }

  writeInventoryData(inventoryData) {
    this.sheet.clear();
    this.sheet.getRange(1, 1, 1, this.headers.length).setValues([this.headers]);
    this._formatHeaderRow();
    this.sheet.setRowHeight(1, 60);

    const rows = [];
    const now = Utilities.formatDate(new Date(), "JST", "yyyy/MM/dd HH:mm:ss");

    for (const inventory of inventoryData) {
      const summary = new InventorySummary(inventory);
      rows.push(summary.toArray(now));
    }

    this._setColumnWidths();

    if (rows.length > 0) {
      this.sheet.getRange(2, 1, rows.length, 11).setValues(rows);
      this._formatDataRows(rows.length);
    }

    Logger.log(`${rows.length}件の在庫データを書き込みました。`);
  }

  _formatDataRows(rowCount) {
    for (let i = 3; i <= 10; i++) {
      this.sheet.getRange(2, i, rowCount, 1).setNumberFormat('#,##0');
      this.sheet.getRange(2, i, rowCount, 1).setHorizontalAlignment('right');
    }

    for (let i = 0; i < rowCount; i++) {
      const rowNum = i + 2;
      const color = i % 2 === 0 ? '#F5F5F5' : '#FFFFFF';
      this.sheet.getRange(rowNum, 1, 1, 11).setBackground(color);
    }
  }
}
