# 昨日の売上ダウンロード - 売上合計金額3行目記載

## 概要

JS版とPython版の両方で、昨日の売上個数ダウンロード時に売上合計金額をシートの3行目に記載する。
Python版は昨日の売上個数ダウンロード機能自体を新規作成する。

## 対象シート

- シート名: `売上/日`
- 行レイアウト:
  - Row 1: 日付
  - Row 2: 空白
  - Row 3: **売上合計金額（新規追加）**
  - Row 4: ヘッダー行（日付）
  - Row 5以降: ASINごとのunitCount

## JS版の変更

### `SalesSheet.writeSalesNums` の変更

- 全ASINの `totalSales.amount` を合計し、Row 3 の `START_COLUMN` に書き込む
- 変更箇所は `src/infrastructure/sheets/SalesSheet.js` の1メソッドのみ

## Python版の新規実装

### アーキテクチャ

個別リポジトリ方式を採用。DDDの原則に従い、ドメインごとにリポジトリを分離する。

### 新規コンポーネント

#### 共通基盤

- `py_src/infrastructure/api/sp_api_authenticator.py`
  - `SpApiAuthenticator`: SP-API認証ロジック（LWA token取得）
  - 既存 `OrdersRepository` の認証ロジックを抽出・共通化

#### Value Object

- `py_src/domain/value_objects/sales_info.py`
  - `SalesInfo`: `unit_count: int`, `total_sales_amount: float`, `order_count: int`

#### Repository インターフェース

- `py_src/domain/repositories/sales_repository.py`
  - `SalesRepository(Protocol)`: `get_daily_sales(asin_list, start_date, end_date) -> dict[str, SalesInfo]`

- `py_src/domain/repositories/price_repository.py`
  - `PriceRepository(Protocol)`: `get_competitive_prices(asin_list) -> dict[str, float]`

#### Infrastructure - API

- `py_src/infrastructure/api/sp_api_sales_repository.py`
  - `SpApiSalesRepository`: `/sales/v1/orderMetrics` エンドポイント呼び出し
  - ASINごとに `interval`, `granularity=Day`, `granularityTimeZone=Asia/Tokyo` で取得
  - `SpApiAuthenticator` を使用

- `py_src/infrastructure/api/sp_api_price_repository.py`
  - `SpApiPriceRepository`: `/products/pricing/v0/competitivePrice` エンドポイント呼び出し
  - ASINリストを一括取得（20件ずつバッチ処理）
  - `SpApiAuthenticator` を使用

#### Infrastructure - Sheets

- `py_src/infrastructure/sheets/sales_sheet.py`
  - `SalesSheet`: `売上/日` シートへの書き込み
  - `get_asin_list() -> list[str]`: Column Aからasin取得
  - `write_sales(asin_sales: dict[str, SalesInfo], prices: dict[str, float]) -> None`:
    - 新しいカラムを `START_COLUMN` に挿入
    - Row 1: 日付（dd形式）
    - Row 3: 全ASINの `total_sales_amount` 合計
    - Row 4: 日付（dd形式、ヘッダー行）
    - Row 5以降: ASINごとの `unit_count`
    - 各セルのノートに競合価格を記載
    - 前日との価格比較で背景色設定（赤: 値下げ、水色: 値上げ）
  - `START_COLUMN` は「設定」シートの `B2` セルから取得
  - `PRICE_COLUMN` は「設定」シートの `B5` セルから取得
  - フィルターの保持・再設定

#### UseCase

- `py_src/usecases/update_daily_sales.py`
  - `UpdateDailySalesUseCase`:
    - コンストラクタ: `sales_sheet`, `sales_repository`, `price_repository`
    - `execute()`:
      1. `sales_sheet.get_asin_list()` でASINリスト取得
      2. 昨日の日付範囲を計算（JST基準）
      3. `sales_repository.get_daily_sales()` でASIN別売上取得
      4. `price_repository.get_competitive_prices()` で価格取得
      5. `sales_sheet.write_sales()` でシートに書き込み

#### エントリポイント

- `main.py` に `update_daily_sales()` 関数を追加

### 既存コードへの影響

- `OrdersRepository`: `SpApiAuthenticator` を使うようにリファクタリング
  - 認証ロジックを `SpApiAuthenticator` に委譲
  - 外部インターフェースは変更なし

## テスト

- 全コンポーネントに対してpytestでテストを作成（TDD）
- 外部依存（SP-API, Google Sheets）はモックでテスト
- JS版の変更はJestでテスト

## データフロー

```
main.py (update_daily_sales)
  └── UpdateDailySalesUseCase.execute()
        ├── SalesSheet.get_asin_list()           → ASINリスト
        ├── SpApiSalesRepository.get_daily_sales() → dict[asin, SalesInfo]
        ├── SpApiPriceRepository.get_competitive_prices() → dict[asin, float]
        └── SalesSheet.write_sales()             → シート書き込み
            ├── Row 3: sum(total_sales_amount)
            ├── Row 5+: unit_count per ASIN
            └── Notes: competitive prices
```
