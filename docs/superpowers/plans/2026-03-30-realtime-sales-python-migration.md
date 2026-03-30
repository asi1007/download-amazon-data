# リアルタイム売上 Python移行 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GASの `updateRealtimeSales()` をPythonに完全移行する。Orders API → orderMetrics API、金額 = unitCount × 自社価格。

**Architecture:** SpApiSalesRepository で orderMetrics API から個数を取得し、SalesSheet から自社価格を読み取り、unitCount × 自社価格で金額を算出。RealtimeSalesSheet でC列（個数）・D列（金額）に書き込む。

**Tech Stack:** Python 3.12+, gspread, requests, pytest

---

## ファイル構成

| ファイル | 操作 | 責務 |
|---------|------|------|
| `py_src/infrastructure/sheets/sales_sheet.py` | 修正 | `get_selling_prices()` 追加 |
| `py_src/usecases/update_realtime_sales.py` | 書き換え | OrdersRepository → SpApiSalesRepository、自社価格フォールバック |
| `main.py` | 修正 | エントリポイントの依存差し替え |
| `py_tests/test_sales_sheet.py` | 修正 | `get_selling_prices` テスト追加 |
| `py_tests/test_update_realtime_sales.py` | 書き換え | 新UseCase構成のテスト |

---

### Task 1: SalesSheet.get_selling_prices() のテストと実装

**Files:**
- Modify: `py_tests/test_sales_sheet.py`
- Modify: `py_src/infrastructure/sheets/sales_sheet.py`

- [ ] **Step 1: テストを書く**

`py_tests/test_sales_sheet.py` の末尾に追加:

```python
class TestGetSellingPrices:
    def test_returns_asin_to_price_map(self) -> None:
        sales_ws = Mock()
        settings_ws = Mock()
        settings_ws.acell.side_effect = lambda cell: Mock(value="3" if cell == "B2" else "5")
        sales_ws.col_values.return_value = [
            "header", "header2", "header3", "header4",
            "B00EXAMPLE", "B00EXAMPLF", "B00EXAMPLG",
        ]
        sales_ws.get.return_value = [
            ["header"], ["header2"], ["header3"], ["header4"],
            ["500"], ["800"], [""],
        ]
        sheet = SalesSheet(sales_worksheet=sales_ws, settings_worksheet=settings_ws)
        sheet.get_asin_list()
        prices = sheet.get_selling_prices()
        assert prices == {"B00EXAMPLE": 500.0, "B00EXAMPLF": 800.0}

    def test_returns_empty_when_no_asins(self) -> None:
        sales_ws = Mock()
        settings_ws = Mock()
        settings_ws.acell.side_effect = lambda cell: Mock(value="3" if cell == "B2" else "5")
        sales_ws.col_values.return_value = ["header"]
        sheet = SalesSheet(sales_worksheet=sales_ws, settings_worksheet=settings_ws)
        sheet.get_asin_list()
        prices = sheet.get_selling_prices()
        assert prices == {}
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest py_tests/test_sales_sheet.py::TestGetSellingPrices -v`
Expected: FAIL with `AttributeError: 'SalesSheet' object has no attribute 'get_selling_prices'`

- [ ] **Step 3: 実装**

`py_src/infrastructure/sheets/sales_sheet.py` に追加:

```python
def get_selling_prices(self) -> dict[str, float]:
    if not self._asin_list:
        return {}
    last_row = max(self._asin_to_row.values())
    col_letter = chr(ord("A") + self._price_column - 1)
    price_range = f"{col_letter}1:{col_letter}{last_row}"
    price_values = self._worksheet.get(price_range)
    result: dict[str, float] = {}
    for asin in self._asin_list:
        row = self._asin_to_row[asin]
        if row - 1 < len(price_values):
            cell_value = price_values[row - 1][0] if price_values[row - 1] else ""
            if cell_value:
                result[asin] = float(cell_value)
    return result
```

- [ ] **Step 4: テストがパスすることを確認**

Run: `pytest py_tests/test_sales_sheet.py::TestGetSellingPrices -v`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add py_src/infrastructure/sheets/sales_sheet.py py_tests/test_sales_sheet.py
git commit -m "feat: SalesSheet.get_selling_prices() を追加"
```

---

### Task 2: UpdateRealtimeSalesUseCase のテスト書き換え

**Files:**
- Rewrite: `py_tests/test_update_realtime_sales.py`

- [ ] **Step 1: テストファイルを書き換え**

```python
import pytest
from unittest.mock import Mock
from py_src.usecases.update_realtime_sales import UpdateRealtimeSalesUseCase
from py_src.domain.value_objects.sales_info import SalesInfo


class TestUpdateRealtimeSalesUseCase:
    def test_calculates_amount_from_unit_count_and_selling_price(self) -> None:
        mock_realtime_sheet = Mock()
        mock_realtime_sheet.get_asin_list.return_value = ["B00EXAMPLE", "B00EXAMPLF"]
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=3, total_sales_amount=900.0, order_count=2),
            "B00EXAMPLF": SalesInfo(unit_count=1, total_sales_amount=400.0, order_count=1),
        }
        mock_sales_sheet = Mock()
        mock_sales_sheet.get_selling_prices.return_value = {
            "B00EXAMPLE": 500.0,
            "B00EXAMPLF": 800.0,
        }
        usecase = UpdateRealtimeSalesUseCase(
            realtime_sheet=mock_realtime_sheet,
            sales_repository=mock_sales_repo,
            sales_sheet=mock_sales_sheet,
        )
        usecase.execute()

        sales_map = mock_realtime_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 3
        assert sales_map["B00EXAMPLE"].total_amount == 1500.0
        assert sales_map["B00EXAMPLF"].unit_count == 1
        assert sales_map["B00EXAMPLF"].total_amount == 800.0

    def test_zero_sales(self) -> None:
        mock_realtime_sheet = Mock()
        mock_realtime_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=0, total_sales_amount=0.0, order_count=0),
        }
        mock_sales_sheet = Mock()
        mock_sales_sheet.get_selling_prices.return_value = {"B00EXAMPLE": 500.0}
        usecase = UpdateRealtimeSalesUseCase(
            realtime_sheet=mock_realtime_sheet,
            sales_repository=mock_sales_repo,
            sales_sheet=mock_sales_sheet,
        )
        usecase.execute()

        sales_map = mock_realtime_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 0
        assert sales_map["B00EXAMPLE"].total_amount == 0.0

    def test_missing_selling_price_defaults_to_zero(self) -> None:
        mock_realtime_sheet = Mock()
        mock_realtime_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=5, total_sales_amount=1000.0, order_count=3),
        }
        mock_sales_sheet = Mock()
        mock_sales_sheet.get_selling_prices.return_value = {}
        usecase = UpdateRealtimeSalesUseCase(
            realtime_sheet=mock_realtime_sheet,
            sales_repository=mock_sales_repo,
            sales_sheet=mock_sales_sheet,
        )
        usecase.execute()

        sales_map = mock_realtime_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 5
        assert sales_map["B00EXAMPLE"].total_amount == 0.0

    def test_works_without_sales_sheet(self) -> None:
        mock_realtime_sheet = Mock()
        mock_realtime_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=5, total_sales_amount=1000.0, order_count=3),
        }
        usecase = UpdateRealtimeSalesUseCase(
            realtime_sheet=mock_realtime_sheet,
            sales_repository=mock_sales_repo,
        )
        usecase.execute()

        sales_map = mock_realtime_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 5
        assert sales_map["B00EXAMPLE"].total_amount == 0.0
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest py_tests/test_update_realtime_sales.py -v`
Expected: FAIL（コンストラクタ引数の不一致）

---

### Task 3: UpdateRealtimeSalesUseCase の実装書き換え

**Files:**
- Rewrite: `py_src/usecases/update_realtime_sales.py`

- [ ] **Step 1: UseCase を書き換え**

```python
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from py_src.domain.value_objects.realtime_sales_result import RealtimeSalesResult
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.infrastructure.api.sp_api_sales_repository import SpApiSalesRepository
from py_src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet
from py_src.infrastructure.sheets.sales_sheet import SalesSheet

JST = timezone(timedelta(hours=9))


class UpdateRealtimeSalesUseCase:
    def __init__(
        self,
        realtime_sheet: RealtimeSalesSheet,
        sales_repository: SpApiSalesRepository,
        sales_sheet: SalesSheet | None = None,
    ) -> None:
        self._realtime_sheet = realtime_sheet
        self._sales_repository = sales_repository
        self._sales_sheet = sales_sheet

    def execute(self) -> None:
        asin_list = self._realtime_sheet.get_asin_list()
        selling_prices = self._load_selling_prices()
        start_date, end_date = self._get_today_range()
        sales_infos = self._sales_repository.get_daily_sales(asin_list, start_date, end_date)
        sales_map = self._build_sales_map(asin_list, sales_infos, selling_prices)
        self._realtime_sheet.write_realtime_sales(sales_map)

    def _load_selling_prices(self) -> dict[str, float]:
        if not self._sales_sheet:
            return {}
        self._sales_sheet.get_asin_list()
        return self._sales_sheet.get_selling_prices()

    def _get_today_range(self) -> tuple[str, str]:
        now = datetime.now(JST)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        start_utc = today_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_utc = tomorrow_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return start_utc, end_utc

    def _build_sales_map(
        self,
        asin_list: list[str],
        sales_infos: dict[str, SalesInfo],
        selling_prices: dict[str, float],
    ) -> dict[str, RealtimeSalesResult]:
        sales_map: dict[str, RealtimeSalesResult] = {}
        for asin in asin_list:
            info = sales_infos.get(asin, SalesInfo())
            unit_count = info.unit_count
            total_amount = unit_count * selling_prices.get(asin, 0.0)
            sales_map[asin] = RealtimeSalesResult(
                asin=asin, unit_count=unit_count, total_amount=total_amount,
            )
        return sales_map
```

- [ ] **Step 2: テストがパスすることを確認**

Run: `pytest py_tests/test_update_realtime_sales.py -v`
Expected: 4 PASSED

- [ ] **Step 3: コミット**

```bash
git add py_src/usecases/update_realtime_sales.py py_tests/test_update_realtime_sales.py
git commit -m "feat: UpdateRealtimeSalesUseCase を orderMetrics + 自社価格 方式に書き換え"
```

---

### Task 4: main.py のエントリポイント更新

**Files:**
- Modify: `main.py`

- [ ] **Step 1: main() 関数を書き換え**

`main.py` の `main()` 関数を以下に変更:

```python
def main() -> None:
    load_dotenv()
    authenticator = _create_authenticator()
    sales_repository = SpApiSalesRepository(authenticator=authenticator)
    spreadsheet = _open_spreadsheet()

    realtime_ws = spreadsheet.worksheet("売上/今")
    realtime_sheet = RealtimeSalesSheet(worksheet=realtime_ws)

    sales_ws = spreadsheet.worksheet("売上/日")
    settings_ws = spreadsheet.worksheet("設定")
    sales_sheet = SalesSheet(sales_worksheet=sales_ws, settings_worksheet=settings_ws)

    usecase = UpdateRealtimeSalesUseCase(
        realtime_sheet=realtime_sheet,
        sales_repository=sales_repository,
        sales_sheet=sales_sheet,
    )
    usecase.execute()
```

import 文の変更:
- 削除: `from py_src.infrastructure.api.orders_repository import OrdersRepository`
- 追加なし（`SpApiSalesRepository`, `SalesSheet` は既存import）

- [ ] **Step 2: 全テストがパスすることを確認**

Run: `pytest py_tests/ -v`
Expected: ALL PASSED

- [ ] **Step 3: コミット**

```bash
git add main.py
git commit -m "feat: main.py を orderMetrics + 自社価格 方式に更新"
```

---

### Task 5: 手動実行テスト

- [ ] **Step 1: ローカルで実行**

```bash
python main.py
```

Expected: 「売上/今」シートのC列（個数）・D列（金額）が更新される

- [ ] **Step 2: 結果確認**

「売上/今」シートで B0FR3CZRGP の金額が `個数 × 524` になっていることを確認

- [ ] **Step 3: 最終コミット・プッシュ**

```bash
git push
```
