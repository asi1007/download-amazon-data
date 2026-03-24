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

- `writeSalesNums` 内のASINループで `salesNums[asin].totalSales.amount` を合算
- ループ後に `this.sheet.getRange(3, this.START_COLUMN).setValue(totalAmount)` で Row 3 に書き込み
- 変更箇所は `src/infrastructure/sheets/SalesSheet.js` の `writeSalesNums` メソッドのみ

## Python版の新規実装

### アーキテクチャ

個別リポジトリ方式を採用。DDDの原則に従い、ドメインごとにリポジトリを分離する。

### 新規コンポーネント

#### 共通基盤

- `py_src/infrastructure/api/sp_api_authenticator.py`
  - `SpApiAuthenticator`: SP-API認証ロジック（LWA token取得）
  - 既存 `OrdersRepository` の認証ロジックを抽出・共通化
  - リトライ処理（403: 再認証、429: バックオフ）を含む共通リクエストメソッド

#### Value Object

- `py_src/domain/value_objects/sales_info.py`
  - `SalesInfo`: `unit_count: int`, `total_sales_amount: float`, `order_count: int`
  - `RealtimeSalesResult` との違い: `SalesInfo` はAPI応答をそのままマッピングする読み取り専用の値オブジェクト。`RealtimeSalesResult` は注文データから集計する可変オブジェクト。

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
  - `SpApiPriceRepository`: `/products/pricing/v0/price` エンドポイント呼び出し
  - 既存 `OrdersRepository._fetch_prices` と同じエンドポイント・ロジックを移行
  - ASINリストを一括取得（20件ずつバッチ処理、レートリミット対策込み）
  - `SpApiAuthenticator` を使用

#### Infrastructure - Sheets

- `py_src/infrastructure/sheets/sales_sheet.py`
  - `SalesSheet`: `売上/日` シートへの書き込み
  - `get_asin_list() -> list[str]`: Column AからASIN取得
  - `write_sales_nums(asin_sales: dict[str, SalesInfo]) -> None`:
    - 新しいカラムを `START_COLUMN` に挿入
    - Row 1: 日付（dd形式）
    - Row 3: 全ASINの `total_sales_amount` 合計
    - Row 4: 日付（dd形式、ヘッダー行）
    - Row 5以降: ASINごとの `unit_count`
    - フィルターの保持・再設定
  - `write_prices(prices: dict[str, float]) -> None`:
    - 各ASINセルのノートに競合価格を記載
    - 前日との価格比較で背景色設定（赤: 値下げ、水色: 値上げ）
    - `PRICE_COLUMN` に現在価格を書き込み
  - `START_COLUMN` は「設定」シートの `B2` セルから取得
  - `PRICE_COLUMN` は「設定」シートの `B5` セルから取得

#### UseCase

- `py_src/usecases/update_daily_sales.py`
  - `UpdateDailySalesUseCase`:
    - コンストラクタ: `sales_sheet`, `sales_repository`, `price_repository`
    - `execute()`:
      1. `sales_sheet.get_asin_list()` でASINリスト取得
      2. 昨日の日付範囲を計算（JST基準）
      3. `sales_repository.get_daily_sales()` でASIN別売上取得
      4. `sales_sheet.write_sales_nums()` でシートに売上書き込み
      5. `price_repository.get_competitive_prices()` で価格取得
      6. `sales_sheet.write_prices()` で価格書き込み

#### エントリポイント

- `main.py` に `update_daily_sales()` 関数を追加

### 既存コードへの影響

- `OrdersRepository`:
  - `SpApiAuthenticator` を使うようにリファクタリング（認証ロジック委譲）
  - `get_prices()` メソッドを削除（`SpApiPriceRepository` に移行）
  - 外部インターフェースの `get_orders_with_items()` は変更なし

- `UpdateRealtimeSalesUseCase`:
  - 価格取得を `SpApiPriceRepository` 経由に変更
  - コンストラクタに `price_repository` を追加
  - `_fetch_prices_for_zero_items` 内の `self._repository.get_prices()` を `self._price_repository.get_competitive_prices()` に変更

- `main.py`:
  - `UpdateRealtimeSalesUseCase` の初期化時に `SpApiPriceRepository` を渡すよう変更

## テスト

- 全新規コンポーネントに対してpytestでテストを作成（TDD）
- 外部依存（SP-API, Google Sheets）はモックでテスト
- 既存テストも `OrdersRepository` リファクタリングに合わせて更新
- JS版の変更はJestでテスト

## データフロー

```
main.py (update_daily_sales)
  └── UpdateDailySalesUseCase.execute()
        ├── SalesSheet.get_asin_list()                        → ASINリスト
        ├── SpApiSalesRepository.get_daily_sales()            → dict[asin, SalesInfo]
        ├── SalesSheet.write_sales_nums(asin_sales)           → シート書き込み
        │     ├── Row 3: sum(total_sales_amount)
        │     └── Row 5+: unit_count per ASIN
        ├── SpApiPriceRepository.get_competitive_prices()     → dict[asin, float]
        └── SalesSheet.write_prices(prices)                   → 価格書き込み
              ├── Notes: prices per ASIN cell
              ├── Background color: price comparison
              └── PRICE_COLUMN: current price
```
