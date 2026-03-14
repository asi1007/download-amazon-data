# リアルタイム売上モニタリング Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 10分間隔でOrders APIからASIN別の本日売上個数・売上価格を取得し、「売上/今」シートに上書き記録する

**Architecture:** DDDパターンに従い、Order エンティティ + RealtimeSalesResult 値オブジェクト + OrderRepository + OrdersDownloader + RealtimeSalesSheet + UpdateRealtimeSalesUseCase を作成。既存の Downloader 基底クラスを継承し、TransactionDownloader のページネーションパターンを踏襲。

**Tech Stack:** JavaScript (Google Apps Script), Jest, clasp

**Spec:** `docs/superpowers/specs/2026-03-15-realtime-sales-design.md`

**Note:** 記録先スプレッドシートID `1Z3P0iL19r3gA9-NG8x2e_42pGhrEs_wFMLWLbFvReAw` は `src/infrastructure/sheets/SheetConfig.js` の `SHEET_ID` と同一であることを確認済み。`getSheetByName('売上/今')` でアクセス可能。

---

## Chunk 1: ドメイン層（エンティティ・値オブジェクト・リポジトリ）

### Task 1: Order エンティティ

**Files:**
- Create: `src/domain/entities/Order.js`
- Test: `tests/getSPAPIdata.test.js`（既存ファイルにテスト追加）

- [ ] **Step 1: テストファイルにソースファイルパスを追加**

`tests/getSPAPIdata.test.js` の `sourceFiles` 配列と `gasExports` 配列に新しいファイルを登録する。ただしこの時点ではファイルが存在しないため、この手順は Task 1 の実装完了後に行う。

- [ ] **Step 2: Order エンティティの失敗するテストを書く**

`tests/getSPAPIdata.test.js` の末尾に以下を追加:

```javascript
describe('Order', () => {
  test('constructor maps API response to properties', () => {
    const apiResponse = {
      AmazonOrderId: '503-1234567-1234567',
      OrderStatus: 'Shipped',
      PurchaseDate: '2026-03-15T10:30:00Z',
    };
    const orderItems = [
      {
        ASIN: 'B00EXAMPLE',
        QuantityOrdered: 2,
        ItemPrice: { CurrencyCode: 'JPY', Amount: '3000' },
      },
      {
        ASIN: 'B00EXAMPLF',
        QuantityOrdered: 1,
        ItemPrice: { CurrencyCode: 'JPY', Amount: '1500' },
      },
    ];

    const order = new global.Order(apiResponse, orderItems);

    expect(order.orderId).toBe('503-1234567-1234567');
    expect(order.orderStatus).toBe('Shipped');
    expect(order.purchaseDate).toBe('2026-03-15T10:30:00Z');
    expect(order.items).toHaveLength(2);
    expect(order.items[0].asin).toBe('B00EXAMPLE');
    expect(order.items[0].quantityOrdered).toBe(2);
    expect(order.items[0].itemPriceAmount).toBe(3000);
    expect(order.items[1].asin).toBe('B00EXAMPLF');
    expect(order.items[1].quantityOrdered).toBe(1);
    expect(order.items[1].itemPriceAmount).toBe(1500);
  });

  test('isCanceled returns true for Canceled orders', () => {
    const apiResponse = {
      AmazonOrderId: '503-0000000-0000000',
      OrderStatus: 'Canceled',
      PurchaseDate: '2026-03-15T10:30:00Z',
    };
    const order = new global.Order(apiResponse, []);
    expect(order.isCanceled()).toBe(true);
  });

  test('isCanceled returns false for Shipped orders', () => {
    const apiResponse = {
      AmazonOrderId: '503-0000000-0000000',
      OrderStatus: 'Shipped',
      PurchaseDate: '2026-03-15T10:30:00Z',
    };
    const order = new global.Order(apiResponse, []);
    expect(order.isCanceled()).toBe(false);
  });

  test('handles missing ItemPrice gracefully', () => {
    const apiResponse = {
      AmazonOrderId: '503-0000000-0000000',
      OrderStatus: 'Shipped',
      PurchaseDate: '2026-03-15T10:30:00Z',
    };
    const orderItems = [
      {
        ASIN: 'B00EXAMPLE',
        QuantityOrdered: 1,
        ItemPrice: null,
      },
    ];
    const order = new global.Order(apiResponse, orderItems);
    expect(order.items[0].itemPriceAmount).toBe(0);
  });
});
```

- [ ] **Step 3: テストを実行し失敗を確認**

Run: `npm test -- --testNamePattern="Order" 2>&1 | tail -20`
Expected: FAIL（Order が未定義）

- [ ] **Step 4: Order エンティティを実装**

`src/domain/entities/Order.js` を作成:

```javascript
class OrderItem {
  constructor(item) {
    this.asin = item.ASIN;
    this.quantityOrdered = item.QuantityOrdered;
    this.itemPriceAmount = item.ItemPrice ? Number(item.ItemPrice.Amount) : 0;
  }
}

class Order {
  constructor(orderData, orderItemsData) {
    this.orderId = orderData.AmazonOrderId;
    this.orderStatus = orderData.OrderStatus;
    this.purchaseDate = orderData.PurchaseDate;
    this.items = orderItemsData.map(item => new OrderItem(item));
  }

  isCanceled() {
    return this.orderStatus === 'Canceled';
  }
}
```

- [ ] **Step 5: テストファイルにソースとエクスポートを登録**

`tests/getSPAPIdata.test.js` の `sourceFiles` 配列に追加:
```javascript
'../src/domain/entities/Order.js',
```

`gasExports` 配列に追加:
```javascript
'Order', 'OrderItem',
```

- [ ] **Step 6: テストを実行し成功を確認**

Run: `npm test -- --testNamePattern="Order" 2>&1 | tail -20`
Expected: PASS（4 tests）

- [ ] **Step 7: コミット**

```bash
git add src/domain/entities/Order.js tests/getSPAPIdata.test.js
git commit -m "feat: Order エンティティを追加"
```

---

### Task 2: RealtimeSalesResult 値オブジェクト

**Files:**
- Create: `src/domain/value_objects/RealtimeSalesResult.js`
- Modify: `tests/getSPAPIdata.test.js`

- [ ] **Step 1: 失敗するテストを書く**

`tests/getSPAPIdata.test.js` の末尾に追加:

```javascript
describe('RealtimeSalesResult', () => {
  test('constructor sets properties', () => {
    const result = new global.RealtimeSalesResult('B00EXAMPLE', 5, 15000);
    expect(result.asin).toBe('B00EXAMPLE');
    expect(result.unitCount).toBe(5);
    expect(result.totalAmount).toBe(15000);
  });

  test('default values are zero', () => {
    const result = new global.RealtimeSalesResult('B00EXAMPLE');
    expect(result.unitCount).toBe(0);
    expect(result.totalAmount).toBe(0);
  });

  test('addSale accumulates values', () => {
    const result = new global.RealtimeSalesResult('B00EXAMPLE');
    result.addSale(2, 3000);
    result.addSale(1, 1500);
    expect(result.unitCount).toBe(3);
    expect(result.totalAmount).toBe(4500);
  });
});
```

- [ ] **Step 2: テストを実行し失敗を確認**

Run: `npm test -- --testNamePattern="RealtimeSalesResult" 2>&1 | tail -20`
Expected: FAIL

- [ ] **Step 3: RealtimeSalesResult を実装**

`src/domain/value_objects/RealtimeSalesResult.js` を作成:

```javascript
class RealtimeSalesResult {
  constructor(asin, unitCount, totalAmount) {
    this.asin = asin;
    this.unitCount = unitCount || 0;
    this.totalAmount = totalAmount || 0;
  }

  addSale(quantity, amount) {
    this.unitCount += quantity;
    this.totalAmount += amount;
  }
}
```

- [ ] **Step 4: テストファイルにソースとエクスポートを登録**

`sourceFiles` に追加: `'../src/domain/value_objects/RealtimeSalesResult.js'`
`gasExports` に追加: `'RealtimeSalesResult'`

- [ ] **Step 5: テストを実行し成功を確認**

Run: `npm test -- --testNamePattern="RealtimeSalesResult" 2>&1 | tail -20`
Expected: PASS（3 tests）

- [ ] **Step 6: コミット**

```bash
git add src/domain/value_objects/RealtimeSalesResult.js tests/getSPAPIdata.test.js
git commit -m "feat: RealtimeSalesResult 値オブジェクトを追加"
```

---

### Task 3: OrderRepository インターフェース

**Files:**
- Create: `src/domain/repositories/OrderRepository.js`

- [ ] **Step 1: OrderRepository を作成**

```javascript
class OrderRepository {
  getOrdersWithItems(startDate) {
    throw new Error('Not implemented');
  }
}
```

- [ ] **Step 2: テストファイルにソースとエクスポートを登録**

`sourceFiles` に追加: `'../src/domain/repositories/OrderRepository.js'`
`gasExports` に追加: `'OrderRepository'`

- [ ] **Step 3: コミット**

```bash
git add src/domain/repositories/OrderRepository.js tests/getSPAPIdata.test.js
git commit -m "feat: OrderRepository インターフェースを追加"
```

---

## Chunk 2: インフラ層（API・Sheets）

### Task 4: OrdersDownloader

**Files:**
- Create: `src/infrastructure/api/OrdersDownloader.js`
- Modify: `tests/getSPAPIdata.test.js`

- [ ] **Step 1: 失敗するテストを書く**

`tests/getSPAPIdata.test.js` の末尾に追加:

```javascript
describe('OrdersDownloader', () => {
  let downloader;

  beforeEach(() => {
    global.UrlFetchApp.fetch.mockReturnValue({
      getContentText: () => JSON.stringify({ access_token: 'test-token' })
    });
    downloader = new global.OrdersDownloader('/orders/v0/orders');
  });

  test('searchOrders returns orders with pagination', () => {
    const page1Response = {
      payload: {
        Orders: [
          { AmazonOrderId: '503-001', OrderStatus: 'Shipped', PurchaseDate: '2026-03-15T10:00:00Z' },
          { AmazonOrderId: '503-002', OrderStatus: 'Unshipped', PurchaseDate: '2026-03-15T11:00:00Z' },
        ],
        NextToken: 'token123',
      },
    };
    const page2Response = {
      payload: {
        Orders: [
          { AmazonOrderId: '503-003', OrderStatus: 'Shipped', PurchaseDate: '2026-03-15T12:00:00Z' },
        ],
        NextToken: null,
      },
    };

    global.UrlFetchApp.fetch
      .mockReturnValueOnce({ getContentText: () => JSON.stringify({ access_token: 'test-token' }) })
      .mockReturnValueOnce({ getContentText: () => JSON.stringify(page1Response) })
      .mockReturnValueOnce({ getContentText: () => JSON.stringify(page2Response) });

    downloader = new global.OrdersDownloader('/orders/v0/orders');
    const startDate = new Date('2026-03-15T00:00:00+09:00');
    const orders = downloader.searchOrders(startDate);

    expect(orders).toHaveLength(3);
    expect(orders[0].AmazonOrderId).toBe('503-001');
    expect(orders[2].AmazonOrderId).toBe('503-003');
  });

  test('searchOrders handles single page response', () => {
    const response = {
      payload: {
        Orders: [
          { AmazonOrderId: '503-001', OrderStatus: 'Shipped', PurchaseDate: '2026-03-15T10:00:00Z' },
        ],
        NextToken: null,
      },
    };

    global.UrlFetchApp.fetch
      .mockReturnValueOnce({ getContentText: () => JSON.stringify({ access_token: 'test-token' }) })
      .mockReturnValueOnce({ getContentText: () => JSON.stringify(response) });

    downloader = new global.OrdersDownloader('/orders/v0/orders');
    const startDate = new Date('2026-03-15T00:00:00+09:00');
    const orders = downloader.searchOrders(startDate);

    expect(orders).toHaveLength(1);
  });

  test('getOrderItemsForOrders fetches items for each order via fetchAll', () => {
    const orderIds = ['503-001', '503-002'];
    const mockResponses = [
      { getContentText: () => JSON.stringify({
        payload: { OrderItems: [
          { ASIN: 'B00EXAMPLE', QuantityOrdered: 2, ItemPrice: { CurrencyCode: 'JPY', Amount: '3000' } },
        ] }
      }) },
      { getContentText: () => JSON.stringify({
        payload: { OrderItems: [
          { ASIN: 'B00EXAMPLF', QuantityOrdered: 1, ItemPrice: { CurrencyCode: 'JPY', Amount: '1500' } },
        ] }
      }) },
    ];
    global.UrlFetchApp.fetchAll.mockReturnValue(mockResponses);

    const result = downloader.getOrderItemsForOrders(orderIds);

    expect(result['503-001']).toHaveLength(1);
    expect(result['503-001'][0].ASIN).toBe('B00EXAMPLE');
    expect(result['503-002']).toHaveLength(1);
    expect(result['503-002'][0].ASIN).toBe('B00EXAMPLF');
  });

  test('getOrdersWithItems returns Order entities', () => {
    const ordersResponse = {
      payload: {
        Orders: [
          { AmazonOrderId: '503-001', OrderStatus: 'Shipped', PurchaseDate: '2026-03-15T10:00:00Z' },
        ],
        NextToken: null,
      },
    };
    const itemsResponse = [
      { getContentText: () => JSON.stringify({
        payload: { OrderItems: [
          { ASIN: 'B00EXAMPLE', QuantityOrdered: 2, ItemPrice: { CurrencyCode: 'JPY', Amount: '3000' } },
        ] }
      }) },
    ];

    global.UrlFetchApp.fetch
      .mockReturnValueOnce({ getContentText: () => JSON.stringify({ access_token: 'test-token' }) })
      .mockReturnValueOnce({ getContentText: () => JSON.stringify(ordersResponse) });
    global.UrlFetchApp.fetchAll.mockReturnValue(itemsResponse);

    downloader = new global.OrdersDownloader('/orders/v0/orders');
    const startDate = new Date('2026-03-15T00:00:00+09:00');
    const orders = downloader.getOrdersWithItems(startDate);

    expect(orders).toHaveLength(1);
    expect(orders[0].orderId).toBe('503-001');
    expect(orders[0].items[0].asin).toBe('B00EXAMPLE');
    expect(orders[0].items[0].quantityOrdered).toBe(2);
    expect(orders[0].items[0].itemPriceAmount).toBe(3000);
  });
});
```

- [ ] **Step 2: テストを実行し失敗を確認**

Run: `npm test -- --testNamePattern="OrdersDownloader" 2>&1 | tail -20`
Expected: FAIL

- [ ] **Step 3: OrdersDownloader を実装**

`src/infrastructure/api/OrdersDownloader.js` を作成:

```javascript
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
```

- [ ] **Step 4: テストファイルにソースとエクスポートを登録**

`sourceFiles` に追加: `'../src/infrastructure/api/OrdersDownloader.js'`
`gasExports` に追加: `'OrdersDownloader'`

注意: `OrdersDownloader` は `Order` と `Downloader` に依存するため、`sourceFiles` での読み込み順序が重要。`Order.js` と `Downloader.js` が先に読み込まれるようにする。

- [ ] **Step 5: テストを実行し成功を確認**

Run: `npm test -- --testNamePattern="OrdersDownloader" 2>&1 | tail -20`
Expected: PASS（4 tests）

- [ ] **Step 6: コミット**

```bash
git add src/infrastructure/api/OrdersDownloader.js tests/getSPAPIdata.test.js
git commit -m "feat: OrdersDownloader を追加（searchOrders + getOrderItems）"
```

---

### Task 5: RealtimeSalesSheet

**Files:**
- Create: `src/infrastructure/sheets/RealtimeSalesSheet.js`
- Modify: `tests/getSPAPIdata.test.js`

- [ ] **Step 1: 失敗するテストを書く**

`tests/getSPAPIdata.test.js` の末尾に追加:

```javascript
describe('RealtimeSalesSheet', () => {
  let sheet;

  beforeEach(() => {
    sheet = new global.RealtimeSalesSheet();
  });

  test('getAsinList reads ASINs from column A skipping header', () => {
    const mockSheet = global.SpreadsheetApp.openById().getSheetByName();
    mockSheet.getLastRow.mockReturnValue(4);
    mockSheet.getRange.mockReturnValue({
      getValues: jest.fn().mockReturnValue([
        ['ASIN'],
        ['B00EXAMPLE'],
        ['B00EXAMPLF'],
        ['B00EXAMPLG'],
      ]),
    });

    const asinList = sheet.getAsinList();

    expect(asinList).toEqual(['B00EXAMPLE', 'B00EXAMPLF', 'B00EXAMPLG']);
  });

  test('writeRealtimeSales writes unit count and amount to columns B and C', () => {
    const mockSetValues = jest.fn();
    const mockSheet = global.SpreadsheetApp.openById().getSheetByName();
    mockSheet.getLastRow.mockReturnValue(4);
    mockSheet.getRange.mockReturnValue({
      getValues: jest.fn().mockReturnValue([
        ['ASIN'],
        ['B00EXAMPLE'],
        ['B00EXAMPLF'],
        ['B00EXAMPLG'],
      ]),
      setValues: mockSetValues,
    });

    const salesMap = {
      'B00EXAMPLE': { unitCount: 5, totalAmount: 15000 },
      'B00EXAMPLF': { unitCount: 3, totalAmount: 9000 },
      'B00EXAMPLG': { unitCount: 0, totalAmount: 0 },
    };

    sheet.getAsinList();
    sheet.writeRealtimeSales(salesMap);

    expect(mockSetValues).toHaveBeenCalledWith([
      [5, 15000],
      [3, 9000],
      [0, 0],
    ]);
  });
});
```

- [ ] **Step 2: テストを実行し失敗を確認**

Run: `npm test -- --testNamePattern="RealtimeSalesSheet" 2>&1 | tail -20`
Expected: FAIL

- [ ] **Step 3: RealtimeSalesSheet を実装**

`src/infrastructure/sheets/RealtimeSalesSheet.js` を作成:

```javascript
class RealtimeSalesSheet {
  constructor() {
    this.sheet = getSheetByName('売上/今');
    this.asinList = [];
  }

  getAsinList() {
    const lastRow = this.sheet.getLastRow();
    const values = this.sheet.getRange(1, 1, lastRow).getValues();

    this.asinList = [];
    for (let i = 1; i < values.length; i++) {
      const asin = values[i][0];
      if (asin && asin.length === 10) {
        this.asinList.push(asin);
      }
    }
    return this.asinList;
  }

  writeRealtimeSales(salesMap) {
    const writeData = this.asinList.map(asin => {
      const sales = salesMap[asin] || { unitCount: 0, totalAmount: 0 };
      return [sales.unitCount, sales.totalAmount];
    });

    if (writeData.length > 0) {
      this.sheet.getRange(2, 2, writeData.length, 2).setValues(writeData);
    }
  }
}
```

- [ ] **Step 4: テストファイルにソースとエクスポートを登録**

`sourceFiles` に追加: `'../src/infrastructure/sheets/RealtimeSalesSheet.js'`
`gasExports` に追加: `'RealtimeSalesSheet'`

- [ ] **Step 5: テストを実行し成功を確認**

Run: `npm test -- --testNamePattern="RealtimeSalesSheet" 2>&1 | tail -20`
Expected: PASS（2 tests）

- [ ] **Step 6: コミット**

```bash
git add src/infrastructure/sheets/RealtimeSalesSheet.js tests/getSPAPIdata.test.js
git commit -m "feat: RealtimeSalesSheet を追加（売上/今シートの読み書き）"
```

---

## Chunk 3: ユースケース層とエントリポイント

### Task 6: UpdateRealtimeSalesUseCase

**Files:**
- Create: `src/usecases/UpdateRealtimeSalesUseCase.js`
- Modify: `tests/getSPAPIdata.test.js`

- [ ] **Step 1: 失敗するテストを書く**

`tests/getSPAPIdata.test.js` の末尾に追加:

```javascript
describe('UpdateRealtimeSalesUseCase', () => {
  test('aggregates orders by ASIN and writes to sheet', () => {
    const mockOrders = [
      {
        orderId: '503-001',
        orderStatus: 'Shipped',
        purchaseDate: '2026-03-15T10:00:00Z',
        items: [
          { asin: 'B00EXAMPLE', quantityOrdered: 2, itemPriceAmount: 3000 },
          { asin: 'B00EXAMPLF', quantityOrdered: 1, itemPriceAmount: 1500 },
        ],
        isCanceled: () => false,
      },
      {
        orderId: '503-002',
        orderStatus: 'Shipped',
        purchaseDate: '2026-03-15T12:00:00Z',
        items: [
          { asin: 'B00EXAMPLE', quantityOrdered: 1, itemPriceAmount: 1500 },
        ],
        isCanceled: () => false,
      },
    ];

    const mockDownloader = {
      getOrdersWithItems: jest.fn().mockReturnValue(mockOrders),
    };
    const writtenSalesMap = {};
    const mockSheet = {
      getAsinList: jest.fn().mockReturnValue(['B00EXAMPLE', 'B00EXAMPLF', 'B00EXAMPLG']),
      writeRealtimeSales: jest.fn().mockImplementation(salesMap => {
        Object.assign(writtenSalesMap, salesMap);
      }),
    };

    const useCase = new global.UpdateRealtimeSalesUseCase(mockSheet, mockDownloader);
    useCase.execute();

    expect(mockDownloader.getOrdersWithItems).toHaveBeenCalledTimes(1);
    expect(mockSheet.writeRealtimeSales).toHaveBeenCalledTimes(1);

    const salesMap = mockSheet.writeRealtimeSales.mock.calls[0][0];
    expect(salesMap['B00EXAMPLE'].unitCount).toBe(3);
    expect(salesMap['B00EXAMPLE'].totalAmount).toBe(4500);
    expect(salesMap['B00EXAMPLF'].unitCount).toBe(1);
    expect(salesMap['B00EXAMPLF'].totalAmount).toBe(1500);
    expect(salesMap['B00EXAMPLG'].unitCount).toBe(0);
    expect(salesMap['B00EXAMPLG'].totalAmount).toBe(0);
  });

  test('excludes Canceled orders from aggregation', () => {
    const mockOrders = [
      {
        orderId: '503-001',
        orderStatus: 'Shipped',
        items: [{ asin: 'B00EXAMPLE', quantityOrdered: 2, itemPriceAmount: 3000 }],
        isCanceled: () => false,
      },
      {
        orderId: '503-002',
        orderStatus: 'Canceled',
        items: [{ asin: 'B00EXAMPLE', quantityOrdered: 5, itemPriceAmount: 7500 }],
        isCanceled: () => true,
      },
    ];

    const mockDownloader = { getOrdersWithItems: jest.fn().mockReturnValue(mockOrders) };
    const mockSheet = {
      getAsinList: jest.fn().mockReturnValue(['B00EXAMPLE']),
      writeRealtimeSales: jest.fn(),
    };

    const useCase = new global.UpdateRealtimeSalesUseCase(mockSheet, mockDownloader);
    useCase.execute();

    const salesMap = mockSheet.writeRealtimeSales.mock.calls[0][0];
    expect(salesMap['B00EXAMPLE'].unitCount).toBe(2);
    expect(salesMap['B00EXAMPLE'].totalAmount).toBe(3000);
  });

  test('only aggregates ASINs present in sheet', () => {
    const mockOrders = [
      {
        orderId: '503-001',
        orderStatus: 'Shipped',
        items: [
          { asin: 'B00EXAMPLE', quantityOrdered: 1, itemPriceAmount: 1500 },
          { asin: 'B00UNKNOWN', quantityOrdered: 3, itemPriceAmount: 9000 },
        ],
        isCanceled: () => false,
      },
    ];

    const mockDownloader = { getOrdersWithItems: jest.fn().mockReturnValue(mockOrders) };
    const mockSheet = {
      getAsinList: jest.fn().mockReturnValue(['B00EXAMPLE']),
      writeRealtimeSales: jest.fn(),
    };

    const useCase = new global.UpdateRealtimeSalesUseCase(mockSheet, mockDownloader);
    useCase.execute();

    const salesMap = mockSheet.writeRealtimeSales.mock.calls[0][0];
    expect(salesMap['B00EXAMPLE'].unitCount).toBe(1);
    expect(salesMap['B00UNKNOWN']).toBeUndefined();
  });

  test('handles zero orders gracefully', () => {
    const mockDownloader = { getOrdersWithItems: jest.fn().mockReturnValue([]) };
    const mockSheet = {
      getAsinList: jest.fn().mockReturnValue(['B00EXAMPLE']),
      writeRealtimeSales: jest.fn(),
    };

    const useCase = new global.UpdateRealtimeSalesUseCase(mockSheet, mockDownloader);
    useCase.execute();

    const salesMap = mockSheet.writeRealtimeSales.mock.calls[0][0];
    expect(salesMap['B00EXAMPLE'].unitCount).toBe(0);
    expect(salesMap['B00EXAMPLE'].totalAmount).toBe(0);
  });

  test('skips sheet write when API fails', () => {
    const mockDownloader = {
      getOrdersWithItems: jest.fn().mockImplementation(() => {
        throw new Error('API error');
      }),
    };
    const mockSheet = {
      getAsinList: jest.fn().mockReturnValue(['B00EXAMPLE']),
      writeRealtimeSales: jest.fn(),
    };

    const useCase = new global.UpdateRealtimeSalesUseCase(mockSheet, mockDownloader);
    useCase.execute();

    expect(mockSheet.writeRealtimeSales).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: テストを実行し失敗を確認**

Run: `npm test -- --testNamePattern="UpdateRealtimeSalesUseCase" 2>&1 | tail -20`
Expected: FAIL

- [ ] **Step 3: UpdateRealtimeSalesUseCase を実装**

`src/usecases/UpdateRealtimeSalesUseCase.js` を作成:

```javascript
class UpdateRealtimeSalesUseCase {
  constructor(realtimeSalesSheet, ordersDownloader) {
    this.realtimeSalesSheet = realtimeSalesSheet;
    this.ordersDownloader = ordersDownloader;
  }

  execute() {
    const asinList = this.realtimeSalesSheet.getAsinList();
    const startDate = this._getTodayStart();

    let orders;
    try {
      orders = this.ordersDownloader.getOrdersWithItems(startDate);
    } catch (error) {
      console.log('注文データの取得に失敗しました: ' + error.message);
      return;
    }

    const salesMap = this._aggregateByAsin(orders, asinList);
    this.realtimeSalesSheet.writeRealtimeSales(salesMap);
  }

  _getTodayStart() {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
  }

  _aggregateByAsin(orders, asinList) {
    const salesMap = {};
    for (const asin of asinList) {
      salesMap[asin] = new RealtimeSalesResult(asin);
    }

    const activeOrders = orders.filter(order => !order.isCanceled());

    for (const order of activeOrders) {
      for (const item of order.items) {
        if (salesMap[item.asin]) {
          salesMap[item.asin].addSale(item.quantityOrdered, item.itemPriceAmount);
        }
      }
    }

    return salesMap;
  }
}
```

- [ ] **Step 4: テストファイルにソースとエクスポートを登録**

`sourceFiles` に追加: `'../src/usecases/UpdateRealtimeSalesUseCase.js'`
`gasExports` に追加: `'UpdateRealtimeSalesUseCase'`

- [ ] **Step 5: テストを実行し成功を確認**

Run: `npm test -- --testNamePattern="UpdateRealtimeSalesUseCase" 2>&1 | tail -20`
Expected: PASS（5 tests）

- [ ] **Step 6: コミット**

```bash
git add src/usecases/UpdateRealtimeSalesUseCase.js tests/getSPAPIdata.test.js
git commit -m "feat: UpdateRealtimeSalesUseCase を追加（ASIN別集計・シート書き込み）"
```

---

### Task 7: main.js にエントリポイントを追加

**Files:**
- Modify: `src/main.js`

- [ ] **Step 1: main.js に updateRealtimeSales 関数を追加**

`src/main.js` の末尾（`deleteOrderNumber()` の後）に追加:

```javascript
function updateRealtimeSales() {
  try {
    const realtimeSalesSheet = new RealtimeSalesSheet();
    const ordersDownloader = new OrdersDownloader('/orders/v0/orders');
    const useCase = new UpdateRealtimeSalesUseCase(realtimeSalesSheet, ordersDownloader);
    useCase.execute();
  } catch (error) {
    Logger.log('エラーが発生しました: ' + error.toString());
    throw error;
  }
}

function setupRealtimeSalesTrigger() {
  ScriptApp.newTrigger('updateRealtimeSales')
    .timeBased()
    .everyMinutes(10)
    .create();
  Logger.log('リアルタイム売上更新トリガーを設定しました（10分間隔）');
}
```

- [ ] **Step 2: テストファイルの gasExports に追加**

`gasExports` に追加: `'updateRealtimeSales', 'setupRealtimeSalesTrigger'`

- [ ] **Step 3: 全テストを実行して既存テストが壊れていないことを確認**

Run: `npm test 2>&1 | tail -30`
Expected: All tests PASS

- [ ] **Step 4: コミット**

```bash
git add src/main.js tests/getSPAPIdata.test.js
git commit -m "feat: updateRealtimeSales エントリポイントとトリガー設定関数を追加"
```

---

## Chunk 4: 統合テスト・最終確認

### Task 8: 全テスト実行と最終確認

- [ ] **Step 1: 全テストを実行**

Run: `npm test 2>&1`
Expected: All tests PASS

- [ ] **Step 2: 新規ファイルの一覧を確認**

以下のファイルが作成されていることを確認:
- `src/domain/entities/Order.js`
- `src/domain/value_objects/RealtimeSalesResult.js`
- `src/domain/repositories/OrderRepository.js`
- `src/infrastructure/api/OrdersDownloader.js`
- `src/infrastructure/sheets/RealtimeSalesSheet.js`
- `src/usecases/UpdateRealtimeSalesUseCase.js`

以下のファイルが変更されていることを確認:
- `src/main.js`（2関数追加）
- `tests/getSPAPIdata.test.js`（テスト追加）

- [ ] **Step 3: package.json のバージョンを更新**

新機能追加のためマイナーバージョンをインクリメント。現在のバージョン `2.6.2` → `2.7.0` に更新。

- [ ] **Step 4: コミット**

```bash
git add package.json
git commit -m "feat: リアルタイム売上モニタリング機能を追加 (v2.7.0)"
```

### Task 9: デプロイ手順

- [ ] **Step 1: clasp push でGASにデプロイ**

Run: `clasp push`

- [ ] **Step 2: GAS Editorで確認**

GAS Editorで以下を確認:
1. `updateRealtimeSales()` 関数が表示されること
2. 手動実行して動作確認

- [ ] **Step 3: トリガー登録**

GAS Editorで `setupRealtimeSalesTrigger()` を1回実行し、10分間隔トリガーを登録。
