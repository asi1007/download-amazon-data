# Amazon SP-API Data Downloader

## プロジェクト概要
Amazon Selling Partner APIとGoogle Sheetsを統合し、売上、価格、在庫、コスト、広告データの自動取得・集計を行うGoogle Apps Scriptプロジェクト。

## 技術スタック
- JavaScript (Google Apps Script)
- Jest (テストフレームワーク)
- clasp (GASデプロイツール)

## 開発原則
- コードはドメイン駆動設計 (DDD) に基づいて構造化
- 各ドメインは Entity, ValueObject, Repository, UseCase 層に分離
- 外部依存（GAS API）はインターフェース化し、モックでテスト可能に
- クラス名・モジュール名はドメインの言葉を使用
- 各関数の中で呼び出す関数の粒度は同じになるように実装 (SLAP原則)
- docstringは書かない。コード自体が自己説明的になるよう変数名で意図を明確化

## フォルダ構造
```
src/
├── domain/
│   ├── entities/           # エンティティ（Transaction, Item, AmazonAdData等）
│   ├── value_objects/      # 値オブジェクト（CostData, SalesInfo等）
│   └── repositories/       # リポジトリインターフェース
├── usecases/               # ユースケース（売上更新、在庫更新等）
├── infrastructure/
│   ├── api/               # SP-API呼び出し実装
│   └── sheets/            # Google Sheets操作実装
├── main.js                # 公開関数（エントリポイント）
├── updatePrice.js         # 価格更新機能
└── event.js               # イベントハンドラー
tests/
└── *.test.js              # テストファイル
```

## 主要ドメイン用語
- ASIN: Amazon Standard Identification Number（商品識別子）
- SKU: Stock Keeping Unit（在庫管理単位）
- SP-API: Amazon Selling Partner API
- FBA: Fulfillment by Amazon

## Google Sheets シートID
- メインシート: `1aAliE0u45YbMwcBMczrLrG82MRMjOVc999L3GWCUENE`

## 主要な公開関数
| 関数名 | 説明 |
|--------|------|
| `updateYesterdaySalesNum()` | 昨日の売上データを更新 |
| `updateLastWeekSalesNum()` | 先週の売上データを更新 |
| `downloadPrices()` | 競合価格情報を取得して記録 |
| `updateInventoryStatus()` | FBA在庫状況を更新 |
| `updateWeeklyCostSummary()` | 週次コスト集計を実行 |
| `getAmazonAdData()` | 最新の広告データを取得 |

## バージョン管理
- バージョン情報は `package.json` の `version` フィールドで管理
- セマンティックバージョニングに従う: MAJOR.MINOR.PATCH
- コミット時にバージョン更新

## テスト
```bash
npm test           # テスト実行
npm run test:watch # ウォッチモード
npm run test:coverage # カバレッジ
```

## デプロイ
```bash
clasp push         # GASにプッシュ
clasp pull         # GASから取得
```
