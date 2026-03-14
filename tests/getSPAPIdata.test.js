global.PropertiesService = {
  getScriptProperties: jest.fn().mockReturnValue({
    getProperty: jest.fn().mockReturnValue('test-value')
  })
};

global.UrlFetchApp = {
  fetch: jest.fn(),
  fetchAll: jest.fn(),
};

global.SpreadsheetApp = {
  openById: jest.fn().mockReturnValue({
    getSheetByName: jest.fn().mockReturnValue({
      getLastRow: jest.fn().mockReturnValue(10),
      getRange: jest.fn().mockReturnValue({
        getValues: jest.fn().mockReturnValue([
          ['B00EXAMPLE'],
          ['B00EXAMPLF'],
          ['B00EXAMPLG'],
        ]),
        getValue: jest.fn().mockReturnValue(5),
        setValue: jest.fn(),
        setBackground: jest.fn(),
        setNote: jest.fn(),
        getNote: jest.fn().mockReturnValue('100'),
        copyTo: jest.fn(),
        setFontWeight: jest.fn(),
        setFontColor: jest.fn(),
        setHorizontalAlignment: jest.fn(),
        setVerticalAlignment: jest.fn(),
        setWrap: jest.fn(),
        setNumberFormat: jest.fn(),
      }),
      insertColumnBefore: jest.fn(),
      clear: jest.fn(),
      setColumnWidth: jest.fn(),
      setRowHeight: jest.fn(),
      insertSheet: jest.fn(),
    }),
    insertSheet: jest.fn().mockReturnValue({
      getRange: jest.fn().mockReturnValue({
        setValues: jest.fn(),
        setFontWeight: jest.fn(),
        setBackground: jest.fn(),
        setFontColor: jest.fn(),
        setHorizontalAlignment: jest.fn(),
        setVerticalAlignment: jest.fn(),
        setWrap: jest.fn(),
      }),
      setColumnWidth: jest.fn(),
      setRowHeight: jest.fn(),
    }),
  }),
  getActiveSpreadsheet: jest.fn().mockReturnValue({
    getSheetByName: jest.fn().mockReturnValue({
      getLastRow: jest.fn().mockReturnValue(10),
      getRange: jest.fn().mockReturnValue({
        setValues: jest.fn(),
      }),
    }),
  }),
};

global.Utilities = {
  sleep: jest.fn(),
  formatDate: jest.fn().mockReturnValue('2025/01/28'),
};

global.Logger = {
  log: jest.fn(),
};

global.console = {
  log: jest.fn(),
};

global.ScriptApp = {
  newTrigger: jest.fn().mockReturnValue({
    timeBased: jest.fn().mockReturnValue({
      everyMinutes: jest.fn().mockReturnValue({
        create: jest.fn(),
      }),
    }),
  }),
};

const fs = require('fs');
const path = require('path');

const sourceFiles = [
  '../src/infrastructure/sheets/SheetConfig.js',
  '../src/domain/entities/Transaction.js',
  '../src/domain/entities/AmazonAdData.js',
  '../src/domain/value_objects/CostData.js',
  '../src/domain/value_objects/SalesInfo.js',
  '../src/domain/value_objects/InventorySummary.js',
  '../src/domain/value_objects/RealtimeSalesResult.js',
  '../src/domain/entities/Order.js',
  '../src/domain/repositories/OrderRepository.js',
  '../src/infrastructure/api/AuthService.js',
  '../src/infrastructure/api/Downloader.js',
  '../src/infrastructure/api/SalesDownloader.js',
  '../src/infrastructure/api/PriceDownloader.js',
  '../src/infrastructure/api/SKUDownloader.js',
  '../src/infrastructure/api/InventorySummariesDownloader.js',
  '../src/infrastructure/sheets/SalesSheet.js',
  '../src/infrastructure/sheets/InventorySheet.js',
  '../src/infrastructure/sheets/CostDataReader.js',
  '../src/infrastructure/sheets/AmazonAdDataReader.js',
  '../src/infrastructure/sheets/RealtimeSalesSheet.js',
  '../src/infrastructure/sheets/TransactionSheet.js',
  '../src/infrastructure/api/TransactionDownloader.js',
  '../src/infrastructure/api/OrdersDownloader.js',
  '../src/usecases/UpdateSalesUseCase.js',
  '../src/usecases/UpdatePriceUseCase.js',
  '../src/usecases/UpdateInventoryUseCase.js',
  '../src/usecases/GetAdDataUseCase.js',
  '../src/usecases/DownloadTransactionUseCase.js',
  '../src/usecases/UpdateRealtimeSalesUseCase.js',
  '../src/main.js',
];

const gasExports = [
  'getSheetByName', 'getScriptProperty', 'getAuthToken',
  'Transaction', 'AmazonAdData', 'CostData', 'SalesInfo', 'InventorySummary', 'RealtimeSalesResult',
  'Order', 'OrderItem', 'OrderRepository',
  'Downloader', 'SalesDownloader', 'PriceDownloader', 'SKUDownloader', 'InventorySummariesDownloader',
  'SalesSheet', 'InventorySheet', 'CostDataReader', 'AmazonAdDataReader', 'WeeklyCostSheet', 'RealtimeSalesSheet', 'TransactionSheet',
  'TransactionDownloader', 'OrdersDownloader', 'DownloadTransactionUseCase',
  'UpdateSalesUseCase', 'UpdatePriceUseCase', 'UpdateInventoryUseCase', 'GetAdDataUseCase', 'UpdateWeeklyCostUseCase', 'UpdateRealtimeSalesUseCase',
  'updateYesterdaySalesNum', 'updateLastWeekSalesNum', 'downloadPrices',
  'updateInventoryStatus', 'updateWeeklyCostSummary', 'getCostData',
  'getAmazonAdData', 'getAmazonAdDataByDate', 'downloadTransactions', 'deleteOrderNumber',
  'updateRealtimeSales', 'setupRealtimeSalesTrigger',
];

const loadSourceFiles = () => {
  const allCode = sourceFiles.map(f =>
    fs.readFileSync(path.resolve(__dirname, f), 'utf-8')
  ).join('\n');

  const assignCode = gasExports.map(name =>
    `try { this.${name} = ${name}; } catch(e) {}`
  ).join('\n');

  const fn = new Function(allCode + '\n' + assignCode);
  fn.call(global);
};

loadSourceFiles();

describe('getAuthToken', () => {
  test('successfully gets auth token', () => {
    const mockResponse = { access_token: 'test-token' };
    global.UrlFetchApp.fetch.mockReturnValue({
      getContentText: () => JSON.stringify(mockResponse)
    });
    expect(global.getAuthToken()).toBe('test-token');
  });
});

describe('Downloader', () => {
  let downloader;
  beforeEach(() => {
    global.UrlFetchApp.fetch.mockReturnValue({
      getContentText: () => JSON.stringify({ access_token: 'test-token' })
    });
    downloader = new global.Downloader('/test-path');
    downloader.url = 'https://test-url.com';
  });

  test('constructor sets up basic properties', () => {
    expect(downloader.SP_API_URL).toBe('https://sellingpartnerapi-fe.amazon.com');
  });

  test('getData fetches and parses response', () => {
    const mockResponse = { data: 'test' };
    global.UrlFetchApp.fetch.mockReturnValue({
      getContentText: () => JSON.stringify(mockResponse)
    });
    downloader.setQueryParams(['param=value']);
    expect(downloader.getData()).toEqual(mockResponse);
  });
});

describe('SKUDownloader', () => {
  let skuDownloader;
  beforeEach(() => {
    global.UrlFetchApp.fetch.mockReturnValue({
      getContentText: () => JSON.stringify({ access_token: 'test-token' })
    });
    skuDownloader = new global.SKUDownloader('/test-path');
  });

  test('getASINtoSKUs maps ASINs to SKUs', () => {
    const mockResponse = {
      items: [
        { summaries: [{ asin: 'B00EXAMPLE' }], sku: 'SKU1' },
        { summaries: [{ asin: 'B00EXAMPLF' }], sku: 'SKU2' }
      ],
      pagination: { nextToken: undefined }
    };
    global.UrlFetchApp.fetch.mockReturnValue({
      getContentText: () => JSON.stringify(mockResponse)
    });
    expect(skuDownloader.getASINtoSKUs()).toEqual({
      'B00EXAMPLE': 'SKU1',
      'B00EXAMPLF': 'SKU2'
    });
  });
});

describe('PriceDownloader', () => {
  let priceDownloader;
  beforeEach(() => {
    global.UrlFetchApp.fetch.mockReturnValue({
      getContentText: () => JSON.stringify({ access_token: 'test-token' })
    });
    priceDownloader = new global.PriceDownloader('/test-path');
  });

  test('getPriceOf returns price data', () => {
    const mockResponse = {
      payload: [{
        Product: {
          CompetitivePricing: {
            CompetitivePrices: [{
              Price: { LandedPrice: { Amount: 29.99 } }
            }]
          }
        }
      }]
    };
    global.UrlFetchApp.fetch.mockReturnValue({
      getContentText: () => JSON.stringify(mockResponse)
    });
    expect(priceDownloader.getPriceOf('B00EXAMPLE')).toEqual(mockResponse.payload);
  });
});

describe('SalesDownloader', () => {
  let salesDownloader;
  beforeEach(() => {
    global.UrlFetchApp.fetch.mockReturnValue({
      getContentText: () => JSON.stringify({ access_token: 'test-token' })
    });
    salesDownloader = new global.SalesDownloader('/test-path');
  });

  test('buildQueryParams creates correct parameters', () => {
    const startDate = new Date('2025-01-01');
    const endDate = new Date('2025-01-02');
    const params = salesDownloader.buildQueryParams('B00EXAMPLE', 'Day', startDate, endDate);
    expect(params).toContain('granularity=Day');
    expect(params).toContain('asin=B00EXAMPLE');
  });

  test('getSalesInfosOf uses fetchAll for batch requests', () => {
    const mockResponses = [
      { getContentText: () => JSON.stringify({ payload: [{ unitCount: 5, totalSales: { amount: 100 } }] }) },
      { getContentText: () => JSON.stringify({ payload: [{ unitCount: 3, totalSales: { amount: 60 } }] }) },
    ];
    global.UrlFetchApp.fetchAll.mockReturnValue(mockResponses);

    const startDate = new Date('2025-01-01');
    const endDate = new Date('2025-01-02');
    const result = salesDownloader.getSalesInfosOf(['B00EXAMPLE', 'B00EXAMPLF'], 'Day', startDate, endDate);

    expect(global.UrlFetchApp.fetchAll).toHaveBeenCalledTimes(1);
    expect(global.UrlFetchApp.fetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/test-path'),
      expect.anything()
    );
    expect(result['B00EXAMPLE'].unitCount).toBe(5);
    expect(result['B00EXAMPLF'].unitCount).toBe(3);
  });
});

describe('SalesSheet', () => {
  let salesSheet;
  beforeEach(() => {
    salesSheet = new global.SalesSheet('売上/日', 'B2');
  });

  test('getASINList returns valid ASINs', () => {
    const asinList = salesSheet.getASINList();
    expect(asinList).toContain('B00EXAMPLE');
    expect(asinList).toContain('B00EXAMPLF');
  });
});

describe('CostData', () => {
  test('getTotalUnitCost calculates correctly', () => {
    const costData = new global.CostData({
      asin: 'B00EXAMPLE',
      localPrice: 100,
      shipCost: 20,
      taxCost: 10,
      extraCost: 5,
      variableFee: 15,
      fixedFee: 10
    });
    expect(costData.getTotalUnitCost()).toBe(160);
  });
});

describe('Transaction', () => {
  test('constructor sets postedDate', () => {
    const rawTransaction = {
      transactionType: 'Shipment',
      transactionStatus: 'RELEASED',
      postedDate: '2025-01-20T10:00:00Z',
      items: [{
        contexts: [{ asin: 'B00EXAMPLE', quantityShipped: 2 }],
        breakdowns: [
          { breakdownAmount: 1000 },
          { breakdownAmount: 100 },
          { breakdownAmount: 0, breakdowns: [{ breakdownAmount: 200 }, { breakdownAmount: 300 }] },
        ],
      }],
    };
    const transaction = new global.Transaction(rawTransaction);
    expect(transaction.postedDate).toBe('2025-01-20T10:00:00Z');
    expect(transaction.items[0].asin).toBe('B00EXAMPLE');
  });
});

describe('TransactionDownloader', () => {
  let downloader;
  beforeEach(() => {
    global.UrlFetchApp.fetch.mockReturnValue({
      getContentText: () => JSON.stringify({ access_token: 'test-token' })
    });
    downloader = new global.TransactionDownloader('/finances/2024-06-19/transactions');
  });

  test('getAllTransactions paginates through all pages', () => {
    const page1Response = {
      payload: {
        nextToken: 'token123',
        transactions: [{
          transactionType: 'Shipment',
          transactionStatus: 'RELEASED',
          postedDate: '2025-01-20T10:00:00Z',
          items: [{
            contexts: [{ asin: 'B00EXAMPLE', quantityShipped: 1 }],
            breakdowns: [
              { breakdownAmount: 500 },
              { breakdownAmount: 50 },
              { breakdownAmount: 0, breakdowns: [{ breakdownAmount: 100 }, { breakdownAmount: 150 }] },
            ],
          }],
        }],
      },
    };
    const page2Response = {
      payload: {
        nextToken: null,
        transactions: [{
          transactionType: 'Shipment',
          transactionStatus: 'RELEASED',
          postedDate: '2025-01-21T10:00:00Z',
          items: [{
            contexts: [{ asin: 'B00EXAMPLF', quantityShipped: 2 }],
            breakdowns: [
              { breakdownAmount: 800 },
              { breakdownAmount: 80 },
              { breakdownAmount: 0, breakdowns: [{ breakdownAmount: 200 }, { breakdownAmount: 250 }] },
            ],
          }],
        }],
      },
    };

    global.UrlFetchApp.fetch
      .mockReturnValueOnce({ getContentText: () => JSON.stringify({ access_token: 'test-token' }) })
      .mockReturnValueOnce({ getContentText: () => JSON.stringify(page1Response) })
      .mockReturnValueOnce({ getContentText: () => JSON.stringify(page2Response) });

    downloader = new global.TransactionDownloader('/finances/2024-06-19/transactions');
    const startDate = new Date('2025-01-20');
    const endDate = new Date('2025-01-27');
    const result = downloader.getAllTransactions(startDate, endDate);

    expect(result).toHaveLength(2);
    expect(result[0].items[0].asin).toBe('B00EXAMPLE');
    expect(result[1].items[0].asin).toBe('B00EXAMPLF');
  });

  test('getAllTransactions filters non-Shipment transactions', () => {
    const response = {
      payload: {
        nextToken: null,
        transactions: [
          {
            transactionType: 'Shipment',
            transactionStatus: 'RELEASED',
            postedDate: '2025-01-20T10:00:00Z',
            items: [{
              contexts: [{ asin: 'B00EXAMPLE', quantityShipped: 1 }],
              breakdowns: [
                { breakdownAmount: 500 },
                { breakdownAmount: 50 },
                { breakdownAmount: 0, breakdowns: [{ breakdownAmount: 100 }, { breakdownAmount: 150 }] },
              ],
            }],
          },
          {
            transactionType: 'Refund',
            transactionStatus: 'RELEASED',
            postedDate: '2025-01-20T10:00:00Z',
            items: [],
          },
        ],
      },
    };

    global.UrlFetchApp.fetch
      .mockReturnValueOnce({ getContentText: () => JSON.stringify({ access_token: 'test-token' }) })
      .mockReturnValueOnce({ getContentText: () => JSON.stringify(response) });

    downloader = new global.TransactionDownloader('/finances/2024-06-19/transactions');
    const result = downloader.getAllTransactions(new Date('2025-01-20'), new Date('2025-01-27'));

    expect(result).toHaveLength(1);
    expect(result[0].type).toBe('Shipment');
  });
});

describe('DownloadTransactionUseCase', () => {
  test('aggregates transactions by ASIN and date', () => {
    const mockTransactions = [
      {
        postedDate: '2025-01-20T00:00:00+09:00',
        items: [
          { asin: 'B00EXAMPLE', quantity: 2, sales: 1000, fees: 200, comission: 300 },
          { asin: 'B00EXAMPLF', quantity: 1, sales: 500, fees: 100, comission: 150 },
        ],
      },
      {
        postedDate: '2025-01-20T12:00:00+09:00',
        items: [
          { asin: 'B00EXAMPLE', quantity: 1, sales: 500, fees: 100, comission: 150 },
        ],
      },
      {
        postedDate: '2025-01-21T00:00:00+09:00',
        items: [
          { asin: 'B00EXAMPLE', quantity: 3, sales: 1500, fees: 300, comission: 450 },
        ],
      },
    ];

    const mockDownloader = {
      getAllTransactions: jest.fn().mockReturnValue(mockTransactions),
    };
    const writtenData = [];
    const mockSheet = {
      writeTransactionData: jest.fn().mockImplementation(rows => writtenData.push(...rows)),
    };

    const useCase = new global.DownloadTransactionUseCase(mockDownloader, mockSheet);
    useCase.execute();

    expect(mockDownloader.getAllTransactions).toHaveBeenCalledTimes(1);
    expect(mockSheet.writeTransactionData).toHaveBeenCalledTimes(1);

    const rows = mockSheet.writeTransactionData.mock.calls[0][0];
    expect(rows).toHaveLength(3);

    const exampleJan20 = rows.find(r => r[0] === '2025/01/20' && r[1] === 'B00EXAMPLE');
    expect(exampleJan20[2]).toBe(3);
    expect(exampleJan20[3]).toBe(1500);
    expect(exampleJan20[4]).toBe(300);
    expect(exampleJan20[5]).toBe(450);
    expect(exampleJan20[6]).toBe(750);

    const examplFJan20 = rows.find(r => r[0] === '2025/01/20' && r[1] === 'B00EXAMPLF');
    expect(examplFJan20[2]).toBe(1);
    expect(examplFJan20[3]).toBe(500);
    expect(examplFJan20[6]).toBe(250);

    const exampleJan21 = rows.find(r => r[0] === '2025/01/21' && r[1] === 'B00EXAMPLE');
    expect(exampleJan21[2]).toBe(3);
    expect(exampleJan21[6]).toBe(750);
  });

  test('rows are sorted by date then ASIN', () => {
    const mockTransactions = [
      {
        postedDate: '2025-01-21T00:00:00+09:00',
        items: [{ asin: 'B00EXAMPLF', quantity: 1, sales: 500, fees: 100, comission: 50 }],
      },
      {
        postedDate: '2025-01-20T00:00:00+09:00',
        items: [{ asin: 'B00EXAMPLE', quantity: 1, sales: 500, fees: 100, comission: 50 }],
      },
    ];

    const mockDownloader = { getAllTransactions: jest.fn().mockReturnValue(mockTransactions) };
    const mockSheet = { writeTransactionData: jest.fn() };

    const useCase = new global.DownloadTransactionUseCase(mockDownloader, mockSheet);
    useCase.execute();

    const rows = mockSheet.writeTransactionData.mock.calls[0][0];
    expect(rows[0][0]).toBe('2025/01/20');
    expect(rows[1][0]).toBe('2025/01/21');
  });
});

describe('AmazonAdData', () => {
  test('creates correct object from row data', () => {
    const row = ['2025-01-01', 'B00EXAMPLE', 100, 1000, 50, 500, 10, 20, 2, 5];
    const adData = new global.AmazonAdData(row);
    expect(adData.asin).toBe('B00EXAMPLE');
    expect(adData.adSpend).toBe(100);
    expect(adData.acos).toBe(20);
  });
});

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
