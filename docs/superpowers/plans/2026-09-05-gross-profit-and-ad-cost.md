# 粗利益と広告費の行を並べる 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 「売上/日」の各 ASIN を4行（売上個数 / 広告経由 / 粗利益 / 広告費）にし、粗利益は当日は見積で入れて後から14日分を実測で上書きする。

**Architecture:** ラベル行の解決（A列が空・商品名列がラベル・直前に ASIN 行）は既に `AdSalesSheet` にある考え方を共有モジュールへ出し、広告費・粗利益の書き込みが同じ仕組みに乗るようにする。広告費は既存の Ads レポートに `cost` 列を足すだけで取れる。粗利益の実測は Orders API の注文一覧（注文ID→注文日）と Finances API のイベント（注文ID→手数料）を突き合わせ、SKU をシートの SKU 列で ASIN に引き当てる。

**Tech Stack:** Python 3.14 / gspread 6.2 / requests / pytest / launchd

**Spec:** `docs/superpowers/specs/2026-09-05-gross-profit-and-ad-cost-design.md`

## Global Constraints

- 作業対象は `data-engineer/download-amazon-data`（**親の automation とは別リポジトリ**、ブランチ `refactor/ddd-structure`）。Task 12 のみ親リポジトリ側
- DDD 構成に従う。`py_src/domain/` `py_src/usecases/` `py_src/infrastructure/`
- **docstring は書かない。** 型ヒントは必須
- 各関数の中で呼ぶ関数の粒度を揃える（SLAP）
- **スプレッドシートの列はヘッダー行（4行目）の列名で引く。** 列インデックス固定は禁止
- gspread の書き込みは `batch_update` にまとめる
- **予約行（1〜4行）には書かない。** 既存のガードは `row > HEADER_ROW`
- **欠測に 0 を書かない。** 手数料や原価が空なら粗利益のセルは**空**にする（0 だと利益が過大に見える）
- **外向きの HTTP には必ずタイムアウトを付ける**（`SP_API_REQUEST_TIMEOUT_SECONDS` / `GOOGLE_SHEETS_TIMEOUT_SECONDS` が既にある）
- コミットのたびに `pyproject.toml` の `version` を更新する（**実ファイルの現在値を確認してから**。現在 `0.20.4`）
- テストは `py_tests/` に pytest。ワークシートと HTTP セッションは `Mock` で差し替える
- `git add` は**ファイルを個別にパス指定**。`git add -A` / `git commit -a` は使わない。コミット前に `git diff --cached --name-only` を確認
- コミットメッセージは日本語。末尾に:
  ```
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01Hf9ADaWTRwggKigRAw3nD4
  ```
- **実運用シートに書くコマンドは実行しない**（`main.py` 各種 / `insert_*.py` / `backfill_*.py` / `sync_agents.py` / `launchctl`）。controller が実行する

---

### Task 1: ラベル行の共有モジュール

**Files:**
- Create: `py_src/infrastructure/sheets/label_rows.py`
- Modify: `py_src/infrastructure/sheets/ad_sales_sheet.py`
- Test: `py_tests/test_label_rows.py`

**Interfaces:**
- Produces:
  - 定数 `HEADER_ROW = 4` / `ASIN_COLUMN = 1` / `PRODUCT_NAME_HEADER = "商品名"` / `ASIN_LENGTH = 10`
  - 定数 `AD_ROW_LABEL = "広告経由"` / `GROSS_PROFIT_ROW_LABEL = "粗利益"` / `AD_COST_ROW_LABEL = "広告費"`
  - `ROW_LABELS_IN_ORDER: tuple[str, ...] = (AD_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL)`
  - `date_serial(day: date) -> int`
  - `bind_label_rows(asin_values: list[str], name_values: list[str], label: str) -> dict[str, list[int]]`
  - `read_date_columns(worksheet) -> dict[int, int]`（シリアル値 → 列番号）
  - `find_column(headers: list[str], name: str) -> int`

いまの `AdSalesSheet._bind_ad_rows` は 広告経由 に固定されている。ラベルを引数にして、3種類の行すべてに使えるようにする。**振る舞いは変えない。**

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_label_rows.py`:

```python
from datetime import date
from unittest.mock import Mock

from py_src.infrastructure.sheets.label_rows import (
    AD_COST_ROW_LABEL,
    AD_ROW_LABEL,
    GROSS_PROFIT_ROW_LABEL,
    ROW_LABELS_IN_ORDER,
    bind_label_rows,
    date_serial,
    find_column,
    read_date_columns,
)

# 行1〜4は予約。行5以降が ASIN と3本のラベル行の繰り返し
ASIN_VALUES = ["", "", "", "ASIN", "B00EXAMPLE", "", "", "", "見出し", "B00EXAMPLF", "", "", ""]
NAME_VALUES = [
    "", "", "", "商品名", "ルーペ", AD_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL,
    "", "ボールネット", AD_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL,
]


class TestBindLabelRows:
    def test_binds_each_label_to_its_own_rows(self) -> None:
        assert bind_label_rows(ASIN_VALUES, NAME_VALUES, AD_ROW_LABEL) == {
            "B00EXAMPLE": [6], "B00EXAMPLF": [11],
        }
        assert bind_label_rows(ASIN_VALUES, NAME_VALUES, GROSS_PROFIT_ROW_LABEL) == {
            "B00EXAMPLE": [7], "B00EXAMPLF": [12],
        }
        assert bind_label_rows(ASIN_VALUES, NAME_VALUES, AD_COST_ROW_LABEL) == {
            "B00EXAMPLE": [8], "B00EXAMPLF": [13],
        }

    def test_heading_row_breaks_the_binding(self) -> None:
        asin_values = ["", "", "", "ASIN", "見出し", "", ""]
        name_values = ["", "", "", "商品名", "", AD_ROW_LABEL, ""]

        assert bind_label_rows(asin_values, name_values, AD_ROW_LABEL) == {}

    def test_same_asin_twice_gets_both_rows(self) -> None:
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", "", "B00EXAMPLE", ""]
        name_values = ["", "", "", "商品名", "ルーペ", AD_ROW_LABEL, "ルーペ2", AD_ROW_LABEL]

        assert bind_label_rows(asin_values, name_values, AD_ROW_LABEL) == {
            "B00EXAMPLE": [6, 8],
        }

    def test_row_with_asin_is_never_a_label_row(self) -> None:
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", "B00EXAMPLF"]
        name_values = ["", "", "", "商品名", "ルーペ", AD_ROW_LABEL]

        assert bind_label_rows(asin_values, name_values, AD_ROW_LABEL) == {}


class TestRowLabelsInOrder:
    def test_order_matches_the_spec(self) -> None:
        assert ROW_LABELS_IN_ORDER == (
            AD_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL,
        )


class TestDateSerial:
    def test_known_dates(self) -> None:
        assert date_serial(date(2026, 9, 2)) == 46267
        assert date_serial(date(2026, 9, 5)) == 46270


class TestReadDateColumns:
    def test_integers_in_header_row_are_date_columns(self) -> None:
        worksheet = Mock()
        worksheet.row_values.return_value = ["ASIN", "商品名", "目標販売数", 46270, 46269]

        assert read_date_columns(worksheet) == {46270: 4, 46269: 5}


class TestFindColumn:
    def test_finds_by_name(self) -> None:
        assert find_column(["ASIN", "商品名", "SKU"], "SKU") == 3

    def test_missing_raises(self) -> None:
        try:
            find_column(["ASIN"], "SKU")
        except ValueError as error:
            assert "SKU" in str(error)
        else:
            raise AssertionError("ValueError が上がらなかった")
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_label_rows.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 実装する**

`py_src/infrastructure/sheets/label_rows.py`:

```python
from __future__ import annotations
from datetime import date

from gspread import Worksheet
from gspread.utils import ValueRenderOption

HEADER_ROW = 4
ASIN_COLUMN = 1
PRODUCT_NAME_HEADER = "商品名"
ASIN_LENGTH = 10
SHEETS_EPOCH = date(1899, 12, 30)

AD_ROW_LABEL = "広告経由"
GROSS_PROFIT_ROW_LABEL = "粗利益"
AD_COST_ROW_LABEL = "広告費"
ROW_LABELS_IN_ORDER: tuple[str, ...] = (
    AD_ROW_LABEL,
    GROSS_PROFIT_ROW_LABEL,
    AD_COST_ROW_LABEL,
)


def date_serial(day: date) -> int:
    return (day - SHEETS_EPOCH).days


def bind_label_rows(
    asin_values: list[str], name_values: list[str], label: str
) -> dict[str, list[int]]:
    label_rows: dict[str, list[int]] = {}
    current_asin = ""
    for index in range(max(len(asin_values), len(name_values))):
        row = index + 1
        asin = asin_values[index].strip() if index < len(asin_values) else ""
        name = name_values[index].strip() if index < len(name_values) else ""
        if len(asin) == ASIN_LENGTH:
            current_asin = asin
            continue
        if asin:
            current_asin = ""
            continue
        if name == label and current_asin:
            label_rows.setdefault(current_asin, []).append(row)
    return label_rows


def read_date_columns(worksheet: Worksheet) -> dict[int, int]:
    header = worksheet.row_values(
        HEADER_ROW, value_render_option=ValueRenderOption.unformatted
    )
    return {
        value: index
        for index, value in enumerate(header, start=1)
        if isinstance(value, int)
    }


def find_column(headers: list[str], name: str) -> int:
    for index, value in enumerate(headers, start=1):
        if str(value).strip() == name:
            return index
    raise ValueError(f"ヘッダーに '{name}' が見つかりません")
```

- [ ] **Step 4: `AdSalesSheet` をこのモジュールに載せ替える**

`ad_sales_sheet.py` の定数と `_bind_ad_rows` / `_read_date_columns` / `_find_column` / `_date_serial` を削り、`label_rows` から import して使う。`get_ad_rows` は `bind_label_rows(asin_values, name_values, AD_ROW_LABEL)` を呼ぶ形にする。

**公開インターフェース（`get_ad_rows` / `write_ad_units` の名前と戻り値）は変えない。** `AD_ROW_LABEL` を `ad_sales_sheet` から import している箇所（`insert_ad_rows.py`）が壊れないよう、`ad_sales_sheet` 側で再 export するか、import 元を `label_rows` に付け替える。**どちらにしたか報告すること。**

- [ ] **Step 5: 全スイートが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/ -v`
Expected: 既存テストが1件も落ちない（振る舞いを変えていないので）

- [ ] **Step 6: コミット**

```bash
git add py_src/infrastructure/sheets/label_rows.py py_src/infrastructure/sheets/ad_sales_sheet.py py_tests/test_label_rows.py pyproject.toml
git commit -m "refactor: ラベル行の解決を共有モジュールへ切り出す"
```

---

### Task 2: 移行スクリプトを全ラベル行に一般化する

**Files:**
- Modify: `insert_ad_rows.py`
- Test: `py_tests/test_insert_ad_rows.py`

**Interfaces:**
- Consumes: `ROW_LABELS_IN_ORDER` / `bind_label_rows` / 定数（Task 1）
- Produces: `plan_label_row_insertions(asin_values: list[str], name_values: list[str]) -> list[tuple[int, int]]`（(ASIN 行の直後に続くラベル行の最後の行番号, 不足数) の**降順**）
- Produces: `existing_label_run(index: int, name_values: list[str]) -> int`（ASIN 行の直下から `ROW_LABELS_IN_ORDER` の順に何個そろっているか）

いまのスクリプトは「1 ASIN に広告行1本」に特化している。**各 ASIN の直下に `ROW_LABELS_IN_ORDER` の3本が順番どおり並ぶ**ようにする。

- 3本ともそろっていれば何もしない
- 現在の状態（`広告経由` だけある）なら **2本足す**
- 1本も無ければ 3本足す

**既にある行は動かさない。** 広告経由の行には実データが入っているので、その下に足す。

ユーザーの判断で、既存の復旧ロジック（挿入済みだが未ラベルの行を拾う）は**一般化の過程で失われて構わない**。このスクリプトは今回の移行後は使わない見込みのため。ただし**冪等性（何度実行しても増えない）は必ず保つこと**。

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_insert_ad_rows.py` を書き直す（既存のテストは1ラベル前提なので置き換える）:

```python
from insert_ad_rows import (
    build_insert_requests,
    existing_label_run,
    label_row_numbers,
    plan_label_row_insertions,
)
from py_src.infrastructure.sheets.label_rows import (
    AD_COST_ROW_LABEL,
    AD_ROW_LABEL,
    GROSS_PROFIT_ROW_LABEL,
)


class TestExistingLabelRun:
    def test_counts_labels_present_in_order(self) -> None:
        names = ["", "", "", "商品名", "ルーペ", AD_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, ""]

        assert existing_label_run(4, names) == 2

    def test_zero_when_next_row_is_not_the_first_label(self) -> None:
        names = ["", "", "", "商品名", "ルーペ", "メモ"]

        assert existing_label_run(4, names) == 0

    def test_stops_at_the_first_mismatch(self) -> None:
        # 順番が違えば、そこで打ち切る
        names = ["", "", "", "商品名", "ルーペ", AD_ROW_LABEL, AD_COST_ROW_LABEL]

        assert existing_label_run(4, names) == 1

    def test_all_three_present(self) -> None:
        names = [
            "", "", "", "商品名", "ルーペ",
            AD_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL,
        ]

        assert existing_label_run(4, names) == 3


class TestPlanLabelRowInsertions:
    def test_adds_the_missing_two_for_the_current_sheet(self) -> None:
        # いまの状態: 各 ASIN の下に 広告経由 が1本だけ
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", "", "B00EXAMPLF", ""]
        name_values = ["", "", "", "商品名", "ルーペ", AD_ROW_LABEL, "ボール", AD_ROW_LABEL]

        assert plan_label_row_insertions(asin_values, name_values) == [(8, 2), (6, 2)]

    def test_adds_all_three_when_none_present(self) -> None:
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE"]
        name_values = ["", "", "", "商品名", "ルーペ"]

        assert plan_label_row_insertions(asin_values, name_values) == [(5, 3)]

    def test_nothing_to_do_when_all_present(self) -> None:
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", "", "", ""]
        name_values = [
            "", "", "", "商品名", "ルーペ",
            AD_ROW_LABEL, GROSS_PROFIT_ROW_LABEL, AD_COST_ROW_LABEL,
        ]

        assert plan_label_row_insertions(asin_values, name_values) == []

    def test_ignores_heading_rows(self) -> None:
        asin_values = ["", "", "", "ASIN", "様子見", "やめる"]
        name_values = ["", "", "", "商品名", "", ""]

        assert plan_label_row_insertions(asin_values, name_values) == []

    def test_does_not_overwrite_unrelated_content_below_an_asin(self) -> None:
        # 直下に別の文字がある場合、ラベルは0本とみなして上に挿入する（上書きしない）
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", ""]
        name_values = ["", "", "", "商品名", "ルーペ", "メモ"]

        assert plan_label_row_insertions(asin_values, name_values) == [(5, 3)]


class TestBuildInsertRequests:
    def test_inserts_the_missing_count_below_the_run(self) -> None:
        requests = build_insert_requests(sheet_id=551300985, plan=[(8, 2), (6, 2)])

        ranges = [r["insertDimension"]["range"] for r in requests]
        assert ranges[0] == {
            "sheetId": 551300985, "dimension": "ROWS", "startIndex": 8, "endIndex": 10,
        }
        assert ranges[1] == {
            "sheetId": 551300985, "dimension": "ROWS", "startIndex": 6, "endIndex": 8,
        }

    def test_does_not_inherit_formatting(self) -> None:
        requests = build_insert_requests(sheet_id=1, plan=[(5, 3)])

        assert requests[0]["insertDimension"]["inheritFromBefore"] is False


class TestLabelRowNumbers:
    def test_returns_row_and_label_pairs_after_the_shift(self) -> None:
        # 行6の下に2本、行8の下に2本入れると、
        # 1件目は行7=粗利益/行8=広告費、2件目は行11=粗利益/行12=広告費
        assert label_row_numbers([(8, 2), (6, 2)]) == [
            (7, GROSS_PROFIT_ROW_LABEL),
            (8, AD_COST_ROW_LABEL),
            (11, GROSS_PROFIT_ROW_LABEL),
            (12, AD_COST_ROW_LABEL),
        ]

    def test_all_three_labels_when_nothing_existed(self) -> None:
        assert label_row_numbers([(5, 3)]) == [
            (6, AD_ROW_LABEL),
            (7, GROSS_PROFIT_ROW_LABEL),
            (8, AD_COST_ROW_LABEL),
        ]
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_insert_ad_rows.py -v`
Expected: FAIL

- [ ] **Step 3: 実装する**

```python
def existing_label_run(index: int, name_values: list[str]) -> int:
    run = 0
    for offset, label in enumerate(ROW_LABELS_IN_ORDER, start=1):
        position = index + offset
        name = name_values[position].strip() if position < len(name_values) else ""
        if name != label:
            break
        run += 1
    return run


def plan_label_row_insertions(
    asin_values: list[str], name_values: list[str]
) -> list[tuple[int, int]]:
    plan: list[tuple[int, int]] = []
    for index, value in enumerate(asin_values):
        if len(value.strip()) != ASIN_LENGTH:
            continue
        run = existing_label_run(index, name_values)
        missing = len(ROW_LABELS_IN_ORDER) - run
        if missing:
            plan.append((index + 1 + run, missing))
    return sorted(plan, reverse=True)


def build_insert_requests(sheet_id: int, plan: list[tuple[int, int]]) -> list[dict]:
    return [
        {
            "insertDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": row,
                    "endIndex": row + count,
                },
                "inheritFromBefore": False,
            }
        }
        for row, count in plan
    ]


def label_row_numbers(plan: list[tuple[int, int]]) -> list[tuple[int, str]]:
    ascending = sorted(plan)
    numbered: list[tuple[int, str]] = []
    shift = 0
    for row, count in ascending:
        for offset in range(count):
            label = ROW_LABELS_IN_ORDER[len(ROW_LABELS_IN_ORDER) - count + offset]
            numbered.append((row + shift + offset + 1, label))
        shift += count
    return numbered
```

`main()` の流れは今と同じ:
1. ワークシートを開き、A列と商品名列を読む
2. `plan_label_row_insertions` で対象を出し、件数と不足数を表示
3. `--dry-run` ならここで終了
4. `build_insert_requests` を1回の `spreadsheet.batch_update` で送る
5. `label_row_numbers` の行へラベルを `batch_update` で書く
6. 薄いグレー（`{red: 0.95, green: 0.95, blue: 0.95}`、A列〜商品名列）を `batch_format` で塗る

**予約行（1〜4行）には書かない。** `plan_label_row_insertions` は A列が10文字の行だけを対象にするので自然に守られるが、念のため確認すること。

- [ ] **Step 4: テストが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_insert_ad_rows.py -v`
Expected: PASS

- [ ] **Step 5: dry-run の出力を確認する**

Run: `.venv/bin/python insert_ad_rows.py --dry-run`
Expected: 対象が **77件、各2本不足**。見出し行が混ざっていないこと

**これは読み取りのみなので実行してよい。本実行はしないこと。**

- [ ] **Step 6: コミット**

```bash
git add insert_ad_rows.py py_tests/test_insert_ad_rows.py pyproject.toml
git commit -m "feat: 移行スクリプトを粗利益・広告費の行にも対応させる"
```

---

### Task 3: 広告レポートに広告費を足す

**Files:**
- Modify: `py_src/infrastructure/api/ads_units_repository.py`
- Test: `py_tests/test_ads_units_repository.py`

**Interfaces:**
- Produces: `AdsUnitsRepository.get_daily_metrics(start: date, end: date) -> dict[str, dict[str, AdMetrics]]`
- Produces: `AdMetrics`（frozen dataclass、`units: int` と `cost: float`）を `py_src/domain/value_objects/ad_metrics.py` に置く

既存の `get_daily_units` は個数だけを返す。同じ1リクエストで `cost` も取れるので、戻り値を広げる。

**`get_daily_units` は残さず `get_daily_metrics` に置き換える。** 呼び出し元は `UpdateAdSalesUseCase` だけなので、Task 4 で合わせて直す。

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_ads_units_repository.py` に追記（既存テストは `get_daily_units` を呼んでいるので、**すべて `get_daily_metrics` へ書き換える**。アサーションの中身は下記のとおり `AdMetrics` を見る形に変える）:

```python
    def test_returns_units_and_cost_by_date_and_asin(self) -> None:
        rows = [
            {"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D",
             "unitsSoldSameSku14d": 3, "cost": 120.5},
            {"date": "2026-09-01", "advertisedAsin": "B0GQPRJNPF",
             "unitsSoldSameSku14d": 0, "cost": 40.0},
        ]
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.side_effect = [
            _response(payload={"status": "COMPLETED", "url": "https://example.com/r.gz"}),
            _response(content=_gzipped(rows)),
        ]
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        metrics = repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 1))

        assert metrics["2026-09-01"]["B0HH5DR13D"] == AdMetrics(units=3, cost=120.5)
        assert metrics["2026-09-01"]["B0GQPRJNPF"] == AdMetrics(units=0, cost=40.0)

    def test_same_asin_appearing_twice_sums_both_units_and_cost(self) -> None:
        rows = [
            {"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D",
             "unitsSoldSameSku14d": 2, "cost": 100.0},
            {"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D",
             "unitsSoldSameSku14d": 1, "cost": 50.5},
        ]
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.side_effect = [
            _response(payload={"status": "COMPLETED", "url": "https://example.com/r.gz"}),
            _response(content=_gzipped(rows)),
        ]
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        metrics = repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 1))

        assert metrics["2026-09-01"]["B0HH5DR13D"] == AdMetrics(units=3, cost=150.5)

    def test_cost_column_is_requested(self) -> None:
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.side_effect = [
            _response(payload={"status": "COMPLETED", "url": "https://example.com/r.gz"}),
            _response(content=_gzipped([])),
        ]
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        repository.get_daily_metrics(date(2026, 9, 1), date(2026, 9, 1))

        body = session.post.call_args.kwargs["json"]
        assert "cost" in body["configuration"]["columns"]
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_ads_units_repository.py -v`
Expected: FAIL

- [ ] **Step 3: 実装する**

`py_src/domain/value_objects/ad_metrics.py`:

```python
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class AdMetrics:
    units: int = 0
    cost: float = 0.0
```

`ads_units_repository.py`:
- `COST_COLUMN = "cost"` を足し、`COLUMNS = ["date", "advertisedAsin", UNITS_COLUMN, COST_COLUMN]`
- `get_daily_units` を `get_daily_metrics` に改名し、戻り値を `dict[str, dict[str, AdMetrics]]` にする
- `_group_by_date` は同じ ASIN が複数回現れたら **units と cost の両方を合算**する

**「レポートに現れない ASIN のキーを作らない」方針は変えない。**

- [ ] **Step 4: テストが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_ads_units_repository.py -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add py_src/domain/value_objects/ad_metrics.py py_src/infrastructure/api/ads_units_repository.py py_tests/test_ads_units_repository.py pyproject.toml
git commit -m "feat(ads): 広告レポートから広告費も取得する"
```

---

### Task 4: 広告費を広告費の行へ書く

**Files:**
- Modify: `py_src/infrastructure/sheets/ad_sales_sheet.py`
- Modify: `py_src/usecases/update_ad_sales.py`
- Modify: `main.py`
- Test: `py_tests/test_ad_sales_sheet.py`, `py_tests/test_update_ad_sales.py`

**Interfaces:**
- Consumes: `AdMetrics`（Task 3）、`bind_label_rows` / `AD_COST_ROW_LABEL`（Task 1）
- Produces: `AdSalesSheet.write_ad_metrics(metrics_by_date: dict[str, dict[str, AdMetrics]]) -> AdWriteResult`

`write_ad_units` を `write_ad_metrics` に置き換える。広告経由の行に `units`、広告費の行に `cost` を書く。**同じ `batch_update` にまとめる。**

**0 埋めの方針は広告経由と同じく広告費にも適用する** — レポートに現れなかった ASIN の広告費は 0（その日は広告を出していない＝費用0が正しい）。

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_ad_sales_sheet.py` に追記。フィクスチャは行1〜4が予約、行5以降が「ASIN → 広告経由 → 粗利益 → 広告費」の繰り返しになるよう作り直す:

```python
    def test_writes_units_and_cost_to_their_own_rows(self) -> None:
        worksheet = _make_worksheet()
        sheet = AdSalesSheet(worksheet=worksheet)
        sheet.get_ad_rows()

        sheet.write_ad_metrics({"2026-09-01": {"B00EXAMPLE": AdMetrics(units=3, cost=120.0)}})

        requests = worksheet.batch_update.call_args[0][0]
        by_range = {r["range"]: r["values"] for r in requests}
        assert by_range[rowcol_to_a1(6, 3)] == [[3]]      # 広告経由の行
        assert by_range[rowcol_to_a1(8, 3)] == [[120.0]]  # 広告費の行

    def test_writes_zero_cost_for_asins_absent_from_the_report(self) -> None:
        worksheet = _make_worksheet()
        sheet = AdSalesSheet(worksheet=worksheet)
        sheet.get_ad_rows()

        sheet.write_ad_metrics({"2026-09-01": {}})

        requests = worksheet.batch_update.call_args[0][0]
        assert all(r["values"] in ([[0]], [[0.0]]) for r in requests)

    def test_units_and_cost_go_in_one_batch(self) -> None:
        worksheet = _make_worksheet()
        sheet = AdSalesSheet(worksheet=worksheet)
        sheet.get_ad_rows()

        sheet.write_ad_metrics({"2026-09-01": {"B00EXAMPLE": AdMetrics(units=1, cost=10.0)}})

        assert worksheet.batch_update.call_count == 1
```

`py_tests/test_update_ad_sales.py` は `get_daily_units` / `write_ad_units` を `get_daily_metrics` / `write_ad_metrics` に置き換え、返す値を `AdMetrics` にする。**アサーションが確かめている内容は変えない。**

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_ad_sales_sheet.py py_tests/test_update_ad_sales.py -v`
Expected: FAIL

- [ ] **Step 3: 実装する**

- `AdSalesSheet` に `self._ad_cost_rows` を持たせ、`get_ad_rows` で `bind_label_rows(..., AD_COST_ROW_LABEL)` も解決する
- `write_ad_metrics` は広告経由の行と広告費の行の両方へ書き、1回の `batch_update` にまとめる
- `UpdateAdSalesUseCase` は `get_daily_metrics` を呼び、`write_ad_metrics` へ渡す。空レポートのガードと日付の穴埋めは**そのまま**
- `main.py` の `update_ad_sales()` の print は変えない（`AdWriteResult` の内容は同じ）

- [ ] **Step 4: 全スイートが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/ -v`
Expected: 全 PASS

- [ ] **Step 5: コミット**

```bash
git add py_src/infrastructure/sheets/ad_sales_sheet.py py_src/usecases/update_ad_sales.py main.py py_tests/test_ad_sales_sheet.py py_tests/test_update_ad_sales.py pyproject.toml
git commit -m "feat(ads): 広告費を広告費の行へ書く"
```

---

### Task 5: シートの移行を実行する（controller）

**Files:** なし（実行のみ）

**このタスクは controller が実行する。** 実装エージェントは担当しない。

- [ ] **Step 1: dry-run で対象を確認**

Run: `.venv/bin/python insert_ad_rows.py --dry-run`
Expected: 77件

- [ ] **Step 2: ユーザーに確認して本実行**

77 ASIN × 2行 = **154行**をシートに挿入する。行数は約166行 → 約320行。

- [ ] **Step 3: 結果を確認**

- 各 ASIN が「ASIN → 広告経由 → 粗利益 → 広告費」の4行になっている
- **既存の売上個数と広告経由の値が変わっていない**（代表ASINを1件、日付列の値で突き合わせる）
- 見出し行の直下に新しい行が入っていない
- 再実行の dry-run が0件

- [ ] **Step 4: 広告ジョブを実データで通す**

Run: `.venv/bin/python main.py ads`
Expected: 広告経由と広告費の両方にセルが入る。**広告費が広告経由より大きい日がある**のは正常（費用と成果は別物）

---

### Task 6: 粗利益（見積）を計算して書く

**Files:**
- Create: `py_src/infrastructure/sheets/unit_cost_reader.py`
- Create: `py_src/domain/value_objects/unit_costs.py`
- Modify: `py_src/infrastructure/sheets/sales_sheet.py`
- Test: `py_tests/test_unit_cost_reader.py`, `py_tests/test_gross_profit.py`

**Interfaces:**
- Produces: `UnitCosts`（frozen dataclass、`selling_fee: float | None` / `fba_fee: float | None` / `cost: float | None`）
- Produces: `UnitCostReader(worksheet).read() -> dict[str, UnitCosts]`（ASIN → 1個あたりの各費用）
- Produces: `estimate_gross_profit(sales: SalesInfo, costs: UnitCosts) -> float | None`（`py_src/domain/value_objects/unit_costs.py` に置く）
- Produces: `SalesSheet.write_gross_profit(profit_by_asin: dict[str, float], target_date: date) -> int`

計算は `実売上 − (販売手数料 + FBA手数料 + 原価) × 個数`。**3つのうち1つでも空なら `None` を返し、セルを空にする。**

シートの列名は「販売手数料」「FBA手数料」「原価」。

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_gross_profit.py`:

```python
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.domain.value_objects.unit_costs import UnitCosts, estimate_gross_profit


class TestEstimateGrossProfit:
    def test_subtracts_per_unit_costs_from_actual_sales(self) -> None:
        sales = SalesInfo(unit_count=3, total_sales_amount=3000.0)
        costs = UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=200.0)

        # 3000 - (100 + 300 + 200) * 3 = 1200
        assert estimate_gross_profit(sales, costs) == 1200.0

    def test_uses_actual_sales_not_units_times_price(self) -> None:
        # セール等で実売上が単価×個数と一致しなくても、実売上をそのまま使う
        sales = SalesInfo(unit_count=2, total_sales_amount=1500.0)
        costs = UnitCosts(selling_fee=50.0, fba_fee=100.0, cost=100.0)

        assert estimate_gross_profit(sales, costs) == 1000.0

    def test_returns_none_when_any_cost_is_missing(self) -> None:
        sales = SalesInfo(unit_count=1, total_sales_amount=1000.0)

        assert estimate_gross_profit(sales, UnitCosts(None, 300.0, 200.0)) is None
        assert estimate_gross_profit(sales, UnitCosts(100.0, None, 200.0)) is None
        assert estimate_gross_profit(sales, UnitCosts(100.0, 300.0, None)) is None

    def test_zero_units_gives_zero_profit(self) -> None:
        sales = SalesInfo(unit_count=0, total_sales_amount=0.0)
        costs = UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=200.0)

        assert estimate_gross_profit(sales, costs) == 0.0

    def test_can_be_negative(self) -> None:
        sales = SalesInfo(unit_count=1, total_sales_amount=500.0)
        costs = UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=200.0)

        assert estimate_gross_profit(sales, costs) == -100.0
```

`py_tests/test_unit_cost_reader.py`:

```python
from unittest.mock import Mock

from py_src.domain.value_objects.unit_costs import UnitCosts
from py_src.infrastructure.sheets.unit_cost_reader import UnitCostReader


def _worksheet() -> Mock:
    worksheet = Mock()
    worksheet.row_values.return_value = ["ASIN", "商品名", "販売手数料", "FBA手数料", "原価"]
    worksheet.get.return_value = [
        ["ASIN", "商品名", "販売手数料", "FBA手数料", "原価"],
        ["B00EXAMPLE", "ルーペ", "100", "300", "200"],
        ["", "広告経由", "", "", ""],
        ["B00EXAMPLF", "ボール", "", "250", "180"],
    ]
    return worksheet


class TestUnitCostReader:
    def test_reads_per_unit_costs_by_asin(self) -> None:
        costs = UnitCostReader(_worksheet()).read()

        assert costs["B00EXAMPLE"] == UnitCosts(
            selling_fee=100.0, fba_fee=300.0, cost=200.0
        )

    def test_missing_value_becomes_none(self) -> None:
        costs = UnitCostReader(_worksheet()).read()

        assert costs["B00EXAMPLF"].selling_fee is None
        assert costs["B00EXAMPLF"].fba_fee == 250.0

    def test_ignores_non_asin_rows(self) -> None:
        costs = UnitCostReader(_worksheet()).read()

        assert set(costs) == {"B00EXAMPLE", "B00EXAMPLF"}

    def test_strips_currency_formatting(self) -> None:
        worksheet = _worksheet()
        worksheet.get.return_value = [
            ["ASIN", "商品名", "販売手数料", "FBA手数料", "原価"],
            ["B00EXAMPLE", "ルーペ", "¥1,100", "300", "200"],
        ]

        assert UnitCostReader(worksheet).read()["B00EXAMPLE"].selling_fee == 1100.0
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_gross_profit.py py_tests/test_unit_cost_reader.py -v`
Expected: FAIL

- [ ] **Step 3: 実装する**

`py_src/domain/value_objects/unit_costs.py`:

```python
from __future__ import annotations
from dataclasses import dataclass

from py_src.domain.value_objects.sales_info import SalesInfo


@dataclass(frozen=True)
class UnitCosts:
    selling_fee: float | None = None
    fba_fee: float | None = None
    cost: float | None = None

    @property
    def total_per_unit(self) -> float | None:
        parts = (self.selling_fee, self.fba_fee, self.cost)
        if any(part is None for part in parts):
            return None
        return sum(parts)


def estimate_gross_profit(sales: SalesInfo, costs: UnitCosts) -> float | None:
    per_unit = costs.total_per_unit
    if per_unit is None:
        return None
    return sales.total_sales_amount - per_unit * sales.unit_count
```

`UnitCostReader` はヘッダー行から「販売手数料」「FBA手数料」「原価」の列を引き、A列が10文字の行だけを対象に読む。`¥` とカンマを落として float にし、空文字は `None`。

`SalesSheet.write_gross_profit(profit_by_asin, target_date)` は:
- `bind_label_rows(..., GROSS_PROFIT_ROW_LABEL)` で粗利益の行を解決
- 対象日の列を `read_date_columns` から引く。無ければ何もせず 0 を返す
- **値が `None` の ASIN はセルに触らない**（空のまま）
- 書いたセルに**薄い黄色**（`{red: 1.0, green: 0.95, blue: 0.8}`）を付ける
- 予約行ガード（`row > HEADER_ROW`）を通す

- [ ] **Step 4: テストが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/ -v`
Expected: 全 PASS

- [ ] **Step 5: コミット**

```bash
git add py_src/domain/value_objects/unit_costs.py py_src/infrastructure/sheets/unit_cost_reader.py py_src/infrastructure/sheets/sales_sheet.py py_tests/test_gross_profit.py py_tests/test_unit_cost_reader.py pyproject.toml
git commit -m "feat: 粗利益（見積）の計算と書き込みを追加"
```

---

### Task 7: 売上ジョブから粗利益（見積）を書く

**Files:**
- Modify: `py_src/usecases/update_today_sales.py`
- Modify: `py_src/usecases/update_daily_sales.py`
- Modify: `main.py`
- Test: `py_tests/test_update_today_sales.py`, `py_tests/test_update_daily_sales.py`

**Interfaces:**
- Consumes: `UnitCostReader`（Task 6）、`estimate_gross_profit`（Task 6）、`SalesSheet.write_gross_profit`（Task 6）

売上個数を書いた直後に、同じ ASIN の実売上と個数から粗利益（見積）を計算して書く。**API 呼び出しは増えない。**

- [ ] **Step 1: 失敗するテストを書く**

```python
    def test_writes_estimated_gross_profit_after_units(self) -> None:
        sales_sheet = Mock()
        sales_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        cost_reader = Mock()
        cost_reader.read.return_value = {
            "B00EXAMPLE": UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=200.0)
        }
        sales_repository = Mock()
        sales_repository.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=3, total_sales_amount=3000.0)
        }
        usecase = UpdateTodaySalesUseCase(
            sales_sheet=sales_sheet,
            sales_repository=sales_repository,
            cost_reader=cost_reader,
        )

        usecase.execute()

        written = sales_sheet.write_gross_profit.call_args[0][0]
        assert written == {"B00EXAMPLE": 1200.0}

    def test_asin_with_missing_costs_is_absent_from_the_write(self) -> None:
        sales_sheet = Mock()
        sales_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        cost_reader = Mock()
        cost_reader.read.return_value = {"B00EXAMPLE": UnitCosts(None, 300.0, 200.0)}
        sales_repository = Mock()
        sales_repository.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=3, total_sales_amount=3000.0)
        }
        usecase = UpdateTodaySalesUseCase(
            sales_sheet=sales_sheet,
            sales_repository=sales_repository,
            cost_reader=cost_reader,
        )

        usecase.execute()

        assert sales_sheet.write_gross_profit.call_args[0][0] == {}

    def test_units_are_written_before_profit(self) -> None:
        # 粗利益は売上個数と同じ列に書くので、列を解決する write_sales_nums が先
        sales_sheet = Mock()
        sales_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        cost_reader = Mock()
        cost_reader.read.return_value = {
            "B00EXAMPLE": UnitCosts(selling_fee=1.0, fba_fee=1.0, cost=1.0)
        }
        sales_repository = Mock()
        sales_repository.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=1, total_sales_amount=10.0)
        }
        calls: list[str] = []
        sales_sheet.write_sales_nums.side_effect = lambda *a, **k: calls.append("units")
        sales_sheet.write_gross_profit.side_effect = lambda *a, **k: calls.append("profit")
        usecase = UpdateTodaySalesUseCase(
            sales_sheet=sales_sheet,
            sales_repository=sales_repository,
            cost_reader=cost_reader,
        )

        usecase.execute()

        assert calls == ["units", "profit"]
```

同じ趣旨のテストを `test_update_daily_sales.py` にも足す。

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_update_today_sales.py py_tests/test_update_daily_sales.py -v`
Expected: FAIL

- [ ] **Step 3: 実装する**

両ユースケースのコンストラクタに `cost_reader` を足し、`execute` の中で:

```python
        self._sheet.write_sales_nums(asin_sales, target_date=target_date)
        costs = self._cost_reader.read()
        profits = {
            asin: profit
            for asin, sales in asin_sales.items()
            if (profit := estimate_gross_profit(sales, costs.get(asin, UnitCosts()))) is not None
        }
        self._sheet.write_gross_profit(profits, target_date)
```

`main.py` の `update_today_sales()` と `update_daily_sales()` で `UnitCostReader(worksheet)` を組み立てて渡す。

**打ち切り（`SalesFetchDeadlineExceededError`）の経路では粗利益も部分結果に対して書く。** 総売上と同じく、部分であることが分かる状態を保つ。

- [ ] **Step 4: 全スイートが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/ -v`
Expected: 全 PASS

- [ ] **Step 5: コミット**

```bash
git add py_src/usecases/update_today_sales.py py_src/usecases/update_daily_sales.py main.py py_tests/test_update_today_sales.py py_tests/test_update_daily_sales.py pyproject.toml
git commit -m "feat: 売上ジョブから粗利益（見積）を書く"
```

---

### Task 8: 粗利益（見積）を実データで確認する（controller）

**Files:** なし（実行のみ）

**このタスクは controller が実行する。**

- [ ] **Step 1: 実行**

Run: `.venv/bin/python main.py today`

- [ ] **Step 2: 確認**

- 粗利益の行に数字が入り、**薄い黄色**になっている
- 手数料や原価が空の ASIN は**セルが空**（0 ではない）
- 代表 ASIN で手計算と一致する（`実売上 −（販売手数料+FBA手数料+原価）× 個数`）
- 売上個数・広告経由・広告費の行が壊れていない

---

### Task 9: Finances API の疎通確認

**Files:**
- Create: `tools/check_finances_api.py`

**このタスクの目的は「実装の前提が成り立つか」を実物で確かめること。** 広告のときに列名を確認した関門と同じ役割で、ここが通らないと Task 10 以降が成り立たない。

確かめること:

1. **`GET /finances/v0/financialEvents` が権限エラーにならないか**（この資格情報で叩けるか）
2. **レスポンスの形** — `FinancialEvents.ShipmentEventList[].ShipmentItemList[]` に `SellerSKU` と `ItemFeeList` があるか。`ItemFeeList[].FeeType` にどんな値が来るか（`Commission` / `FBAPerUnitFulfillmentFee` など）
3. **1日分の注文件数** — `GET /orders/v0/orders` を1日分叩いてページ数と件数を数える。14日分の実行時間の見積を出す
4. **SKU の欠損率** — 「売上/日」の SKU 列（`SKU`）のうち `#N/A` が何件あるか

- [ ] **Step 1: 確認スクリプトを書く**

`tools/check_finances_api.py`。`tools/check_ads_columns.py` と同じ形にする（`sys.path` を通し、`load_dotenv` に**絶対パスを渡す**。相対だとスクリプトの置き場所を起点に探して `.env` を見失う）。

出力してほしいもの:
- 財務イベントの取得可否と、取れた `ShipmentEvent` の件数
- `ItemFeeList` に現れた `FeeType` の種類と件数（**金額は伏せず出してよいが、注文IDは伏せる**）
- 1日分の注文件数とページ数
- SKU 列の総数・`#N/A` の件数・その ASIN の例（3件まで）

- [ ] **Step 2: 実行して結果を確かめる**

Run: `.venv/bin/python tools/check_finances_api.py`

**403 や権限エラーで落ちた場合は、そのまま報告して止まること。** 資格情報の問題は実装では直せない。

- [ ] **Step 3: spec に結果を反映**

`docs/superpowers/specs/2026-09-05-gross-profit-and-ad-cost-design.md` の「## リスクと未検証事項」を、確かめた事実に書き換える。特に:
- 使える `FeeType` の実際の値
- 注文件数の実測と、そこから見積もった14日分の実行時間
- SKU の `#N/A` の実数

- [ ] **Step 4: コミット**

```bash
git add tools/check_finances_api.py docs/superpowers/specs/2026-09-05-gross-profit-and-ad-cost-design.md pyproject.toml
git commit -m "chore: Finances API の疎通と注文件数を実物で確認し spec に反映"
```

---

### Task 10: 注文一覧と財務イベントのリポジトリ

**Files:**
- Modify: `py_src/domain/entities/order.py`
- Modify: `py_src/infrastructure/api/orders_repository.py`
- Create: `py_src/infrastructure/api/finances_repository.py`
- Test: `py_tests/test_orders_repository.py`, `py_tests/test_finances_repository.py`

**Interfaces:**
- Produces: `OrdersRepository.get_purchase_dates(created_after: str, created_before: str) -> dict[str, date]`（注文ID → 注文日）
- Produces: `FinancesRepository.get_item_fees(posted_after: str, posted_before: str) -> list[ItemFee]`
- Produces: `ItemFee`（frozen dataclass、`order_id: str` / `seller_sku: str` / `fee_amount: float`）を `py_src/domain/value_objects/item_fee.py` に置く

**`get_orders_with_items` は使わない。** `_build_order` が注文1件ごとに `getOrderItems` を呼び、3秒スリープを挟むため、1万件で8時間以上かかる。注文日だけが必要なので**一覧のエンドポイントだけを使う**。

`ItemFee.fee_amount` は**正の数**にする（API は手数料をマイナスで返すので、符号を反転して保持する）。呼び出し側が引き算しやすいため。

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_finances_repository.py`:

```python
from datetime import date
from unittest.mock import Mock

from py_src.domain.value_objects.item_fee import ItemFee
from py_src.infrastructure.api.finances_repository import FinancesRepository


def _events_page(events: list[dict], next_token: str | None = None) -> Mock:
    response = Mock()
    response.status_code = 200
    payload = {"FinancialEvents": {"ShipmentEventList": events}}
    if next_token:
        payload["NextToken"] = next_token
    response.json.return_value = {"payload": payload}
    return response


class TestFinancesRepository:
    def test_flattens_item_fees(self) -> None:
        auth = Mock()
        auth._session.get.return_value = _events_page([
            {
                "AmazonOrderId": "249-1",
                "ShipmentItemList": [
                    {
                        "SellerSKU": "SKU-A",
                        "ItemFeeList": [
                            {"FeeType": "Commission",
                             "FeeAmount": {"CurrencyAmount": -100.0}},
                            {"FeeType": "FBAPerUnitFulfillmentFee",
                             "FeeAmount": {"CurrencyAmount": -300.0}},
                        ],
                    }
                ],
            }
        ])
        repository = FinancesRepository(authenticator=auth, pause_seconds=0)

        fees = repository.get_item_fees("2026-09-01T00:00:00Z", "2026-09-02T00:00:00Z")

        assert fees == [
            ItemFee(order_id="249-1", seller_sku="SKU-A", fee_amount=400.0),
        ]

    def test_fees_are_positive_even_though_the_api_returns_negatives(self) -> None:
        auth = Mock()
        auth._session.get.return_value = _events_page([
            {
                "AmazonOrderId": "249-2",
                "ShipmentItemList": [
                    {"SellerSKU": "SKU-B",
                     "ItemFeeList": [{"FeeType": "Commission",
                                      "FeeAmount": {"CurrencyAmount": -55.5}}]},
                ],
            }
        ])
        repository = FinancesRepository(authenticator=auth, pause_seconds=0)

        assert repository.get_item_fees("a", "b")[0].fee_amount == 55.5

    def test_follows_next_token(self) -> None:
        auth = Mock()
        auth._session.get.side_effect = [
            _events_page([
                {"AmazonOrderId": "249-1", "ShipmentItemList": [
                    {"SellerSKU": "SKU-A", "ItemFeeList": [
                        {"FeeType": "Commission", "FeeAmount": {"CurrencyAmount": -10.0}}]}]}
            ], next_token="TOKEN"),
            _events_page([
                {"AmazonOrderId": "249-2", "ShipmentItemList": [
                    {"SellerSKU": "SKU-B", "ItemFeeList": [
                        {"FeeType": "Commission", "FeeAmount": {"CurrencyAmount": -20.0}}]}]}
            ]),
        ]
        repository = FinancesRepository(authenticator=auth, pause_seconds=0)

        fees = repository.get_item_fees("a", "b")

        assert [fee.order_id for fee in fees] == ["249-1", "249-2"]

    def test_event_without_fees_is_skipped(self) -> None:
        auth = Mock()
        auth._session.get.return_value = _events_page([
            {"AmazonOrderId": "249-3", "ShipmentItemList": [
                {"SellerSKU": "SKU-C", "ItemFeeList": []}]}
        ])
        repository = FinancesRepository(authenticator=auth, pause_seconds=0)

        assert repository.get_item_fees("a", "b") == []
```

`py_tests/test_orders_repository.py` に追記:

```python
    def test_get_purchase_dates_maps_order_id_to_date(self) -> None:
        auth = Mock()
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"payload": {"Orders": [
            {"AmazonOrderId": "249-1", "PurchaseDate": "2026-09-01T10:00:00Z"},
            {"AmazonOrderId": "249-2", "PurchaseDate": "2026-09-02T23:30:00Z"},
        ]}}
        auth._session.get.return_value = response
        repository = OrdersRepository(authenticator=auth)

        dates = repository.get_purchase_dates("2026-09-01T00:00:00Z", "2026-09-03T00:00:00Z")

        assert dates == {"249-1": date(2026, 9, 1), "249-2": date(2026, 9, 3)}
```

**注意: `PurchaseDate` は UTC。JST に直してから日付を取る**（`2026-09-02T23:30:00Z` は JST では 9/3）。上のテストはその変換を確かめている。

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_finances_repository.py py_tests/test_orders_repository.py -v`
Expected: FAIL

- [ ] **Step 3: 実装する**

- `ItemFee` を作る
- `FinancesRepository` は `GET {SP_API_BASE}/finances/v0/financialEvents?PostedAfter=...&PostedBefore=...` を叩き、`NextToken` を辿る。**タイムアウトは `SP_API_REQUEST_TIMEOUT_SECONDS`**。ページごとに `pause_seconds` 待つ（既定は既存に倣う）
- `OrdersRepository.get_purchase_dates` を足す。一覧のエンドポイントだけを使い、`NextToken` を辿る。`PurchaseDate` を JST に直して `date` にする
- **`get_orders_with_items` と `_build_order` は消さない**（テストが参照している）。使わないだけ

- [ ] **Step 4: テストが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/ -v`
Expected: 全 PASS

- [ ] **Step 5: コミット**

```bash
git add py_src/domain/value_objects/item_fee.py py_src/domain/entities/order.py py_src/infrastructure/api/finances_repository.py py_src/infrastructure/api/orders_repository.py py_tests/test_finances_repository.py py_tests/test_orders_repository.py pyproject.toml
git commit -m "feat: 注文日と実測手数料を取得するリポジトリ"
```

---

### Task 11: 実測で粗利益を上書きする

**Files:**
- Create: `py_src/usecases/update_actual_gross_profit.py`
- Create: `py_src/infrastructure/sheets/sku_reader.py`
- Modify: `py_src/infrastructure/sheets/sales_sheet.py`
- Modify: `main.py`
- Test: `py_tests/test_update_actual_gross_profit.py`, `py_tests/test_sku_reader.py`

**Interfaces:**
- Consumes: `OrdersRepository.get_purchase_dates`、`FinancesRepository.get_item_fees`、`UnitCostReader.read`（Task 6）
- Produces: `SkuReader(worksheet).read() -> dict[str, str]`（SellerSKU → ASIN）
- Produces: `UpdateActualGrossProfitUseCase(...).execute() -> int`（上書きしたセル数）
- Produces: `SalesSheet.write_actual_gross_profit(profit_by_date: dict[str, dict[str, float]]) -> int`

結合の流れ:

```
手数料(注文ID, SKU) → 注文ID で注文日 → SKU で ASIN → (注文日, ASIN) ごとに手数料を合算
粗利益(実測) = 実売上 − 合算した手数料 − 原価 × 個数
```

**実売上と個数はシートから読まず、SP-API から取り直す**（`get_daily_sales` を14日分）。シートの値は見積で上書きされている可能性があり、根拠として使えないため。

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_update_actual_gross_profit.py`:

```python
from datetime import date
from unittest.mock import Mock

from py_src.domain.value_objects.item_fee import ItemFee
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.domain.value_objects.unit_costs import UnitCosts
from py_src.usecases.update_actual_gross_profit import UpdateActualGrossProfitUseCase

WINDOW_END = date(2026, 9, 10)


def _usecase(
    purchase_dates: dict[str, date],
    fees: list[ItemFee],
    sku_to_asin: dict[str, str],
    costs: dict[str, UnitCosts],
    sales: dict[str, dict[str, SalesInfo]],
) -> tuple[UpdateActualGrossProfitUseCase, Mock]:
    orders = Mock()
    orders.get_purchase_dates.return_value = purchase_dates
    finances = Mock()
    finances.get_item_fees.return_value = fees
    sku_reader = Mock()
    sku_reader.read.return_value = sku_to_asin
    cost_reader = Mock()
    cost_reader.read.return_value = costs
    sales_repository = Mock()
    sales_repository.get_daily_sales.side_effect = lambda asin_list, start, end: sales.get(
        start[:10], {}
    )
    sheet = Mock()
    sheet.get_asin_list.return_value = list({a for day in sales.values() for a in day})
    sheet.write_actual_gross_profit.return_value = 0
    usecase = UpdateActualGrossProfitUseCase(
        sales_sheet=sheet,
        orders_repository=orders,
        finances_repository=finances,
        sku_reader=sku_reader,
        cost_reader=cost_reader,
        sales_repository=sales_repository,
        days=14,
        today=WINDOW_END,
    )
    return usecase, sheet


class TestUpdateActualGrossProfit:
    def test_attributes_fees_to_the_order_date_not_the_posted_date(self) -> None:
        # 9/1 に売れた商品の手数料が 9/3 に決済されても、粗利益は 9/1 の列に入る
        usecase, sheet = _usecase(
            purchase_dates={"249-1": date(2026, 9, 1)},
            fees=[ItemFee(order_id="249-1", seller_sku="SKU-A", fee_amount=400.0)],
            sku_to_asin={"SKU-A": "B00EXAMPLE"},
            costs={"B00EXAMPLE": UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=200.0)},
            sales={"2026-09-01": {"B00EXAMPLE": SalesInfo(unit_count=1,
                                                          total_sales_amount=1000.0)}},
        )

        usecase.execute()

        written = sheet.write_actual_gross_profit.call_args[0][0]
        assert "2026-09-01" in written
        assert "2026-09-03" not in written
        # 1000 - 400(実測手数料) - 200(原価) * 1 = 400
        assert written["2026-09-01"]["B00EXAMPLE"] == 400.0

    def test_skips_asins_whose_sku_cannot_be_resolved(self) -> None:
        # SKU 列が #N/A の商品は SkuReader が返さない。実測の対象外で、見積のまま残す
        usecase, sheet = _usecase(
            purchase_dates={"249-1": date(2026, 9, 1)},
            fees=[ItemFee(order_id="249-1", seller_sku="SKU-UNKNOWN", fee_amount=400.0)],
            sku_to_asin={},
            costs={"B00EXAMPLE": UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=200.0)},
            sales={"2026-09-01": {"B00EXAMPLE": SalesInfo(unit_count=1,
                                                          total_sales_amount=1000.0)}},
        )

        usecase.execute()

        assert sheet.write_actual_gross_profit.call_args[0][0] == {}

    def test_fees_for_the_same_asin_and_date_are_summed(self) -> None:
        usecase, sheet = _usecase(
            purchase_dates={"249-1": date(2026, 9, 1), "249-2": date(2026, 9, 1)},
            fees=[
                ItemFee(order_id="249-1", seller_sku="SKU-A", fee_amount=400.0),
                ItemFee(order_id="249-2", seller_sku="SKU-A", fee_amount=150.0),
            ],
            sku_to_asin={"SKU-A": "B00EXAMPLE"},
            costs={"B00EXAMPLE": UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=200.0)},
            sales={"2026-09-01": {"B00EXAMPLE": SalesInfo(unit_count=2,
                                                          total_sales_amount=2000.0)}},
        )

        usecase.execute()

        written = sheet.write_actual_gross_profit.call_args[0][0]
        # 2000 - 550(手数料合計) - 200 * 2 = 1050
        assert written["2026-09-01"]["B00EXAMPLE"] == 1050.0

    def test_asin_with_missing_cost_is_skipped(self) -> None:
        # 原価が空なら実測でも粗利益を出さない（0 扱いにすると利益が過大に見える）
        usecase, sheet = _usecase(
            purchase_dates={"249-1": date(2026, 9, 1)},
            fees=[ItemFee(order_id="249-1", seller_sku="SKU-A", fee_amount=400.0)],
            sku_to_asin={"SKU-A": "B00EXAMPLE"},
            costs={"B00EXAMPLE": UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=None)},
            sales={"2026-09-01": {"B00EXAMPLE": SalesInfo(unit_count=1,
                                                          total_sales_amount=1000.0)}},
        )

        usecase.execute()

        assert sheet.write_actual_gross_profit.call_args[0][0] == {}

    def test_orders_outside_the_window_are_ignored(self) -> None:
        # 20日前の注文への返金が今になって決済されても、注文日が窓の外なので落とす
        usecase, sheet = _usecase(
            purchase_dates={"249-OLD": date(2026, 8, 20)},
            fees=[ItemFee(order_id="249-OLD", seller_sku="SKU-A", fee_amount=400.0)],
            sku_to_asin={"SKU-A": "B00EXAMPLE"},
            costs={"B00EXAMPLE": UnitCosts(selling_fee=100.0, fba_fee=300.0, cost=200.0)},
            sales={"2026-09-01": {"B00EXAMPLE": SalesInfo(unit_count=1,
                                                          total_sales_amount=1000.0)}},
        )

        usecase.execute()

        assert sheet.write_actual_gross_profit.call_args[0][0] == {}

    def test_finances_window_extends_past_the_order_window(self) -> None:
        # 決済は注文より後ろにずれるので、財務イベントは窓を広く取る
        usecase, _ = _usecase(
            purchase_dates={}, fees=[], sku_to_asin={}, costs={}, sales={},
        )

        usecase.execute()

        posted_after, posted_before = (
            usecase._finances_repository.get_item_fees.call_args[0]  # noqa: SLF001
        )
        created_after, created_before = (
            usecase._orders_repository.get_purchase_dates.call_args[0]  # noqa: SLF001
        )
        assert posted_before > created_before
```

`today` をコンストラクタで受け取るのは、テストで窓を固定するため。本番では `main.py` が渡さず、既定で JST の今日を使う。

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_update_actual_gross_profit.py -v`
Expected: FAIL

- [ ] **Step 3: 実装する**

- `SkuReader` は「SKU」列と A列を読み、`#N/A` や空を除いて `SKU → ASIN` を作る
- `UpdateActualGrossProfitUseCase.execute()`:
  1. 14日の範囲を決める（終端は昨日）
  2. `get_purchase_dates` と `get_item_fees` を取る。**Finances の窓は Orders より広く取る**（決済が後ろにずれるため。窓の後ろを7日足す）
  3. 注文日が14日の窓の中にあるものだけ残す
  4. SKU → ASIN、原価、実売上・個数を突き合わせ、`(日付, ASIN) → 粗利益` を作る
  5. `write_actual_gross_profit` へ渡す
- `SalesSheet.write_actual_gross_profit` は粗利益の行の該当セルを上書きし、**背景色を外す**（`_clear_backgrounds` と同じ `repeatCell` + `fields` の方式）。日付列が無い日はスキップ
- `main.py` に `update_actual_gross_profit()` と `finances` サブコマンドを足す
- **締切を付ける**（Task 9 の実測を見て値を決める）

- [ ] **Step 4: 全スイートが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/ -v`
Expected: 全 PASS

- [ ] **Step 5: コミット**

```bash
git add py_src/usecases/update_actual_gross_profit.py py_src/infrastructure/sheets/sku_reader.py py_src/infrastructure/sheets/sales_sheet.py main.py py_tests/test_update_actual_gross_profit.py py_tests/test_sku_reader.py pyproject.toml
git commit -m "feat: 実測手数料で粗利益を上書きする"
```

---

### Task 12: launchd ジョブと新商品の4行挿入

**Files:**
- Create: `/Users/wadaatsushi/Documents/automation/ops/launchd/com.automation.download-amazon-data-finances.plist`
- Modify: `/Users/wadaatsushi/Documents/automation/marketar/listing-creator/write_sales_sheet.py`

**このタスクだけ親リポジトリ（`/Users/wadaatsushi/Documents/automation`）を触る。**

plist は `com.automation.download-amazon-data-ads.plist` を雛形にし、`Label` と std path のファイル名、`ProgramArguments` の最後を `finances`、`StartCalendarInterval` を **3:00** にする。

**launchd の落とし穴（過去に2度、全ジョブを止めている）:**

| 対象 | `~/Documents` 配下でよいか |
|---|---|
| plist 本体（symlink も不可） | **不可** |
| `ProgramArguments[0]` | **不可** |
| `StandardOutPath` / `StandardErrorPath` | **不可** |
| `WorkingDirectory` | 可 |

`~` は展開されないので絶対パスで書く。正本は `ops/launchd/`。**配布（`sync_agents.py`）と起動（`launchctl`）は controller が行う。**

`write_sales_sheet.py` は現在2行挿入して2行目に「広告経由」を書く。**4行挿入**して2〜4行目に `広告経由` `粗利益` `広告費` を書くよう直す。数式のコピー元 `source_start_row=INSERT_ROW + 2` は **`INSERT_ROW + 4`** になる。

- [ ] **Step 1: plist を作る**
- [ ] **Step 2: `write_sales_sheet.py` を4行挿入に直す**
- [ ] **Step 3: `marketar/listing-creator` のテストを走らせる**

Run: `cd /Users/wadaatsushi/Documents/automation/marketar/listing-creator && .venv/bin/python -m pytest src/tests/ -v`
Expected: 変更前と同じかそれ以上に緑

- [ ] **Step 4: 親リポジトリでコミット（2つに分ける）**

```bash
cd /Users/wadaatsushi/Documents/automation
git add ops/launchd/com.automation.download-amazon-data-finances.plist
git diff --cached --name-only
git commit -m "feat(ops): 実測手数料で粗利益を上書きするジョブを毎日3:00に登録"

git add marketar/listing-creator/write_sales_sheet.py marketar/listing-creator/pyproject.toml
git diff --cached --name-only
git commit -m "feat(listing): 売上/日 の新規行を4行にする"
```

**親リポジトリには他プロジェクトの未コミット変更が多数ある。巻き込まないこと。**

---

### Task 13: 全体の受け入れ確認（controller）

**Files:**
- Modify: `data-engineer/download-amazon-data/CLAUDE.md`
- Modify: `/Users/wadaatsushi/Documents/automation/CLAUDE.md`

**このタスクは controller が実行する。**

- [ ] **Step 1: 配布と登録**

```bash
cd /Users/wadaatsushi/Documents/automation/ops && python3 sync_agents.py && python3 check_launchd.py
```

- [ ] **Step 2: 実測ジョブを走らせる**

Run: `.venv/bin/python main.py finances`

- [ ] **Step 3: 確認**

1. 実測で上書きされたセルの**塗りが外れている**
2. まだ実測が来ていないセルは**薄い黄色のまま**
3. SKU が `#N/A` の商品は見積のまま残っている
4. 実測の粗利益が、同じ列の売上・広告費と突き合わせて説明できる値
5. 見積と実測の差がどれくらいか（**代表10件で数字を出す**。差が大きすぎるなら計算のどこかが違う）

- [ ] **Step 4: launchd の翌日確認**

**登録した翌日に `runs` が増えていることを必ず確かめる。** 前回、定期実行を入れた直後の `runs` だけを見て「稼働中」と報告し、19時間半の停止に気づかなかった。

- [ ] **Step 5: ドキュメントを直す**

- `download-amazon-data/CLAUDE.md`: エントリポイントの表に `finances`、launchd スケジュールの表に3:00のジョブ、粗利益の節（見積と実測の区別、SKU が引けない商品は見積のまま）
- 親 `CLAUDE.md`: 「売上/日 は ASIN 1件につき2行」の記述を**4行**に直す

- [ ] **Step 6: コミット**
