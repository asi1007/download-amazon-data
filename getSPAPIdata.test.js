// Mock GAS global objects
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
        setValue: jest.fn(),
        setBackground: jest.fn(),
        setNote: jest.fn(),
        getNote: jest.fn().mockReturnValue('100'),
        copyTo: jest.fn(),
      }),
      insertColumnBefore: jest.fn(),
    }),
  }),
};

global.Utilities = {
  sleep: jest.fn(),
};

global.console = {
  log: jest.fn(),
};

// Load the GAS code
require('./getSPAPIdata');

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
    downloader = new global.Downloader('test-token');
    downloader.url = 'https://test-url.com';
  });

  test('constructor sets up basic properties', () => {
    expect(downloader.SP_API_URL).toBe('https://sellingpartnerapi-fe.amazon.com');
    expect(downloader.authToken).toBe('test-token');
  });

  test('getData fetches and parses response', () => {
    const mockResponse = { data: 'test' };
    global.UrlFetchApp.fetch.mockReturnValue({
      getContentText: () => JSON.stringify(mockResponse)
    });
    expect(downloader.getData(['param=value'])).toEqual(mockResponse);
  });
});

describe('SKUDownloader', () => {
  let skuDownloader;
  beforeEach(() => {
    skuDownloader = new global.SKUDownloader('test-token');
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
    priceDownloader = new global.PriceDownloader('test-token');
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
    salesDownloader = new global.SalesDownloader('test-token');
  });

  test('buildQueryParams creates correct parameters', () => {
    const params = salesDownloader.buildQueryParams('B000EXAMPLE1', 'Day');
    expect(params).toContain('granularity=Day');
    expect(params).toContain('asin=B000EXAMPLE1');
  });

  test('getSalesNumOf returns unit count', () => {
    const mockResponse = {
      payload: [{ unitCount: 5 }]
    };
    global.UrlFetchApp.fetch.mockReturnValue({
      getContentText: () => JSON.stringify(mockResponse)
    });
    expect(salesDownloader.getSalesNumOf('B000EXAMPLE1', 'Day')).toBe(5);
  });
});

describe('MainSheet', () => {
  let mainSheet;
  beforeEach(() => {
    mainSheet = new global.MainSheet();
  });

  test('getASINList returns valid ASINs', () => {
    const asinList = mainSheet.getASINList();
    expect(asinList).toContain('B000EXAMPLE1');
    expect(asinList).toContain('B000EXAMPLE2');
  });

  test('writeSalesNums updates sheet', () => {
    const salesNums = { 'B000EXAMPLE1': 5 };
    mainSheet.writeSalesNums(salesNums);
    expect(mainSheet.sheet.getRange).toHaveBeenCalled();
  });
}); 