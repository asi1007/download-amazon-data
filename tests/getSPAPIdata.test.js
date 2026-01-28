global.PropertiesService = {
  getScriptProperties: jest.fn().mockReturnValue({
    getProperty: jest.fn().mockReturnValue('test-value')
  })
};

global.UrlFetchApp = {
  fetch: jest.fn(),
};

global.SpreadsheetApp = {
  openById: jest.fn().mockReturnValue({
    getSheetByName: jest.fn().mockReturnValue({
      getLastRow: jest.fn().mockReturnValue(10),
      getRange: jest.fn().mockReturnValue({
        getValues: jest.fn().mockReturnValue([
          ['B000EXAMPLE1'],
          ['B000EXAMPLE2'],
          ['B000EXAMPLE3'],
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

const loadSourceFiles = () => {
  require('../src/infrastructure/sheets/SheetConfig');
  require('../src/domain/entities/Transaction');
  require('../src/domain/entities/AmazonAdData');
  require('../src/domain/value_objects/CostData');
  require('../src/domain/value_objects/SalesInfo');
  require('../src/domain/value_objects/InventorySummary');
  require('../src/infrastructure/api/AuthService');
  require('../src/infrastructure/api/Downloader');
  require('../src/infrastructure/api/SalesDownloader');
  require('../src/infrastructure/api/PriceDownloader');
  require('../src/infrastructure/api/SKUDownloader');
  require('../src/infrastructure/api/InventorySummariesDownloader');
  require('../src/infrastructure/sheets/SalesSheet');
  require('../src/infrastructure/sheets/InventorySheet');
  require('../src/infrastructure/sheets/CostDataReader');
  require('../src/infrastructure/sheets/AmazonAdDataReader');
  require('../src/usecases/UpdateSalesUseCase');
  require('../src/usecases/UpdatePriceUseCase');
  require('../src/usecases/UpdateInventoryUseCase');
  require('../src/usecases/GetAdDataUseCase');
  require('../src/main');
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
        { summaries: [{ asin: 'B000EXAMPLE1' }], sku: 'SKU1' },
        { summaries: [{ asin: 'B000EXAMPLE2' }], sku: 'SKU2' }
      ],
      pagination: { nextToken: undefined }
    };
    global.UrlFetchApp.fetch.mockReturnValue({
      getContentText: () => JSON.stringify(mockResponse)
    });
    expect(skuDownloader.getASINtoSKUs()).toEqual({
      'B000EXAMPLE1': 'SKU1',
      'B000EXAMPLE2': 'SKU2'
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
    expect(priceDownloader.getPriceOf('B000EXAMPLE1')).toEqual(mockResponse.payload);
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
    const params = salesDownloader.buildQueryParams('B000EXAMPLE1', 'Day', startDate, endDate);
    expect(params).toContain('granularity=Day');
    expect(params).toContain('asin=B000EXAMPLE1');
  });
});

describe('SalesSheet', () => {
  let salesSheet;
  beforeEach(() => {
    salesSheet = new global.SalesSheet('売上/日', 'B2');
  });

  test('getASINList returns valid ASINs', () => {
    const asinList = salesSheet.getASINList();
    expect(asinList).toContain('B000EXAMPLE1');
    expect(asinList).toContain('B000EXAMPLE2');
  });
});

describe('CostData', () => {
  test('getTotalUnitCost calculates correctly', () => {
    const costData = new global.CostData({
      asin: 'B000EXAMPLE1',
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
    const row = ['2025-01-01', 'B000EXAMPLE1', 100, 1000, 50, 500, 10, 20, 2, 5];
    const adData = new global.AmazonAdData(row);
    expect(adData.asin).toBe('B000EXAMPLE1');
    expect(adData.adSpend).toBe(100);
    expect(adData.acos).toBe(20);
  });
});
