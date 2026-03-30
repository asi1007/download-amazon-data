# リアルタイム売上 Python移行 設計書

## 概要

GASの `updateRealtimeSales()` をPythonに完全移行する。
Orders API ではなく orderMetrics API を使用し、金額は自社価格×個数で算出する。

## データフロー

```
main.py
  → UpdateRealtimeSalesUseCase.execute()
    1. RealtimeSalesSheet.get_asin_list()     ← 「売上/今」A列
    2. SalesSheet.get_selling_prices()         ← 「売上/日」自社価格列
    3. SpApiSalesRepository.get_daily_sales()  ← /sales/v1/orderMetrics
    4. unitCount × 自社価格 で金額算出
    5. RealtimeSalesSheet.write_realtime_sales() → C列(個数), D列(金額)
```

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `py_src/usecases/update_realtime_sales.py` | OrdersRepository → SpApiSalesRepository。SalesSheet から自社価格取得。金額 = unitCount × 自社価格 |
| `py_src/infrastructure/sheets/realtime_sales_sheet.py` | 書き込み列を C列(3)・D列(4) に変更 |
| `py_src/infrastructure/sheets/sales_sheet.py` | `get_selling_prices()` メソッド追加（自社価格列をバッチ読み取り） |
| `main.py` | OrdersRepository → SpApiSalesRepository に差し替え、SalesSheet を追加 |

## 削除する依存

- `UpdateRealtimeSalesUseCase` から `OrdersRepository` の依存を除去
- `PriceRepository` の依存を除去（competitive price フォールバック不要）
- `_fetch_prices_for_zero_items` ロジックを削除

## コンポーネント詳細

### UpdateRealtimeSalesUseCase

```python
class UpdateRealtimeSalesUseCase:
    def __init__(self, realtime_sheet, sales_repository, sales_sheet):
        # realtime_sheet: RealtimeSalesSheet（売上/今）
        # sales_repository: SpApiSalesRepository（orderMetrics）
        # sales_sheet: SalesSheet（売上/日、自社価格読み取り）

    def execute(self):
        asin_list = self._realtime_sheet.get_asin_list()
        selling_prices = self._sales_sheet.get_selling_prices()
        today_range = self._get_today_range()
        sales_infos = self._sales_repository.get_daily_sales(asin_list, *today_range)
        sales_map = self._build_sales_map(asin_list, sales_infos, selling_prices)
        self._realtime_sheet.write_realtime_sales(sales_map)
```

### SalesSheet.get_selling_prices()

- 「売上/日」シートのヘッダー行（4行目）から「自社価格」列を特定
- ASIN列と自社価格列をバッチ読み取り
- `dict[str, float]` を返す（ASIN → 単価）

### RealtimeSalesSheet.write_realtime_sales()

- 2行目以降のA列を読み取り、ASINと行を照合
- C列（個数）・D列（金額）に書き込み
- 1行目（ヘッダー）はスキップ

## SP-API

- エンドポイント: `/sales/v1/orderMetrics`
- 既存の `SpApiSalesRepository.get_daily_sales()` をそのまま使用
- 1 ASIN あたり1リクエスト、4秒スリープ

## 実行環境

- ローカルPC、cron/launchd で10分間隔
- `python main.py` で実行

## テスト

- `UpdateRealtimeSalesUseCase`: SpApiSalesRepository と SalesSheet をモック、金額計算の正確性を検証
- `SalesSheet.get_selling_prices()`: ワークシートをモック、ASIN→価格マッピングを検証
- `RealtimeSalesSheet.write_realtime_sales()`: C列・D列への書き込みを検証
