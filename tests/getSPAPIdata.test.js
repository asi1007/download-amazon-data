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

const fs = require('fs');
const path = require('path');

const sourceFiles = [
  '../src/infrastructure/sheets/SheetConfig.js',
  '../src/domain/entities/Transaction.js',
  '../src/domain/entities/AmazonAdData.js',
  '../src/domain/value_objects/CostData.js',
  '../src/domain/value_objects/SalesInfo.js',
  '../src/domain/value_objects/InventorySummary.js',
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
  '../src/usecases/UpdateSalesUseCase.js',
  '../src/usecases/UpdatePriceUseCase.js',
  '../src/usecases/UpdateInventoryUseCase.js',
  '../src/usecases/GetAdDataUseCase.js',
  '../src/main.js',
];

const gasExports = [
  'getSheetByName', 'getScriptProperty', 'getAuthToken',
  'Transaction', 'AmazonAdData', 'CostData', 'SalesInfo', 'InventorySummary',
  'Downloader', 'SalesDownloader', 'PriceDownloader', 'SKUDownloader', 'InventorySummariesDownloader',
  'SalesSheet', 'InventorySheet', 'CostDataReader', 'AmazonAdDataReader', 'WeeklyCostSheet',
  'UpdateSalesUseCase', 'UpdatePriceUseCase', 'UpdateInventoryUseCase', 'GetAdDataUseCase', 'UpdateWeeklyCostUseCase',
  'updateYesterdaySalesNum', 'updateLastWeekSalesNum', 'downloadPrices',
  'updateInventoryStatus', 'updateWeeklyCostSummary', 'getCostData',
  'getAmazonAdData', 'getAmazonAdDataByDate', 'deleteOrderNumber',
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

describe('AmazonAdData', () => {
  test('creates correct object from row data', () => {
    const row = ['2025-01-01', 'B00EXAMPLE', 100, 1000, 50, 500, 10, 20, 2, 5];
    const adData = new global.AmazonAdData(row);
    expect(adData.asin).toBe('B00EXAMPLE');
    expect(adData.adSpend).toBe(100);
    expect(adData.acos).toBe(20);
  });
});
