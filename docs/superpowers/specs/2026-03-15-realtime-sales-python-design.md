# リアルタイム売上モニタリング Python版 設計書

## 概要

GASで実装していたリアルタイム売上モニタリング機能をPythonに書き直す。
SP-APIのレートリミット制御をライブラリに委譲し、安定した動作を実現する。

## 実行環境

- ローカルPC（cron/launchdで10分間隔実行）
- 将来的にGoogle Cloud Functionsへ移行可能

## アーキテクチャ

```
.env (SP-API認証 + Google Sheets認証パス)
  |
main.py (エントリポイント)
  |
UpdateRealtimeSalesUseCase
  +-- OrderRepository (python-amazon-sp-api)
  |     searchOrders -> getOrderItems -> Order エンティティ
  +-- RealtimeSalesResult (値オブジェクト: ASIN別集計)
  +-- RealtimeSalesSheet (gspread)
        A列ASIN読取 -> B列個数/C列金額を上書き
```

## コンポーネント

| 層 | ファイル | 責務 |
|---|---|---|
| Entity | `domain/entities/order.py` | Order, OrderItem（API→ドメイン変換、is_canceled判定）|
| ValueObject | `domain/value_objects/realtime_sales_result.py` | ASIN別の売上個数・金額の集計 |
| Repository | `infrastructure/api/orders_repository.py` | SP-API呼び出し（python-amazon-sp-api使用）|
| Sheet | `infrastructure/sheets/realtime_sales_sheet.py` | gspreadでシート読み書き |
| UseCase | `usecases/update_realtime_sales.py` | オーケストレーション |
| Entry | `main.py` | .env読み込み → UseCase実行 |

## データフロー

1. シートA列からASINリスト取得
2. SP-API Orders で本日の全注文取得（ページネーション対応はライブラリが処理）
3. 各注文のOrderItems取得（ライブラリがレートリミット制御）
4. Canceled除外 → ASIN別に集計
5. B列（個数）・C列（金額）を上書き

## 依存ライブラリ

- `python-amazon-sp-api` — SP-APIラッパー（レートリミット自動制御）
- `gspread` + `oauth2client` — Google Sheets
- `python-dotenv` — .env読み込み

## 認証

### SP-API
- `.env` に `SP_API_REFRESH_TOKEN`, `LWA_APP_ID`, `LWA_CLIENT_SECRET` 等を保存

### Google Sheets
- `service_account.json` でサービスアカウント認証
- `.env` に `GOOGLE_CREDENTIALS_FILE` でパス指定

## 対象シート

- スプレッドシートID: `1Z3P0iL19r3gA9-NG8x2e_42pGhrEs_wFMLWLbFvReAw`
- シート名: `売上/今`
- A列: ASIN（読み取り専用）、B列: 売上個数、C列: 売上価格

## 実行方法

```bash
python main.py
```

cron設定（10分間隔）:
```
*/10 * * * * cd /path/to/project && python main.py
```
