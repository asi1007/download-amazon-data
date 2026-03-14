# リアルタイム売上モニタリング機能 設計書

## 概要

10分間隔でOrders API（searchOrders）を使用し、ASIN別の本日売上個数・売上価格を取得して指定シートに上書き記録する機能。

## 記録先

- スプレッドシートID: `1Z3P0iL19r3gA9-NG8x2e_42pGhrEs_wFMLWLbFvReAw`
- シート: gid=1690091876
- フォーマット:
  - A列: ASIN（既存、読み取り専用）
  - B列: 売上個数（上書き）
  - C列: 売上価格（上書き）

## データフロー

```
GASトリガー（10分間隔）
  → main.js: updateRealtimeSales()
    → UpdateRealtimeSalesUseCase.execute()
      → RealtimeSalesSheet: A列からASINリスト取得
      → OrdersDownloader: searchOrders で本日の注文取得
      → ASIN別に売上個数・売上価格を集計
      → RealtimeSalesSheet: B列・C列に上書き
```

## ファイル構成

```
src/
├── domain/
│   └── repositories/
│       └── OrderRepository.js          # リポジトリインターフェース
├── infrastructure/
│   ├── api/
│   │   └── OrdersDownloader.js         # Orders API呼び出し
│   └── sheets/
│       └── RealtimeSalesSheet.js        # シート読み書き
├── usecases/
│   └── UpdateRealtimeSalesUseCase.js    # 集計・オーケストレーション
└── main.js                              # エントリポイント追加
```

## 各クラスの責務

### OrderRepository.js

リポジトリインターフェース。`getOrders(startDate, endDate)` メソッドを定義。

### OrdersDownloader.js

既存の `Downloader` 基底クラスを継承。

- `searchOrders`: `GET /orders/v0/orders` を呼び出し
  - パラメータ: `MarketplaceIds=A1VC38T7YXB528`, `CreatedAfter`（本日0:00 JST）, `OrderStatuses`（全ステータス）
  - ページネーション: `NextToken` で全ページ取得
- `getOrderItems`: `GET /orders/v0/orders/{orderId}/orderItems`
  - 各注文のASIN, `QuantityOrdered`, `ItemPrice.Amount` を抽出
  - 既存の `fetchAll` バッチ処理で効率化
- レート制限: `getOrders` 1/5秒、`getOrderItems` 1/2秒

### RealtimeSalesSheet.js

gid=1690091876のシートを操作。

- `getAsinList()`: A列からASINリストを読み取り（ヘッダー行スキップ）
- `writeRealtimeSales(salesMap)`: B列（売上個数）・C列（売上価格）を `setValues()` で一括上書き

### UpdateRealtimeSalesUseCase.js

オーケストレーション:

1. `RealtimeSalesSheet` からASINリスト取得
2. `OrdersDownloader` で本日0:00（JST）〜現在の全注文取得
3. 各注文のOrderItemsを取得
4. ASIN別に `{ unitCount, totalAmount }` を集計
5. `RealtimeSalesSheet` にB列・C列を上書き

### main.js（追加分）

- `updateRealtimeSales()`: エントリポイント（公開関数）
- `setupRealtimeSalesTrigger()`: 10分間隔トリガーを登録する関数

## トリガー設定

- `ScriptApp.newTrigger('updateRealtimeSales').timeBased().everyMinutes(10).create()`
- `setupRealtimeSalesTrigger()` を手動で1回実行して登録

## エラーハンドリング

- API失敗時はログ出力し、取得できた分だけシートに反映
- 全体失敗時は既存データを消さない（書き込みをスキップ）
- 既存の `Downloader` 基底クラスのリトライ（最大3回、指数バックオフ）を活用

## 集計ロジック

- 注文一覧から各注文のOrderItemsを取得
- OrderItemのASINがシートのA列に存在する場合のみ集計
- `QuantityOrdered` を売上個数として合算
- `ItemPrice.Amount` を売上価格として合算
