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
| 関数名 | 説明 | 定期実行 |
|--------|------|---|
| `updateYesterdaySalesNum()` | 昨日の売上データを更新 | **Python `daily` に移行済み** |
| `updateLastWeekSalesNum()` | 先週の売上データを更新 | **Python `weekly` に移行済み** |
| `downloadPrices()` | 競合価格情報を取得して記録 | **Python `daily` の `write_prices` に移行済み** |
| `updateInventoryStatus()` | FBA在庫状況を更新 | **Python `inventory` に移行済み** |
| `updateWeeklyCostSummary()` | 週次コスト集計を実行 | GAS のみ（手動） |
| `getAmazonAdData()` | 最新の広告データを取得 | GAS のみ（手動） |
| `updatePrice()` | シートで選択した行の価格を Amazon へ PATCH | GAS のみ（手動・メニュー） |

### GAS の時間主導型トリガーは全廃した（2026-08-13）

上表の移行済み4本のトリガーを削除した。**再作成しないこと。** 定期実行の正本は launchd（Python）。

削除した理由は二重実行だけではない。**GAS の失敗は誰にも通知されない。** launchd 側は
`notify-on-failure.sh` が拾って daily note に出るが、GAS は実行数の画面を見に行かない限り無音で死ぬ。
実際に認証切れで**7日以上エラー率100%のまま放置**されていた（Python 側が同じ処理をしていたため実害は無かった）。

### GAS の認証情報は Script Properties。`.env` とは別物

`AuthService.js` は `PropertiesService.getScriptProperties()` から `API_KEY` / `API_SECRET` /
`REFRESH_TOKEN` を読む。**`.env` を更新しても GAS には反映されない。**

SP-API credentials を更新したら Script Properties も必ず更新する
（[プロジェクトの設定](https://script.google.com/home/projects/1nzmywONXeGV05dsg_4oAKJZPWWUefKaMmikxib74yvykTG4y5k672rcr/settings)）。
忘れると LWA が `401 {"error":"invalid_client"}` を返し、`updatePrice()` など GAS 固有機能が使えなくなる。
切り分け手順は auto-memory `reference_sp_api_credentials_update_procedure.md`。

## Python エントリポイント (`main.py`)
| サブコマンド | usecase | 用途 |
|---|---|---|
| なし（デフォルト） | `UpdateRealtimeSalesUseCase` | 「売上/今」を更新 |
| `daily` | `UpdateDailySalesUseCase` | 昨日の売上を「売上/日」へ追記＋競合価格を書く |
| `today` | `UpdateTodaySalesUseCase` | 本日の売上を「売上/日」へ毎時0分に上書き（**価格は書かない**、列が無ければ作る）|
| `weekly` | `UpdateWeeklySalesUseCase` | 週次売上集計 |
| `inventory` | `UpdateInventoryStatusUseCase` | FBA在庫を「納品状況」へ書き出し（GAS版の移植、2026-06-17 追加）|
| `ads` | `UpdateAdSalesUseCase` | 広告経由の売上個数を「売上/日」の広告行へ書く（直近14日を毎日上書き）|

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
  - **同じ日付を再実行しても列は増えない**（既存列を見つけて上書きする）。取りこぼしの埋め直しに何度でも使える
  - 「売上/日」の日付列構造は auto-memory `reference_sales_daily_sheet_structure.md` 参照

## 日次売上の取得と書き込み（v0.8.0〜）

`orderMetrics` は ASIN ごとに 1 リクエスト。75 ASIN で数分かかるため、途中の接続断で全体が落ちないようにしてある。

- **接続断・タイムアウトはリトライする。** `SpApiAuthenticator.request` が 429 / 403 に加えて `ConnectionError` / `Timeout` も再試行する（最大5回）
- **ASIN 単位の失敗は全体を止めない。** 失敗した ASIN だけを 1 度まとめて再試行する
- **再試行しても取れなかった ASIN はセルを空のままにする。** 結果 dict にキーを入れないことで、販売 0 件と取得失敗を区別する。**欠測を 0 と書かないこと**（0 を書くと後から欠測と見分けられない）
- **失敗が全 ASIN の 10% を超えたら `SalesFetchFailureError` で中断する。** 部分的に壊れた列を残さないため
- 欠測が出た日は `backfill_daily_sales.py <日付>` で埋め直す

### 書き込みは冪等。列を無条件に挿入しない

`ConnectionResetError(54)` は SP-API 側でも Google Sheets 側でも起きる。日次ジョブは SP-API 取得だけで4分かかるため、書き込み中に切断されると再実行のコストが高い。

- **対象日の列が既にあれば再利用し、無ければ挿入する**（`_resolve_column_for`）。同じ日付で何度実行しても列は増えない
- **列の挿入時に日付ラベル（行1・行4）も同時に書き込む。** 挿入だけ成功して落ちた場合、ラベルが無いと再試行時に見つけられず**列がもう1本入る**
- `_open_spreadsheet` / `write_sales_nums` / `write_prices` は `@retry_on_transient_error` で最大3回リトライする（30秒→60秒の指数バックオフ）。SP-API の再取得は挟まないので、4分の取得結果を捨てずに書き込みだけやり直せる
- **リトライ対象は「切断」だけではない。** Sheets 側は `requests` の例外ではなく `gspread.exceptions.APIError` で 503 を返す。`RETRIABLE_STATUS_CODES`（429 / 500 / 502 / 503 / 504）のみ再試行し、**403・404 は即座に上げる**（権限エラーやシートID誤りを再試行しても無駄で、無限リトライの温床になる）
- **シートを開く処理にもリトライが要る。** 2026-08-15 の日次ジョブは `client.open_by_key()` が 503 を返して落ちた。書き込み側だけ守っても、その手前で死ぬと 1 日分の列が丸ごと欠ける
- **gspread に自動リトライを仕込まないこと。** `BackOffHTTPClient` は experimental かつ 403 で無限リトライする既知問題がある。urllib3 の read リトライも、レスポンス読み取り中の切断では列の二重挿入を招く

### 同じ ASIN が複数行にあることを前提にする

「売上/日」の A列には**同じ ASIN が複数行に登場する**（2026-08-09 時点で `B0FBSCPJJH` が 7・8 行目、`B0F5P3RM78` が 13・56 行目）。

- `SalesSheet._asin_to_rows` は **ASIN → 行番号のリスト**。`dict[str, int]` に戻すと後の行が前の行を上書きし、**先に出てくる行が毎日空のまま**になる（実際にそうなっていた）
- 販売数・価格は重複した**全行に**書く
- `get_asin_list()` の戻り値は重複を除いたユニークな ASIN。SP-API へ同じ ASIN を2回問い合わせないため
- **総売上（3行目）はユニーク ASIN で合算する。** ASIN リストをそのまま回すと重複分が二重計上される

### 列の書式

日付ラベル（行1・行4）と総売上（行3）の `numberFormat` は、**書き込みのたびに `apply_column_formats()` で明示適用する**。列挿入時の隣接列からのフォーマット継承には依存しない（継承が効かず、シリアル値のまま表示される事故があった）。

**総売上（行3）はセルに円のまま書き、表示だけ千円単位にする**（`#,##0,"千円"`）。値を 1000 で割って書かないこと。他シートからの参照が円前提であり、Sheets の数値書式はカンマ1個で 1/1000 にスケールできるため、値を変える必要がない（万円単位は 10^4 で書式では表現できない）。

### 行2にはデータ取得時刻を書く（v0.19.0〜）

当日列は `today` が毎時0分に上書きするため、値だけでは「いつ時点の数字か」が分からない。
`write_sales_nums` は日付列の**行2**（`FETCH_TIME_ROW`）へ書き込み時刻を **`HH:MM`（JST）** の文字列で書く。
**日付は書かない**（バックフィルした列で日付と紛らわしくなるため、あえて時刻のみ）。
`_insert_labeled_column` が作るラベル列は行2を空のままにし、直後の `batch_update` で埋める。

**ASIN の個数書き込みは予約行（行1〜4）をまとめて避ける（`row > HEADER_ROW`、v0.19.2〜）。**
`get_asin_list()` は A列が10文字の文字列というだけで ASIN 行を判定しており、**ASIN が5行目以降にある
保証はコード上どこにも無い**（実運用でそうなっているだけの慣習）。仮に ASIN がこれらの予約行と同じ行に
来ても、ガードにより個数が上書きされることはない。このガードがあるため、`requests` に行1・行2・行4・
ASIN行のどれを先に積むかという**順序には依存しない**（v0.19.1では `TOTAL_AMOUNT_ROW`/`FETCH_TIME_ROW`
の2行だけを列挙するガードだったため行1・行4は無防備で、順序に依存する同じ罠が残っていた。
`row > HEADER_ROW` は「行1〜4は予約、ASINは5行目以降」という構造そのものを表現しており、
個別列挙より漏れが無い）。

**`write_prices` にも同じガードがある（v0.19.2〜）。** `write_prices` は `write_sales_nums` と同じ
`self._asin_to_rows` を回すため、ASIN が予約行に来た場合は価格列の値だけでなく、日付列のセルへ
**ノートと背景色**（値下げ=赤／値上げ=水色）まで書き込んでしまう。これは人が直接見るシートに
目に見える誤りとして出るため、`write_sales_nums` と同じ `row > HEADER_ROW` で対象行そのものを
`targets` から除外している。

### 価格の前日比較は「セルの値」ではなく「セルのノート」を読む

日付列の1つのセルに2つの情報が入っている。**取り違えると比較が成立しない。**

| 場所 | 内容 |
|---|---|
| セルの値 | その日の**売上個数**（0, 1, 2…） |
| セルのノート（コメント） | その日の**価格**（`379.0`, `2544.0`…） |

`write_prices` は前日列のノートを `get_notes(grid_range=...)` で読み、当日価格と比べて**値下げなら赤・値上げなら水色**に塗る。**セルの値（`worksheet.get`）を読んではいけない。** 価格は個数より必ず大きいため、全 ASIN が「値上げ」判定になり列全体が水色一色になる（GAS の `getNote()` を移植時に `.value` と取り違えて実際にそうなっていた。2026-08-12 修正）。

**塗る前に対象セルの背景色をクリアする**（`_clear_backgrounds`）。挿入した列は隣接列から書式を継承するため、クリアしないと価格が動いていない ASIN に前日の色が残る。`format` は `userEnteredFormat` にマージするだけで消せないので、`repeatCell` + `fields: userEnteredFormat.backgroundColor` を使う。

前日のノートが無い日（実行が落ちた日）は比較せず色を付けない。欠測を「変化なし」と描き分けられなくなるため。

## 広告経由の売上個数（v0.15.0〜）

「売上/日」は各 ASIN 行の直下に**広告行**を1本持つ（A列は空、商品名列に「広告経由」。
背景色は**行全体ではなく A列〜商品名列のみ**を薄いグレーで塗る（`insert_ad_rows.py` /
`write_sales_sheet.py` とも同じ範囲）。2026-09-03 時点で **77行**）。
`main.py ads` が Amazon Ads の `spAdvertisedProduct` レポート（DAILY）から
`unitsSoldSameSku14d` を取り、この行へ書く。資格情報の読み込みは `load_ads_credentials(path)`
（`py_src/infrastructure/api/ads_credentials_loader.py`）。

- **日付列は作らない。** 列を作るのは `main.py daily` の責務で、広告ジョブは既にある列に
  書き足すだけ。無い日付はスキップする
- **毎日、直近14日分を上書きする。** 広告の成果はクリックから14日後まで加算されるため、
  昨日分を1回書いて終わりにすると全ての過去日が過小のまま固定される
- **レポートに現れなかった ASIN には 0 を書く。** 空欄のままにすると「広告未出稿」なのか
  「取得に失敗した」のか後から見分けられないため
- **日次売上ジョブとは別ジョブにする設計**（`com.automation.download-amazon-data-ads`、毎日 2:00）。
  日次売上は SP-API だけで4分かかり10%失敗で中断する設計で、ここに Ads のレポート生成待ちを
  足すと片方の失敗が両方を巻き込む
- 資格情報は `data-engineer/dwld-ad-data/.env` を参照する（SP-API とは**別の** refresh_token）
- 広告行は「A列が空 かつ 商品名列が『広告経由』かつ 直前に ASIN 行がある」で特定する。
  位置だけに頼っていないので、空行が紛れ込んでも誤って書かない
- 行を足すのは `insert_ad_rows.py`（冪等。`--dry-run` あり）
- **広告経由の個数は同じ日の売上個数を超えないのが原則だが、少数は超えてよい。**
  売上個数は「注文日」、広告経由の個数は「クリック日」（14日以内の購入を加算）に紐づくため、
  クリックと購入が別日にまたがると超えることがある。実データ（77 ASIN × 14日 = 1078セル）で
  超えたのは **20セル（1.9%）**、いずれも数個の差。**大半のセルで超えていたら指標の取り違い**
- **レポートが `COMPLETED` かつ0行のときは書き込まない。** `AMAZON_PROFILE_ID` の誤り・スコープ変更・
  Amazon側障害だと、取得自体は失敗せず全日付・全ASINに0が書き込まれてしまう（欠測ゼロ埋めと見分けがつかず、
  翌日以降も自己修復しない）。`UpdateAdSalesUseCase` は指定範囲全体で1行も返らなかった場合
  `EmptyAdsReportError` を投げてシートに触らない。範囲内のどこか1件でも実データがあれば
  （値が0の行を含めて）書き込みは進む
- **日付列が無い日はスキップし、スキップした日数を最後に出力する。** `write_ad_units` は書き込みセル数に加えて
  スキップした日付の一覧を返し、`main.py ads` とバックフィルの両方がコンソールへ出す。
  01:00 の売上ジョブ（日付列を作る）が落ちた日は、02:00 の広告ジョブがその日をスキップしたことが
  ここで分かる
- **01:00 の売上ジョブが落ち、その日付列が14日以上経ってからバックフィルされた場合、広告ジョブの
  直近14日ローリング窓は既にその日を通り過ぎており、該当の広告行は永久に空欄のまま残る。** この系の
  「欠測に0を書かない＝空欄は取得失敗」という前提と衝突して見えるが、実際には取得済みの範囲を
  対象外にしただけ。直すには手動で `backfill_ad_sales.py <その日> <その日>` を実行するしかない

## launchd スケジュール
| plist | 実行 | スケジュール |
|---|---|---|
| `com.automation.download-amazon-data.plist` | `main.py`（リアルタイム売上） | 30分ごと |
| `com.automation.download-amazon-data-daily.plist` | `main.py daily`（昨日の売上＋競合価格） | 毎日 1:00 |
| `com.automation.download-amazon-data-today.plist` | `main.py today`（本日の売上を上書き、価格は書かない） | 毎時0分 |
| `com.automation.download-amazon-data-ads.plist` | `main.py ads`（広告経由の売上個数） | 毎日 2:00 |
| `com.automation.download-amazon-data-inventory.plist` | `main.py inventory` | 毎日 23:00 |
| `com.automation.update-weekly-sales.plist` | `main.py weekly` | 月曜 9:00 |

**`today` と `daily` は 1:00 に重なるが、通常は衝突しない。** 0:00 の `today` 実行で当日列（今日）が
先に最左へ作られ、1:00 の `daily` は昨日の列（既存の別列）を解決して書くため、書き込み先の列が
分かれる（`write_sales_nums` が対象日ごとに列を解決し、`write_prices` はその解決済み列を共有する。
詳細は本ファイル上部の列書式の節および `py_src/infrastructure/sheets/sales_sheet.py` 参照）。
衝突しうるのは「0:00 の `today` が落ちて当日列が未作成、かつ前日以前の列作成も失敗している」
という複合障害のときだけ。

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
