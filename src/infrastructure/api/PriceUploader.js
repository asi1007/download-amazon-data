class PriceUploader extends Downloader {
  constructor(sku, price) {
    const sellerid = "APS8L6SC4MEPF";
    const path = "/listings/2021-08-01/items/" + sellerid + "/" + sku;
    super(path);

    this.url = this.SP_API_URL + path;
    this.options.method = 'PATCH';
    const payload = {
      "productType": "PRODUCT",
      "patches": [{
        "op": "replace",
        "path": "/attributes/purchasable_offer",
        "value": [{
          "currency": "JPY",
          "our_price": [{
            "schedule": [{
              "value_with_tax": price
            }]
          }]
        }]
      }]
    };
    this.options.payload = JSON.stringify(payload);
  }

  uploadPrice() {
    this.setQueryParams([this.marketplaceIDs]);
    console.log(this.options);
    const response = this.getData();
    return response;
  }
}
