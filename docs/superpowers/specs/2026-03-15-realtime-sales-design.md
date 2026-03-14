# リアルタイム売上モニタリング機能 設計書

## 概要

10分間隔でOrders API（searchOrders）を使用し、ASIN別の本日売上個数・売上価格を取得して指定シートに上書き記録する機能。

既存の Sales API（`/sales/v1/orderMetrics`）ではなく Orders API を使用する理由: orderMetrics は集計データであり反映に数時間のラグがある。Orders API は注文単位でリアルタイムに取得できるため、10分間隔のモニタリングに適している。

## 記録先

- スプレッドシートID: `1Z3P0iL19r3gA9-NG8x2e_42pGhrEs_wFMLWLbFvReAw`
- シート名: `売上/今`
- フォーマット:
  - A列: ASIN（既存、読み取り専用）
  - B列: 売上個数（上書き）
  - C列: 売上価格（上書き、JPY税込）

## データフロー

```
GASトリガー（10分間隔）
  → main.js: updateRealtimeSales()
    → UpdateRealtimeSalesUseCase.execute()
      → RealtimeSalesSheet: A列からASINリスト取得
      → OrdersDownloader: searchOrders で本日の注文取得
      → OrdersDownloader: getOrderItems で各注文の商品詳細取得
      → ASIN別に売上個数・売上価格を集計（Canceled除外）
      → RealtimeSalesSheet: B列・C列に上書き
```

毎回本日0:00（JST）から全件再取得する設計。シンプルさと冪等性を優先し、差分管理の複雑さを避ける。

## ファイル構成

```
src/
├── domain/
│   ├── entities/
│   │   └── Order.js                    # 注文エンティティ
│   ├── value_objects/
│   │   └── RealtimeSalesResult.js      # ASIN別集計結果
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

### Order.js（エンティティ）

注文エンティティ。APIレスポンスからドメインオブジェクトへ変換。

- プロパティ: `orderId`, `orderStatus`, `purchaseDate`, `orderItems[]`
- 各orderItem: `asin`, `quantityOrdered`, `itemPriceAmount`（JPY税込）
- `isCanceled()`: Canceledステータス判定

### RealtimeSalesResult.js（値オブジェクト）

ASIN別の集計結果を保持。

- プロパティ: `asin`, `unitCount`, `totalAmount`
- 集計対象外のASINにはデフォルト値（0, 0）を設定

### OrderRepository.js

リポジトリインターフェース。`getOrdersWithItems(startDate)` メソッドを定義。

### OrdersDownloader.js

既存の `Downloader` 基底クラスを継承。

- `searchOrders`: `GET /orders/v0/orders` を呼び出し
  - パラメータ: `MarketplaceIds=A1VC38T7YXB528`, `CreatedAfter`（本日0:00 JST）
  - OrderStatusesパラメータは省略（デフォルトで全ステータス返却）
  - ページネーション: `NextToken` でループし全ページ取得（既存 `TransactionDownloader.getAllTransactions` のパターンを踏襲）
- `getOrderItems`: `GET /orders/v0/orders/{orderId}/orderItems`
  - 各注文のASIN, `QuantityOrdered`, `ItemPrice.Amount`（JPY）を抽出
  - 既存の `fetchAll` バッチ処理で効率化
- レート制限:
  - `getOrders`: バーストレート20、回復レート1リクエスト/5秒
  - `getOrderItems`: バーストレート30、回復レート2リクエスト/秒
  - バッチサイズを調整して制限内に収める

### RealtimeSalesSheet.js

シート名 `売上/今` のシートを操作。既存の `SheetConfig.getSheetByName()` を使用。

- `getAsinList()`: A列からASINリストを読み取り（ヘッダー行スキップ）
- `writeRealtimeSales(resultsMap)`: B列（売上個数）・C列（売上価格）を `setValues()` で一括上書き

### UpdateRealtimeSalesUseCase.js

オーケストレーション:

1. `RealtimeSalesSheet` からASINリスト取得
2. `OrdersDownloader` で本日0:00（JST）〜現在の全注文取得
3. 各注文のOrderItemsを取得し `Order` エンティティに変換
4. Canceled注文を除外
5. ASIN別に `RealtimeSalesResult`（unitCount, totalAmount）を集計
6. `RealtimeSalesSheet` にB列・C列を上書き

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

## GAS実行時間制限への対策

GASのスクリプト実行時間制限は6分（360秒）。注文数が多い場合のリスクに対する対策:

- `getOrderItems` のバッチサイズを既存の2から調整（`getOrderItems` はバーストレート30のため、より大きなバッチサイズが可能）
- 通常日の想定注文数: 〜50件。50件の場合 batchSize=10 で5バッチ、十分に制限内
- 異常に注文が多い日（100件超）でも、バーストレート30を活用すれば数十秒で完了

## 集計ロジック

- 注文一覧から各注文のOrderItemsを取得し `Order` エンティティに変換
- `order.isCanceled()` がtrueの注文は集計から除外
- OrderItemのASINがシートのA列に存在する場合のみ集計
- `QuantityOrdered` を売上個数として合算
- `ItemPrice.Amount`（JPY税込）を売上価格として合算

## テスト計画

- `OrdersDownloader`: API呼び出し・ページネーション・レスポンスパース のモックテスト
- `Order`: エンティティ変換・`isCanceled()` 判定のユニットテスト
- `RealtimeSalesResult`: 集計ロジックのユニットテスト
- `UpdateRealtimeSalesUseCase`: 全体フローの統合テスト（全依存をモック）
- `RealtimeSalesSheet`: シート読み書きのモックテスト
