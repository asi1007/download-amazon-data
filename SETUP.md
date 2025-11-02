# セットアップガイド

## 機密情報の管理

このプロジェクトでは、機密情報を2つの方法で管理します：

### 1. ローカル環境（`.env`ファイル）

ローカルでの開発とバックアップ用に`.env`ファイルを使用します。

**初回セットアップ：**

```bash
# .env.exampleをコピーして.envを作成
cp .env.example .env

# .envファイルを編集して実際の認証情報を入力
```

`.env`ファイルの内容：

```env
API_KEY=your_api_key_here
API_SECRET=your_api_secret_here
REFRESH_TOKEN=your_refresh_token_here
SHEET_ID=your_sheet_id_here
```

### 2. Google Apps Script（Script Properties）

Google Apps Scriptの本番環境では、Script Propertiesを使用します。

**設定手順：**

1. Google Apps Scriptエディタを開く
2. **プロジェクトの設定**（歯車アイコン）をクリック
3. **スクリプト プロパティ** セクションで「プロパティを追加」をクリック
4. `.env`ファイルの内容を元に、以下の3つのプロパティを追加：

| プロパティ名 | 説明 | 例 |
|------------|------|-----|
| `API_KEY` | Amazon SP-APIのAPIキー | `amzn1.application-oa2-client.xxxxx` |
| `API_SECRET` | Amazon SP-APIのAPIシークレット | `amzn1.oa2-cs.v1.xxxxx` |
| `REFRESH_TOKEN` | Amazon SP-APIのリフレッシュトークン | `Atzr\|xxxxx` |

### 🔒 セキュリティ注意事項

- ⚠️ `.env`ファイルは**絶対にGitHubにコミットしないでください**
- ✅ `.gitignore`に`.env`が含まれていることを確認済み
- ✅ `.env.example`はテンプレートとしてリポジトリに含まれます（実際の値は含まれません）
- ✅ Script Propertiesはプロジェクト単位で管理され、Gitには含まれません

## Amazon SP-API認証情報の取得方法

1. [Amazon Seller Central](https://sellercentral.amazon.co.jp/)にログイン
2. 設定 > ユーザー権限 > 開発者アカウント
3. アプリを作成してAPI認証情報を取得

## プロジェクトのデプロイ

```bash
# claspを使用してデプロイ
clasp push
```

