# 実効価格ダウンロード & リアルタイム売上フォールバック

## 背景

リアルタイム売上（`updateRealtimeSales`）で Orders API を使用しているが、Pending 注文では `ItemPrice` が undefined になる。そのため売上金額が実際より大幅に低くなる。

## 解決策

2つの機能を追加する：

### 機能A: 実効価格の日次ダウンロード

SP-API `/products/pricing/v0/price` から自社出品価格を取得し、「売上/日」シートの「実効価格」列に書き込む。

**データフロー:**
```
SP-API (/products/pricing/v0/price)
  → EffectivePriceDownloader.getEffectivePricesOf(asinList)
  → { asin: price } のマップを返す
  → UpdateEffectivePriceUseCase.execute()
  → SalesSheet.writeEffectivePrices(asinToPrices)
  → 「売上/日」シートの「実効価格」列に書き込み
```

**公開関数:** `updateEffectivePrices()` を main.js に追加（1日1回トリガー設定）

### 機能B: リアルタイム売上の金額フォールバック

`ItemPrice` が undefined の注文について、「売上/日」シートの「実効価格」列から単価を取得し、`単価 × 数量` で金額を補完する。

**データフロー:**
```
UpdateRealtimeSalesUseCase.execute()
  → SalesSheet から ASIN→実効価格 マップを取得
  → OrderItem の itemPriceAmount が 0 の場合、実効価格 × quantity で補完
  → RealtimeSalesSheet に書き込み
```

## 新規ファイル

| ファイル | 説明 |
|----------|------|
| `src/infrastructure/api/EffectivePriceDownloader.js` | SP-API から自社出品価格を取得 |
| `src/usecases/UpdateEffectivePriceUseCase.js` | 実効価格更新ユースケース |

## 既存ファイルの変更

| ファイル | 変更内容 |
|----------|----------|
| `src/infrastructure/sheets/SalesSheet.js` | `getEffectivePrices()` と `writeEffectivePrices()` を追加 |
| `src/usecases/UpdateRealtimeSalesUseCase.js` | 実効価格フォールバックロジック追加 |
| `src/main.js` | `updateEffectivePrices()` 公開関数を追加 |

## API詳細

**エンドポイント:** `/products/pricing/v0/price`
- クエリ: `MarketplaceId`, `ItemType=Asin`, `Asins=ASIN1,ASIN2,...`
- レスポンス: `payload[].Product.Offers[].BuyingPrice.LandedPrice.Amount` または `ListingPrice.Amount`

## テスト

- EffectivePriceDownloader のレスポンスパースのテスト
- UpdateEffectivePriceUseCase の統合テスト
- UpdateRealtimeSalesUseCase のフォールバックロジックのテスト
