# Amazon SP-API データダウンロード自動化

Amazon Selling Partner API (SP-API) を使用して、売上データ、価格情報、トランザクション情報を自動でGoogle Sheetsに記録するGoogle Apps Scriptプロジェクトです。

## 機能

- 📊 **日次売上データ取得**: ASINごとの日次売上数を自動取得
- 📅 **週次売上集計**: 週次の売上データを集計してシートに保存
- 💰 **価格情報取得**: 競合価格情報を取得して記録
- 🔄 **トランザクションダウンロード**: 注文情報の詳細を取得

## プロジェクト構成

```
.
├── getSPAPIdata.js      # メインのSP-APIデータ取得スクリプト
├── updatePrice.js       # 価格更新スクリプト
├── event.js            # イベントハンドラー
├── appsscript.json     # Google Apps Script設定
├── SETUP.md           # セットアップガイド
└── README.md          # このファイル
```

## セットアップ

詳細なセットアップ手順は [SETUP.md](./SETUP.md) を参照してください。

### 必要な準備

1. Amazon SP-API開発者アカウント
2. Google Apps Scriptプロジェクト
3. Google Sheets（データ保存先）

### インストール

```bash
# 依存パッケージのインストール（テスト用）
npm install

# Google Apps Scriptへのデプロイ
clasp push
```

## 使い方

### 手動実行

Google Apps Scriptエディタから以下の関数を実行：

- `updateYesterdaySalesNum()`: 昨日の売上データを更新
- `updateLastWeekSalesNum()`: 先週の売上データを更新
- `downloadPrices()`: 最新の価格情報を取得

### トリガー設定

定期実行するにはトリガーを設定：

1. Google Apps Scriptエディタで「トリガー」を開く
2. 「トリガーを追加」をクリック
3. 実行する関数とスケジュールを設定

## テスト

```bash
# テストの実行
npm test

# カバレッジ付きでテスト実行
npm test -- --coverage
```

## セキュリティ

- API認証情報はScript Propertiesに保存（リポジトリには含まれません）
- `.gitignore`で機密情報を含むファイルを除外

## ライセンス

Private Project

## 作者

wadaatsushi
