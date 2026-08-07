# Amazon SP-API Data Downloader

## プロジェクト概要
Amazon Selling Partner APIとGoogle Sheetsを統合し、売上、価格、在庫、コスト、広告データの自動取得・集計を行う**GAS + Pythonハイブリッド**プロジェクト。新規ユースケースは Python (`py_src/`) で実装し、GAS 側は段階廃止していく方針。

## 技術スタック
- **GAS 側**: JavaScript (Google Apps Script), Jest, clasp
- **Python 側**: Python 3.10+, gspread, oauth2client, python-dotenv, requests
- **スケジューラ**: launchd (`~/Library/LaunchAgents/com.automation.download-amazon-data*.plist`)

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
- 旧メインシート（GAS の SheetConfig 想定）: `1aAliE0u45YbMwcBMczrLrG82MRMjOVc999L3GWCUENE`
- 実運用シート（Python `.env` の `SPREADSHEET_ID`、GAS `SheetConfig.SHEET_ID`）: `1Z3P0iL19r3gA9-NG8x2e_42pGhrEs_wFMLWLbFvReAw`（売り上げ）
  - シート名: `売上/今` / `売上/日` / `Amazon広告` / `sales_data` / `納品状況`

## 主要な公開関数（GAS）
| 関数名 | 説明 |
|--------|------|
| `updateYesterdaySalesNum()` | 昨日の売上データを更新 |
| `updateLastWeekSalesNum()` | 先週の売上データを更新 |
| `downloadPrices()` | 競合価格情報を取得して記録 |
| `updateInventoryStatus()` | FBA在庫状況を更新（**Python版に移行済み**、GAS trigger は無効化推奨） |
| `updateWeeklyCostSummary()` | 週次コスト集計を実行 |
| `getAmazonAdData()` | 最新の広告データを取得 |

## Python エントリポイント (`main.py`)
| サブコマンド | usecase | 用途 |
|---|---|---|
| なし（デフォルト） | `UpdateRealtimeSalesUseCase` | 「売上/今」を更新 |
| `daily` | `UpdateDailySalesUseCase` | 昨日の売上を「売上/日」へ追記 |
| `weekly` | `UpdateWeeklySalesUseCase` | 週次売上集計 |
| `inventory` | `UpdateInventoryStatusUseCase` | FBA在庫を「納品状況」へ書き出し（GAS版の移植、2026-06-17 追加）|

実行例:
```bash
cd /Users/wadaatsushi/Documents/automation/data-engineer/download-amazon-data
.venv/bin/python main.py inventory
```

## Python バックフィル用スクリプト
- `backfill_daily_sales.py` — 任意日付の「売上/日」バックフィル（複数日対応、`batch_update` でクォータ回避）
  ```bash
  .venv/bin/python backfill_daily_sales.py 2026-06-18 2026-06-19
  ```
  - 既存列を上書きする場合は inline スクリプトで target_col を指定
  - 「売上/日」の日付列構造は auto-memory `reference_sales_daily_sheet_structure.md` 参照

## launchd スケジュール
| plist | 実行 | スケジュール |
|---|---|---|
| `com.automation.download-amazon-data.plist` | `main.py`（リアルタイム売上） | 30分ごと |
| `com.automation.download-amazon-data-inventory.plist` | `main.py inventory` | 毎日 23:00 |

```bash
launchctl start com.automation.download-amazon-data-inventory  # 手動即時実行
launchctl list com.automation.download-amazon-data-inventory   # 状態確認
```

ログ: `launchd.log` / `launchd.err` / `launchd-inventory.log` / `launchd-inventory.err`

## SP-API 認証情報の管理
- Solution Provider Portal の `download_sales_data` アプリ（ID `amzn1.sp.solution.5b32c349-575e-45ce-88bb-439d57bf94c1`）で管理
- `client_id` 末尾 `...946b33`、5プロジェクトで共有（auto-memory `reference_sp_api_credentials.md` 参照）
- 認証失敗時の切り分け手順は同 memory に詳細あり。SP-API が 403 + "The LWA secret token you provided has expired." を返したら、まず Solution Provider Portal で再 self-authorize を試す（取り消す ボタンは押さない）

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
