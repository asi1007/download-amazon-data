# カテゴリ順位を売上/日のラベル行へ移す 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** カテゴリ順位を独立シートではなく「売上/日」の商品ブロック6本目のラベル行へ記録し、順位と売上・利益を1枚で読めるようにする。

**Architecture:** 売上/日 のラベル行を4本から5本へ増やす。順位行だけラベル名にカテゴリ名を埋めるため、ラベル判定を完全一致から「順位で始まる行」の前方一致へ拡張する。`category-rank` は行を挿入せず順位行を探して書くだけにし、ラベルの順序・本数の一致が要るのは従来どおり `download-amazon-data` と `listing-creator` の2箇所に留める。

**Tech Stack:** Python 3.10+, gspread, pytest, SP-API Catalog Items v2022-04-01

**Spec:** `data-engineer/download-amazon-data/docs/superpowers/specs/2026-09-09-category-rank-in-sales-sheet-design.md`

## Global Constraints

- 対象スプレッドシート: `1Z3P0iL19r3gA9-NG8x2e_42pGhrEs_wFMLWLbFvReAw`（売り上げ）。売上/日 の gid は `551300985`、旧カテゴリランキングシートの gid は `533865782`
- 売上/日 のヘッダー行は 4、ASIN は A列、日付列は「目標販売数」列の右隣以降で**最新が左**
- 列はヘッダー行の列名で引く。列インデックス固定は不可
- 書き込みは `batch_update` でまとめる（60req/min のクォータ）
- docstring は書かない。型ヒントは必須
- テストは pytest。`download-amazon-data` は `.venv/bin/python -m pytest py_tests`、`category-rank` と `listing-creator` は各リポジトリの `src/tests`
- コミットのたびに `pyproject.toml` の version を更新する（機能追加はマイナー、修正はパッチ）
- 3リポジトリはそれぞれ独立した git リポジトリ。`git -C <path>` を使うか各ディレクトリで実行する
- 欠測に 0 を書かない。取得できなかったセルは空のままにする

---

### Task 1: ラベル判定を前方一致へ拡張し「順位」を追加する

**Files:**
- Modify: `data-engineer/download-amazon-data/py_src/infrastructure/sheets/label_rows.py`
- Test: `data-engineer/download-amazon-data/py_tests/test_label_rows.py`

**Interfaces:**
- Consumes: なし
- Produces: `RANK_ROW_LABEL = "順位"`、`matches_label(name: str, label: str) -> bool`、`ROW_LABELS_IN_ORDER` が5要素になる

作業ディレクトリは `data-engineer/download-amazon-data`。

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_label_rows.py` に追記する（ファイルが無ければ作る。既存の import 行はそのまま使う）。

```python
from py_src.infrastructure.sheets.label_rows import (
    RANK_ROW_LABEL,
    ROW_LABELS_IN_ORDER,
    bind_label_rows,
    matches_label,
)


class TestRankLabelMatching:
    def test_rank_label_matches_with_category_in_parentheses(self) -> None:
        assert matches_label("順位（メガネストラップ）", RANK_ROW_LABEL) is True

    def test_rank_label_matches_when_category_is_unknown(self) -> None:
        assert matches_label("順位", RANK_ROW_LABEL) is True

    def test_rank_label_does_not_match_a_different_label(self) -> None:
        # 「順位表」のような別の行を誤って掴まない
        assert matches_label("順位表", RANK_ROW_LABEL) is False

    def test_other_labels_still_need_an_exact_match(self) -> None:
        assert matches_label("粗利益", "粗利益") is True
        assert matches_label("粗利益（見積）", "粗利益") is False

    def test_rank_row_is_last_in_the_order(self) -> None:
        # listing-creator の LABEL_ROWS_IN_ORDER と一致していなければならない
        assert ROW_LABELS_IN_ORDER == ("営業利益", "広告経由", "粗利益", "広告費", "順位")

    def test_bind_label_rows_finds_the_rank_row_by_prefix(self) -> None:
        asin_values = ["ASIN", "", "", "header", "B00EXAMPLE", "", "", "", "", ""]
        name_values = [
            "商品名", "", "", "header",
            "商品名です", "営業利益", "広告経由", "粗利益", "広告費", "順位（ジュエリー収納）",
        ]

        rows = bind_label_rows(asin_values, name_values, RANK_ROW_LABEL)

        assert rows == {"B00EXAMPLE": [10]}
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `.venv/bin/python -m pytest py_tests/test_label_rows.py -q`
Expected: FAIL（`ImportError: cannot import name 'RANK_ROW_LABEL'`）

- [ ] **Step 3: 実装する**

`label_rows.py` を書き換える。

```python
AD_ROW_LABEL = "広告経由"
OPERATING_PROFIT_ROW_LABEL = "営業利益"
GROSS_PROFIT_ROW_LABEL = "粗利益"
AD_COST_ROW_LABEL = "広告費"
# 順位行だけラベル名にカテゴリ名を埋める（順位（ジュエリー収納））。カテゴリ名を
# 別の列やノートに持つと、開かないと何のカテゴリか読めない
RANK_ROW_LABEL = "順位"
CATEGORY_OPEN = "（"

ROW_LABELS_IN_ORDER: tuple[str, ...] = (
    OPERATING_PROFIT_ROW_LABEL,
    AD_ROW_LABEL,
    GROSS_PROFIT_ROW_LABEL,
    AD_COST_ROW_LABEL,
    RANK_ROW_LABEL,
)
COLLAPSIBLE_ROW_LABELS: tuple[str, ...] = ROW_LABELS_IN_ORDER[1:]


def matches_label(name: str, label: str) -> bool:
    if label != RANK_ROW_LABEL:
        return name == label
    return name == label or name.startswith(f"{label}{CATEGORY_OPEN}")
```

`bind_label_rows` の判定を差し替える。

```python
        if matches_label(name, label) and current_asin:
            label_rows.setdefault(current_asin, []).append(row)
```

- [ ] **Step 4: 既存テストのヘルパーを6行ブロックに直す**

`py_tests/test_gradient_rules.py` の `_worksheet()` は `ROW_LABELS_IN_ORDER` を展開して
商品名列を作る一方、A列（`col_a`）は行番号を直書きしている。ラベルが5本になると
2商品目の ASIN 行がずれるので、次のように直す。

```python
# 行5 = B00EXAMPLE の売上個数、行7 = その広告経由。ラベル5本なので2商品目は行11、
# その広告経由は行13。日付列は2列なので、中央値は2つの値の平均になる
COUNT_VALUES: dict = {
    5: [10, 4],
    7: [4, 2],
    11: [20, 8],
    13: [6, 4],
}
FIRST_VALUE_ROW = 5
LAST_VALUE_ROW = 16
```

```python
    col_a = ["", "", "", "ASIN", "B00EXAMPLE"] + [""] * 5 + ["B00EXAMPLF"] + [""] * 5
```

これで商品1のブロックが行5〜10（順位行は行10）、商品2が行11〜16（順位行は行16）になる。
`test_count_rule_covers_the_asin_row_and_the_ad_row_together` など行番号を期待している
既存テストも、この構成に合わせて直す。

- [ ] **Step 5: テストが通ることを確認する**

Run: `.venv/bin/python -m pytest py_tests -q`
Expected: PASS

- [ ] **Step 6: コミットする**

```bash
git add py_src/infrastructure/sheets/label_rows.py py_tests/test_label_rows.py py_tests/test_gradient_rules.py pyproject.toml
git commit -m "feat(sheets): ラベル行に順位を追加し、順位だけ前方一致で引く"
```

---

### Task 2: 行挿入の計画が順位行を重複させないことを保証する

**Files:**
- Modify: `data-engineer/download-amazon-data/insert_label_rows.py`
- Test: `data-engineer/download-amazon-data/py_tests/test_insert_label_rows.py`

**Interfaces:**
- Consumes: Task 1 の `matches_label`
- Produces: なし（`plan_label_insertions` の振る舞いが変わるだけ）

`plan_label_insertions` は `name == label` で既存行と突き合わせている。カテゴリ名付きの順位行を「不一致」と見なすと、**毎回もう1本挿入して増殖する**。

- [ ] **Step 1: 失敗するテストを書く**

```python
from insert_label_rows import plan_label_insertions


def test_existing_rank_row_with_category_is_not_inserted_again() -> None:
    asin_values = ["B00EXAMPLE", "", "", "", "", ""]
    name_values = [
        "商品名です", "営業利益", "広告経由", "粗利益", "広告費", "順位（ジュエリー収納）",
    ]

    assert plan_label_insertions(asin_values, name_values) == []


def test_missing_rank_row_is_appended_after_the_ad_cost_row() -> None:
    asin_values = ["B00EXAMPLE", "", "", "", ""]
    name_values = ["商品名です", "営業利益", "広告経由", "粗利益", "広告費"]

    assert plan_label_insertions(asin_values, name_values) == [(6, ["順位"])]
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `.venv/bin/python -m pytest py_tests/test_insert_label_rows.py -q`
Expected: FAIL（1本目は `[(6, ['順位'])]` が返り、順位行が二重に入る）

- [ ] **Step 3: 実装する**

`insert_label_rows.py` の import に `matches_label` を足し、突き合わせを差し替える。

```python
from py_src.infrastructure.sheets.label_rows import (
    ASIN_COLUMN,
    ASIN_LENGTH,
    HEADER_ROW,
    PRODUCT_NAME_HEADER,
    ROW_LABELS_IN_ORDER,
    find_column,
    matches_label,
)
```

```python
        for label in ROW_LABELS_IN_ORDER:
            name = name_values[cursor].strip() if cursor < len(name_values) else ""
            if matches_label(name, label):
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `.venv/bin/python -m pytest py_tests -q`
Expected: PASS

- [ ] **Step 5: コミットする**

```bash
git add insert_label_rows.py py_tests/test_insert_label_rows.py pyproject.toml
git commit -m "fix(sheets): カテゴリ名付きの順位行を既存として認識する"
```

---

### Task 3: 順位行に反転グラデーションを掛ける

**Files:**
- Modify: `data-engineer/download-amazon-data/py_src/infrastructure/sheets/gradient_rules.py`
- Test: `data-engineer/download-amazon-data/py_tests/test_gradient_rules.py`

**Interfaces:**
- Consumes: Task 1 の `RANK_ROW_LABEL`
- Produces: なし

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_gradient_rules.py` に追記する。`_worksheet()` は既存のヘルパーで、商品2件（ASIN行が5行目と10行目）を返す。ラベルが5本になったので、そのヘルパーの `col_values` が返す商品名列に `順位` を足す必要がある。ヘルパーを直したうえで次を足す。

```python
def _rank_rules(worksheet: Mock) -> list[dict]:
    return [
        r for r in _rules(worksheet)
        if "gradientRule" in r
        and r["gradientRule"]["minpoint"].get("color") == PALE_BLUE
    ]


class TestRankGradient:
    def test_rank_is_blue_at_the_top_and_red_at_the_bottom(self) -> None:
        # 順位は小さいほど良い。個数（多いほど良い）と向きが逆になる
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        gradient = _rank_rules(worksheet)[0]["gradientRule"]
        assert gradient["minpoint"] == {"color": PALE_BLUE, "type": "MIN"}
        assert gradient["maxpoint"] == {"color": PALE_RED, "type": "MAX"}

    def test_rank_rule_is_separate_per_product(self) -> None:
        worksheet = _worksheet()
        GradientRules(worksheet).apply()

        rank_rules = _rank_rules(worksheet)
        assert [r["ranges"][0]["startRowIndex"] for r in rank_rules] == [9, 15]
        assert all(len(r["ranges"]) == 1 for r in rank_rules)
```

`startRowIndex` は0起点。Task 1 Step 4 でヘルパーを直したので、商品1のブロックは行5〜10
（順位行は行10 → `startRowIndex=9`）、商品2は行11〜16（順位行は行16 → `startRowIndex=15`）。

- [ ] **Step 2: テストが失敗することを確認する**

Run: `.venv/bin/python -m pytest py_tests/test_gradient_rules.py -q`
Expected: FAIL（`IndexError: list index out of range` — 順位のルールがまだ無い）

- [ ] **Step 3: 実装する**

`gradient_rules.py` の import に `RANK_ROW_LABEL` を足し、`_build_rules` のループ内へ順位行のルールを追加する。

```python
        rank_offset = ROW_LABELS_IN_ORDER.index(RANK_ROW_LABEL)
```

```python
                # 順位は小さいほど良い。MIN（最上位）を青、MAX（最下位）を赤にする。
                # 個数と同じうすい色にして、行の種類は位置で見分ける
                rules.append({
                    "ranges": [
                        _grid_range(sheet_id, first_label + rank_offset, first, last)
                    ],
                    "gradientRule": {
                        "minpoint": {"color": PALE_BLUE, "type": "MIN"},
                        "maxpoint": {"color": PALE_RED, "type": "MAX"},
                    },
                })
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `.venv/bin/python -m pytest py_tests -q`
Expected: PASS（`test_one_rule_per_product_for_the_count_rows` のルール総数の期待値を +2 する）

- [ ] **Step 5: コミットする**

```bash
git add py_src/infrastructure/sheets/gradient_rules.py py_tests/test_gradient_rules.py pyproject.toml
git commit -m "feat(sheets): 順位行に反転グラデーションを掛ける"
```

---

### Task 4: 既存74商品へ順位行を挿入し、書式を流し直す

**Files:**
- 変更なし（既存スクリプトの実行のみ）

**Interfaces:**
- Consumes: Task 1〜3
- Produces: 売上/日 の全商品ブロックが6行になる

これはシートを書き換える実行タスク。**コードのコミットは無い。**

- [ ] **Step 1: 挿入対象を確認する**

```bash
.venv/bin/python -u insert_label_rows.py --dry-run
```

Expected: 74商品それぞれに `順位` を1本挿入する計画が出る。挿入本数が74を大きく超える場合は Task 2 の突き合わせが効いていないので中止して調べる。

- [ ] **Step 2: 挿入する**

```bash
.venv/bin/python -u insert_label_rows.py
```

- [ ] **Step 3: 行グループ・行の高さ・グラデーションを流し直す**

```bash
.venv/bin/python -u apply_row_groups.py
.venv/bin/python -u apply_row_heights.py
.venv/bin/python -u apply_gradients.py
```

Expected: 行グループ 74件、条件付き書式は約225件

- [ ] **Step 4: 営業利益の数式を入れ直す**

行が増えて粗利益・広告費の行番号がずれるため、数式を必ず入れ直す。

```bash
.venv/bin/python -u backfill_operating_profit.py
```

- [ ] **Step 5: 目視で確認する**

売上/日 を開き、商品ブロックが6行になっていること、折りたたむと ASIN行と営業利益だけが見えること、営業利益の数式が正しい行を参照していることを確認する。

---

### Task 5: listing-creator のラベル定数を合わせる

**Files:**
- Modify: `marketar/listing-creator/src/usecases/sales_sheet_row.py:35`
- Test: `marketar/listing-creator/src/tests/usecases/test_sales_sheet_row.py`

**Interfaces:**
- Consumes: なし（別リポジトリなので import できない）
- Produces: 新商品が6行で挿入される

作業ディレクトリは `marketar/listing-creator`。

- [ ] **Step 1: 失敗するテストを書く**

`src/tests/usecases/test_sales_sheet_row.py` の順序を固定しているテストを直す。

```python
def test_label_rows_match_download_amazon_data() -> None:
    # data-engineer/download-amazon-data の label_rows.ROW_LABELS_IN_ORDER と
    # 一致していなければならない。別リポジトリなので import では保証できない
    assert LABEL_ROWS_IN_ORDER == ("営業利益", "広告経由", "粗利益", "広告費", "順位")


def test_first_row_below_label_rows_accounts_for_six_row_blocks() -> None:
    assert first_row_below_label_rows(7) == 13


def test_collapse_range_hides_everything_below_operating_profit() -> None:
    assert collapse_row_range(7) == (9, 12)
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `python3 -m pytest src/tests/usecases/test_sales_sheet_row.py -q`
Expected: FAIL（4本のままなので `first_row_below_label_rows(7) == 12`）

- [ ] **Step 3: 実装する**

```python
LABEL_ROWS_IN_ORDER = ("営業利益", "広告経由", "粗利益", "広告費", "順位")
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `python3 -m pytest src/tests -q`
Expected: PASS

- [ ] **Step 5: コミットする**

```bash
git add src/usecases/sales_sheet_row.py src/tests/usecases/test_sales_sheet_row.py pyproject.toml
git commit -m "feat(listing): 新商品の売上/日 行に順位行を足す"
```

---

### Task 6: category-rank に売上/日 の順位行を読み書きする層を作る

**Files:**
- Create: `marketar/category-rank/src/infrastructure/sales_sheet.py`
- Test: `marketar/category-rank/src/tests/infrastructure/test_sales_sheet.py`

**Interfaces:**
- Consumes: なし（別リポジトリなので `label_rows` は import できない。同じ規約を再実装する）
- Produces:
  - `RANK_ROW_LABEL = "順位"`
  - `rank_label(category: str) -> str` — `順位（ジュエリー収納）` を作る。カテゴリが空なら `順位`
  - `category_of(label: str) -> str` — ラベル名からカテゴリ名を取り出す。無ければ `""`
  - `find_rank_rows(asin_values: list[str], name_values: list[str]) -> dict[str, int]`
  - `find_date_columns(header: list[object]) -> dict[int, int]` — シリアル → 1起点の列番号
  - `date_serial(day: date) -> int`
  - `column_of(header: list[object], name: str) -> int` — ヘッダー名から1起点の列番号
  - `column_letter(column: int) -> str` — 1起点の列番号から A1 表記の列文字

作業ディレクトリは `marketar/category-rank`。

- [ ] **Step 1: 失敗するテストを書く**

```python
from datetime import date

import pytest

from src.infrastructure.sales_sheet import (
    category_of,
    column_letter,
    column_of,
    date_serial,
    find_date_columns,
    find_rank_rows,
    rank_label,
)


class TestRankLabel:
    def test_builds_a_label_with_the_category(self) -> None:
        assert rank_label("ジュエリー収納") == "順位（ジュエリー収納）"

    def test_builds_a_bare_label_when_the_category_is_unknown(self) -> None:
        assert rank_label("") == "順位"

    def test_reads_the_category_back(self) -> None:
        assert category_of("順位（ジュエリー収納）") == "ジュエリー収納"

    def test_returns_empty_when_the_label_has_no_category(self) -> None:
        assert category_of("順位") == ""


class TestFindRankRows:
    def test_binds_the_rank_row_to_the_asin_above_it(self) -> None:
        asin_values = ["ASIN", "", "", "header", "B00EXAMPLE", "", "", "", "", ""]
        name_values = [
            "商品名", "", "", "header",
            "商品名です", "営業利益", "広告経由", "粗利益", "広告費", "順位（収納）",
        ]

        assert find_rank_rows(asin_values, name_values) == {"B00EXAMPLE": 10}

    def test_ignores_a_rank_row_without_an_asin_above_it(self) -> None:
        asin_values = ["ASIN", "", "", "header", "", ""]
        name_values = ["商品名", "", "", "header", "", "順位"]

        assert find_rank_rows(asin_values, name_values) == {}


class TestFindDateColumns:
    def test_maps_serials_to_one_based_columns(self) -> None:
        header = ["ASIN", "目標販売数", 46274, 46273]

        assert find_date_columns(header) == {46274: 3, 46273: 4}

    def test_ignores_non_serial_cells(self) -> None:
        header = ["ASIN", "目標販売数", "07", True, 46273]

        assert find_date_columns(header) == {46273: 5}

    def test_keeps_the_leftmost_column_for_a_duplicated_date(self) -> None:
        header = ["ASIN", "目標販売数", 46274, 46274]

        assert find_date_columns(header) == {46274: 3}


def test_date_serial_matches_the_sheets_epoch() -> None:
    assert date_serial(date(2026, 6, 19)) == 46192


class TestColumnHelpers:
    def test_finds_a_column_by_header_name(self) -> None:
        assert column_of(["ASIN", "商品名", "目標販売数"], "商品名") == 2

    def test_ignores_line_breaks_in_the_header(self) -> None:
        assert column_of(["ASIN", "ライバル\nURL"], "ライバルURL") == 2

    def test_raises_when_the_header_is_missing(self) -> None:
        with pytest.raises(ValueError):
            column_of(["ASIN"], "商品名")

    def test_converts_a_column_number_into_letters(self) -> None:
        assert column_letter(1) == "A"
        assert column_letter(26) == "Z"
        assert column_letter(27) == "AA"
        assert column_letter(96) == "CR"
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `python3 -m pytest src/tests/infrastructure/test_sales_sheet.py -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'src.infrastructure.sales_sheet'`）

- [ ] **Step 3: 実装する**

`src/infrastructure/sales_sheet.py` を作る。

```python
from __future__ import annotations

from datetime import date

from src.domain.entities.category_rank import ASIN_PATTERN

HEADER_ROW = 4
ASIN_COLUMN = 1
PRODUCT_NAME_HEADER = "商品名"
RANK_ROW_LABEL = "順位"
CATEGORY_OPEN = "（"
CATEGORY_CLOSE = "）"
SHEETS_EPOCH = date(1899, 12, 30)
SERIAL_MIN = 40000
SERIAL_MAX = 60000


def rank_label(category: str) -> str:
    if not category:
        return RANK_ROW_LABEL
    return f"{RANK_ROW_LABEL}{CATEGORY_OPEN}{category}{CATEGORY_CLOSE}"


def category_of(label: str) -> str:
    stripped = label.strip()
    if not stripped.startswith(f"{RANK_ROW_LABEL}{CATEGORY_OPEN}"):
        return ""
    return stripped[len(RANK_ROW_LABEL) + 1:].removesuffix(CATEGORY_CLOSE)


def is_rank_label(label: str) -> bool:
    stripped = label.strip()
    return stripped == RANK_ROW_LABEL or stripped.startswith(
        f"{RANK_ROW_LABEL}{CATEGORY_OPEN}"
    )


def find_rank_rows(asin_values: list[str], name_values: list[str]) -> dict[str, int]:
    # ラベル行は「A列が空 かつ 商品名列がラベル かつ 直前に ASIN 行がある」で決まる。
    # 位置だけで決めると、ラベルを並べ替えたときに別の行を掴む
    rows: dict[str, int] = {}
    current_asin = ""
    for index in range(max(len(asin_values), len(name_values))):
        row = index + 1
        asin = asin_values[index].strip() if index < len(asin_values) else ""
        name = name_values[index].strip() if index < len(name_values) else ""
        if ASIN_PATTERN.match(asin):
            current_asin = asin
            continue
        if asin:
            current_asin = ""
            continue
        if current_asin and is_rank_label(name):
            rows[current_asin] = row
    return rows


def find_date_columns(header: list[object]) -> dict[int, int]:
    # 同じ日付が2列にあるときは最も左を採る。bool は int の派生なので除く
    columns: dict[int, int] = {}
    for index, value in enumerate(header, start=1):
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if SERIAL_MIN < value < SERIAL_MAX:
            columns.setdefault(value, index)
    return columns


def date_serial(day: date) -> int:
    return (day - SHEETS_EPOCH).days


def column_of(header: list[object], name: str) -> int:
    # 売上/日 のヘッダーは改行入り（'ライバル\nURL'）があるので素朴な完全一致では落ちる
    target = name.replace("\n", "").strip().casefold()
    for index, value in enumerate(header, start=1):
        if str(value).replace("\n", "").strip().casefold() == target:
            return index
    raise ValueError(f"ヘッダーに '{name}' が見つかりません")


def column_letter(column: int) -> str:
    letters = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `python3 -m pytest src/tests -q`
Expected: PASS

- [ ] **Step 5: コミットする**

```bash
git add src/infrastructure/sales_sheet.py src/tests/infrastructure/test_sales_sheet.py pyproject.toml
git commit -m "feat: 売上/日 の順位行と日付列を引く層を足す"
```

---

### Task 7: 順位を売上/日 へ書く usecase を作る

**Files:**
- Create: `marketar/category-rank/src/usecases/write_ranks_to_sales_sheet.py`
- Test: `marketar/category-rank/src/tests/usecases/test_write_ranks_to_sales_sheet.py`

**Interfaces:**
- Consumes: Task 6 の `find_rank_rows` / `find_date_columns` / `date_serial` / `rank_label`、`src.domain.entities.category_rank.CategoryRank`
- Produces:
  - `@dataclass(frozen=True) class RankWriteResult: cells_written: int; label_updates: int; skipped_date: bool; missing_rows: list[str]`
  - `build_rank_updates(asin_values, name_values, header, ranks, day) -> tuple[list[dict], RankWriteResult]` — gspread の `batch_update` に渡す `{"range": ..., "values": ...}` の並びを返す

範囲は A1 表記で作る。列番号から列文字への変換もこのモジュールに置く。

- [ ] **Step 1: 失敗するテストを書く**

```python
from datetime import date

from src.domain.entities.category_rank import CategoryRank
from src.usecases.write_ranks_to_sales_sheet import build_rank_updates

ASIN_VALUES = ["ASIN", "", "", "header", "B0EXAMPLE1", "", "", "", "", ""]
NAME_VALUES = [
    "商品名", "", "", "header",
    "商品名です", "営業利益", "広告経由", "粗利益", "広告費", "順位",
]
HEADER = ["ASIN", "商品名", "目標販売数", 46274, 46273]
DAY = date(2026, 9, 9)  # serial 46274


def test_writes_the_rank_into_the_date_column_of_the_rank_row() -> None:
    ranks = {"B0EXAMPLE1": CategoryRank(asin="B0EXAMPLE1", category="収納", rank=12)}

    updates, result = build_rank_updates(ASIN_VALUES, NAME_VALUES, HEADER, ranks, DAY)

    assert {"range": "D10", "values": [[12]]} in updates
    assert result.cells_written == 1
    assert result.skipped_date is False


def test_updates_the_label_when_the_category_is_new() -> None:
    ranks = {"B0EXAMPLE1": CategoryRank(asin="B0EXAMPLE1", category="収納", rank=12)}

    updates, result = build_rank_updates(ASIN_VALUES, NAME_VALUES, HEADER, ranks, DAY)

    assert {"range": "B10", "values": [["順位（収納）"]]} in updates
    assert result.label_updates == 1


def test_leaves_the_label_alone_when_it_already_holds_the_category() -> None:
    name_values = NAME_VALUES[:-1] + ["順位（収納）"]
    ranks = {"B0EXAMPLE1": CategoryRank(asin="B0EXAMPLE1", category="収納", rank=12)}

    updates, result = build_rank_updates(ASIN_VALUES, name_values, HEADER, ranks, DAY)

    assert all(u["range"] != "B10" for u in updates)
    assert result.label_updates == 0


def test_writes_nothing_for_an_unranked_asin() -> None:
    # 順位が付いていない日は空欄のまま。0 を書くと「1位より下」に見える
    ranks = {"B0EXAMPLE1": CategoryRank.unranked("B0EXAMPLE1")}

    updates, result = build_rank_updates(ASIN_VALUES, NAME_VALUES, HEADER, ranks, DAY)

    assert updates == []
    assert result.cells_written == 0


def test_skips_a_day_that_has_no_date_column() -> None:
    ranks = {"B0EXAMPLE1": CategoryRank(asin="B0EXAMPLE1", category="収納", rank=12)}

    updates, result = build_rank_updates(
        ASIN_VALUES, NAME_VALUES, HEADER, ranks, date(2026, 1, 1)
    )

    assert updates == []
    assert result.skipped_date is True


def test_reports_an_asin_without_a_rank_row() -> None:
    ranks = {"B0MISSING1": CategoryRank(asin="B0MISSING1", category="収納", rank=3)}

    _, result = build_rank_updates(ASIN_VALUES, NAME_VALUES, HEADER, ranks, DAY)

    assert result.missing_rows == ["B0MISSING1"]
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `python3 -m pytest src/tests/usecases/test_write_ranks_to_sales_sheet.py -q`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 実装する**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from src.domain.entities.category_rank import CategoryRank
from src.infrastructure.sales_sheet import (
    PRODUCT_NAME_HEADER,
    category_of,
    column_letter,
    column_of,
    date_serial,
    find_date_columns,
    find_rank_rows,
    rank_label,
)


@dataclass(frozen=True)
class RankWriteResult:
    cells_written: int = 0
    label_updates: int = 0
    skipped_date: bool = False
    missing_rows: list[str] = field(default_factory=list)


def build_rank_updates(
    asin_values: list[str],
    name_values: list[str],
    header: list[object],
    ranks: dict[str, CategoryRank],
    day: date,
) -> tuple[list[dict], RankWriteResult]:
    column = find_date_columns(header).get(date_serial(day))
    if column is None:
        return [], RankWriteResult(skipped_date=True)

    rows = find_rank_rows(asin_values, name_values)
    name_column = column_of(header, PRODUCT_NAME_HEADER)
    updates: list[dict] = []
    written = 0
    labels = 0
    missing: list[str] = []
    for asin, rank in ranks.items():
        row = rows.get(asin)
        if row is None:
            missing.append(asin)
            continue
        if rank.rank is not None:
            updates.append(
                {"range": f"{column_letter(column)}{row}", "values": [[rank.rank]]}
            )
            written += 1
        current = name_values[row - 1].strip() if row - 1 < len(name_values) else ""
        if rank.category and category_of(current) != rank.category:
            updates.append({
                "range": f"{column_letter(name_column)}{row}",
                "values": [[rank_label(rank.category)]],
            })
            labels += 1
    return updates, RankWriteResult(
        cells_written=written, label_updates=labels, missing_rows=sorted(missing)
    )
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `python3 -m pytest src/tests -q`
Expected: PASS

- [ ] **Step 5: コミットする**

```bash
git add src/usecases/write_ranks_to_sales_sheet.py src/tests/usecases/test_write_ranks_to_sales_sheet.py pyproject.toml
git commit -m "feat: 順位を売上/日 の順位行へ書く更新を組み立てる"
```

---

### Task 8: main.py の書き込み先を売上/日 へ切り替える

**Files:**
- Modify: `marketar/category-rank/main.py`
- Modify: `marketar/category-rank/src/infrastructure/rank_sheet.py`
- Test: `marketar/category-rank/src/tests/infrastructure/test_rank_sheet.py`

**Interfaces:**
- Consumes: Task 6・7
- Produces: `RankSheet.read_sales_grid(gid) -> tuple[list[str], list[str], list[object]]`（A列・商品名列・ヘッダー行4）、`RankSheet.apply_updates(gid, updates) -> None`

カテゴリの引き継ぎ元がラベル名になるので、旧シートの D列を読む `_known_categories` は不要になる。

- [ ] **Step 1: 失敗するテストを書く**

```python
from unittest.mock import Mock

from src.infrastructure.rank_sheet import RankSheet


def _book_with(values: list[list[str]]) -> Mock:
    sheet = Mock()
    sheet.id = 551300985
    sheet.get_all_values.return_value = values
    book = Mock()
    book.worksheets.return_value = [sheet]
    return book, sheet


def test_read_sales_grid_returns_asins_names_and_header() -> None:
    book, _ = _book_with([
        ["ASIN", "商品名", "目標販売数", "09"],
        ["", "", "", ""],
        ["", "", "", ""],
        ["ASIN", "商品名", "目標販売数", 46274],
        ["B0EXAMPLE1", "商品名です", "", ""],
        ["", "順位", "", ""],
    ])

    asins, names, header = RankSheet(book).read_sales_grid(551300985)

    assert asins[4] == "B0EXAMPLE1"
    assert names[5] == "順位"
    assert header == ["ASIN", "商品名", "目標販売数", 46274]


def test_apply_updates_sends_one_batch() -> None:
    book, sheet = _book_with([[]])

    RankSheet(book).apply_updates(551300985, [{"range": "D10", "values": [[12]]}])

    sheet.batch_update.assert_called_once()


def test_apply_updates_does_nothing_when_there_is_nothing_to_write() -> None:
    book, sheet = _book_with([[]])

    RankSheet(book).apply_updates(551300985, [])

    sheet.batch_update.assert_not_called()
```

ヘッダー行4を数値のまま得るには `get_all_values` ではなく `get_values(value_render_option="UNFORMATTED_VALUE")` が要る。テストの Mock もそれに合わせて `sheet.get_values.return_value` を使うこと（`get_all_values` は A列・商品名列の取得に引き続き使う）。

- [ ] **Step 2: テストが失敗することを確認する**

Run: `python3 -m pytest src/tests/infrastructure/test_rank_sheet.py -q`
Expected: FAIL（`AttributeError: 'RankSheet' object has no attribute 'read_sales_grid'`）

- [ ] **Step 3: 実装する**

`rank_sheet.py` に追加する（`write_table` と `required_size` は移行スクリプトが旧シートを読むために残す）。
先頭に `from src.infrastructure.sales_sheet import PRODUCT_NAME_HEADER, column_of` を足す。

```python
    def read_sales_grid(self, gid: int) -> tuple[list[str], list[str], list[object]]:
        sheet = self._worksheet(gid)
        values = call_with_retry(sheet.get_all_values)
        header = call_with_retry(
            lambda: sheet.get_values(
                "A4:ZZ4", value_render_option="UNFORMATTED_VALUE"
            )
        )
        name_column = column_of(header[0] if header else [], PRODUCT_NAME_HEADER)
        asins = [row[0].strip() if row else "" for row in values]
        names = [
            row[name_column - 1].strip() if len(row) >= name_column else ""
            for row in values
        ]
        return asins, names, (header[0] if header else [])

    def apply_updates(self, gid: int, updates: list[dict]) -> None:
        if not updates:
            return
        sheet = self._worksheet(gid)
        call_with_retry(
            lambda: sheet.batch_update(updates, value_input_option="USER_ENTERED")
        )
```

`main.py` の本体を差し替える。

```python
        asins, names, header = sheet.read_sales_grid(config.sales_sheet_gid)
        sales_asins = [a for a in asins if ASIN_PATTERN.match(a)]
        if not sales_asins:
            LOGGER.error("売上/日から ASIN を取得できませんでした")
            return 1

        known = {
            asin: category_of(names[row - 1])
            for asin, row in find_rank_rows(asins, names).items()
            if category_of(names[row - 1])
        }
        items = catalog.fetch(sales_asins)
        _, ranks = to_products_and_ranks(items, known_categories=known)
        updates, result = build_rank_updates(asins, names, header, ranks, day)
```

ログの `context` を差し替える。

```python
        context = {
            "date": day.isoformat(),
            "asins_in_sales": len(sales_asins),
            "ranked": sum(1 for r in ranks.values() if r.is_ranked),
            "cells_written": result.cells_written,
            "label_updates": result.label_updates,
            "skipped_date": result.skipped_date,
            "rows_not_found": len(result.missing_rows),
            "dry_run": args.dry_run,
        }
```

`--dry-run` は `updates` の先頭6件を表示して終わる。`skipped_date` が真なら「その日の列が売上/日 に無い」と警告を出す。

- [ ] **Step 4: テストが通ることを確認する**

Run: `python3 -m pytest src/tests -q`
Expected: PASS

- [ ] **Step 5: 実データで dry-run する**

```bash
cd /Users/wadaatsushi/Documents/automation/marketar/category-rank
/opt/homebrew/bin/python3 main.py --dry-run
```

Expected: 74件前後の ASIN に対し、順位のセルとラベル更新が並ぶ。`rows_not_found` が 0 であること。

- [ ] **Step 6: コミットする**

```bash
git add main.py src/infrastructure/rank_sheet.py src/tests/infrastructure/test_rank_sheet.py pyproject.toml
git commit -m "feat: カテゴリ順位を売上/日 の順位行へ記録する"
```

---

### Task 9: 旧シートの履歴を売上/日 へ移す

**Files:**
- Create: `marketar/category-rank/migrate_to_sales_sheet.py`
- Test: `marketar/category-rank/src/tests/usecases/test_migrate_to_sales_sheet.py`

**Interfaces:**
- Consumes: Task 6・7
- Produces: `build_migration_updates(old_table, asin_values, name_values, header) -> tuple[list[dict], list[str]]` — 更新の並びと、売上/日 に列が無くて落とした日付の一覧

旧シートは1行目が `["ASIN", "画像", "商品名", "カテゴリ", "2026-06-16", ...]`、以降が ASIN ごとの行。日付は ISO 文字列。

- [ ] **Step 1: 失敗するテストを書く**

```python
from migrate_to_sales_sheet import build_migration_updates

ASIN_VALUES = ["ASIN", "", "", "header", "B0EXAMPLE1", "", "", "", "", ""]
NAME_VALUES = [
    "商品名", "", "", "header",
    "商品名です", "営業利益", "広告経由", "粗利益", "広告費", "順位",
]
HEADER = ["ASIN", "商品名", "目標販売数", 46274, 46273]


def test_writes_each_day_into_its_own_column() -> None:
    old = [
        ["ASIN", "画像", "商品名", "カテゴリ", "2026-09-08", "2026-09-09"],
        ["B0EXAMPLE1", "", "商品名です", "収納", "14", "12"],
    ]

    updates, dropped = build_migration_updates(old, ASIN_VALUES, NAME_VALUES, HEADER)

    assert {"range": "E10", "values": [[14]]} in updates
    assert {"range": "D10", "values": [[12]]} in updates
    assert dropped == []


def test_sets_the_label_from_the_old_category_column() -> None:
    old = [
        ["ASIN", "画像", "商品名", "カテゴリ", "2026-09-09"],
        ["B0EXAMPLE1", "", "商品名です", "収納", "12"],
    ]

    updates, _ = build_migration_updates(old, ASIN_VALUES, NAME_VALUES, HEADER)

    assert {"range": "B10", "values": [["順位（収納）"]]} in updates


def test_drops_days_that_have_no_column_in_the_sales_sheet() -> None:
    old = [
        ["ASIN", "画像", "商品名", "カテゴリ", "2026-01-01"],
        ["B0EXAMPLE1", "", "商品名です", "収納", "12"],
    ]

    updates, dropped = build_migration_updates(old, ASIN_VALUES, NAME_VALUES, HEADER)

    # 列が無い日の順位は書けないが、カテゴリのラベルだけは入れてよい
    assert all(u["values"] != [[12]] for u in updates)
    assert dropped == ["2026-01-01"]


def test_skips_empty_cells() -> None:
    old = [
        ["ASIN", "画像", "商品名", "カテゴリ", "2026-09-09"],
        ["B0EXAMPLE1", "", "商品名です", "収納", ""],
    ]

    updates, _ = build_migration_updates(old, ASIN_VALUES, NAME_VALUES, HEADER)

    assert all(u["range"] != "D10" for u in updates)
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `python3 -m pytest src/tests/usecases/test_migrate_to_sales_sheet.py -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'migrate_to_sales_sheet'`）

- [ ] **Step 3: 実装する**

`migrate_to_sales_sheet.py` を作る。

```python
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

from src.infrastructure.configuration import load_configuration  # noqa: E402
from src.infrastructure.rank_sheet import RankSheet, open_book  # noqa: E402
from src.infrastructure.sales_sheet import (  # noqa: E402
    PRODUCT_NAME_HEADER,
    category_of,
    column_letter,
    column_of,
    date_serial,
    find_date_columns,
    find_rank_rows,
    rank_label,
)

COL_ASIN = 0
COL_CATEGORY = 3
FIXED_COLUMNS = 4


def build_migration_updates(
    old_table: list[list[str]],
    asin_values: list[str],
    name_values: list[str],
    header: list[object],
) -> tuple[list[dict], list[str]]:
    if not old_table or not old_table[0]:
        return [], []
    days = [cell.strip() for cell in old_table[0][FIXED_COLUMNS:]]
    columns = find_date_columns(header)
    rows = find_rank_rows(asin_values, name_values)
    name_column = column_of(header, PRODUCT_NAME_HEADER)

    updates: list[dict] = []
    dropped: list[str] = []
    for row in old_table[1:]:
        asin = _at(row, COL_ASIN)
        target_row = rows.get(asin)
        if not asin or target_row is None:
            continue
        _append_label_update(
            updates, row, target_row, name_column, name_values
        )
        for index, day in enumerate(days):
            value = _at(row, FIXED_COLUMNS + index)
            if not value:
                continue
            column = columns.get(date_serial(date.fromisoformat(day)))
            if column is None:
                if day not in dropped:
                    dropped.append(day)
                continue
            updates.append({
                "range": f"{column_letter(column)}{target_row}",
                "values": [[int(value)]],
            })
    return updates, dropped


def _append_label_update(
    updates: list[dict],
    old_row: list[str],
    target_row: int,
    name_column: int,
    name_values: list[str],
) -> None:
    category = _at(old_row, COL_CATEGORY)
    if not category:
        return
    current = name_values[target_row - 1] if target_row - 1 < len(name_values) else ""
    if category_of(current) == category:
        return
    updates.append({
        "range": f"{column_letter(name_column)}{target_row}",
        "values": [[rank_label(category)]],
    })


def _at(row: list[str], index: int) -> str:
    return row[index].strip() if index < len(row) else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="書かずに件数だけ出す")
    args = parser.parse_args()

    config = load_configuration(PROJECT_DIR)
    book = open_book(str(config.service_account_file), config.spreadsheet_id)
    sheet = RankSheet(book)
    old_table = sheet.read_table(config.rank_sheet_gid)
    asins, names, header = sheet.read_sales_grid(config.sales_sheet_gid)

    updates, dropped = build_migration_updates(old_table, asins, names, header)
    print(f"移す件数: {len(updates)} セル")
    if dropped:
        print(f"売上/日 に列が無く落とす日付（{len(dropped)}日）: {', '.join(sorted(dropped))}")
    if args.dry_run:
        print("--dry-run のため書き込みません")
        return 0

    sheet.apply_updates(config.sales_sheet_gid, updates)
    print("移行しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

順位の値は `int(value)` にする。旧シートは文字列で持っているため、そのまま書くとグラデーションが
効かない。空欄はそのまま飛ばす（0 を書かない）。

- [ ] **Step 4: テストが通ることを確認する**

Run: `python3 -m pytest src/tests -q`
Expected: PASS

- [ ] **Step 5: dry-run して内容を確認する**

```bash
/opt/homebrew/bin/python3 migrate_to_sales_sheet.py --dry-run
```

Expected: 移す件数と、売上/日 に列が無くて落とす日付が出る。落とす日付が 6/16 より前だけであることを確認する。

- [ ] **Step 6: 移行を実行する**

```bash
/opt/homebrew/bin/python3 migrate_to_sales_sheet.py
```

- [ ] **Step 7: 目視で確認する**

売上/日 の順位行に過去の順位が入り、ラベルが `順位（カテゴリ名）` になっていることを確認する。

- [ ] **Step 8: コミットする**

```bash
git add migrate_to_sales_sheet.py src/tests/usecases/test_migrate_to_sales_sheet.py pyproject.toml
git commit -m "feat: 旧カテゴリランキングシートの履歴を売上/日 へ移す"
```

---

### Task 10: 旧シートを削除し、ドキュメントを更新する

**Files:**
- Delete: `marketar/category-rank/migrate_to_sales_sheet.py` と そのテスト
- Modify: `marketar/category-rank/README.md`
- Modify: `data-engineer/download-amazon-data/CLAUDE.md`
- Modify: `data-engineer/download-amazon-data/docs/superpowers/specs/2026-09-07-sales-daily-sheet-spec.md`

**Interfaces:**
- Consumes: Task 1〜9
- Produces: なし

- [ ] **Step 1: 旧シートを削除する**

売上/日 の順位行に履歴が入っていることを確認したうえで、スプレッドシートの「カテゴリランキング」シート（gid `533865782`）を削除する。**削除は取り消せない。実行前に Task 9 Step 7 の目視確認を終えていること。**

- [ ] **Step 2: 移行スクリプトを消す**

1回限りの用途で、旧シートが無くなると再実行できない。

```bash
git rm migrate_to_sales_sheet.py src/tests/usecases/test_migrate_to_sales_sheet.py
```

- [ ] **Step 3: category-rank の README を書き直す**

「カテゴリランキング」シートへ書くという記述を、売上/日 の順位行へ書くという記述に差し替える。次の点を残す。

- ラベル名は `順位（カテゴリ名）`。カテゴリが未判明なら `順位`
- カテゴリは一度記録したものを追い続ける（引き継ぎ元はラベル名）
- 日付列は作らない。無い日はスキップして件数を出す
- 売上/日 に無い ASIN は対象外

- [ ] **Step 4: download-amazon-data のドキュメントを直す**

`CLAUDE.md` の「『売上/日』は ASIN 1件につき5行」の節を6行に直す。次を書く。

- 表に `順位（カテゴリ名）` の行を足す（書くのは `category-rank`、たたむ、色はうすい青←最上位・最下位→うすい赤）
- **ラベル判定は順位だけ前方一致**であること。理由（カテゴリ名をラベルに埋めている）と、`matches_label` を通さずに `name == label` で書くと順位行が毎回増殖すること
- ラベルの順序と本数の一致が要るのは `label_rows.ROW_LABELS_IN_ORDER`、`insert_label_rows.py`、`listing-creator` の `LABEL_ROWS_IN_ORDER` の3箇所（従来どおり）

`docs/superpowers/specs/2026-09-07-sales-daily-sheet-spec.md` の「5. 色の意味」の表に順位の行を足す。

- [ ] **Step 5: 定期実行が通ることを確認する**

```bash
launchctl start com.automation.category-rank
launchctl print gui/$(id -u)/com.automation.category-rank | grep -E "runs|last exit code"
```

Expected: `runs` が増え、`last exit code = 0`

- [ ] **Step 6: コミットする**

```bash
git -C marketar/category-rank add -A && git -C marketar/category-rank commit -m "docs: 順位の記録先を売上/日 に変更したことを反映"
git -C data-engineer/download-amazon-data add CLAUDE.md docs/superpowers/specs/2026-09-07-sales-daily-sheet-spec.md pyproject.toml
git -C data-engineer/download-amazon-data commit -m "docs: 売上/日 の順位行を追記"
```
