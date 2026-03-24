# リアルタイム売上モニタリング Python版 実装計画

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GASのリアルタイム売上モニタリングをPythonに書き直し、SP-APIのレートリミット問題を解消する

**Architecture:** python-amazon-sp-apiでOrders API呼び出し（レートリミット自動制御）、gspreadでGoogle Sheets書き込み。DDD構造でEntity/ValueObject/Repository/UseCaseに分離。

**Tech Stack:** Python 3.12, python-amazon-sp-api, gspread, oauth2client, python-dotenv, pytest

---

## ファイル構成

```
src/
├── domain/
│   ├── entities/
│   │   └── order.py                    # Order, OrderItem dataclass
│   └── value_objects/
│       └── realtime_sales_result.py    # ASIN別集計結果
├── infrastructure/
│   ├── api/
│   │   └── orders_repository.py       # SP-API呼び出し
│   └── sheets/
│       └── realtime_sales_sheet.py     # gspreadでシート読み書き
└── usecases/
    └── update_realtime_sales.py        # オーケストレーション

tests/
├── test_order.py
├── test_realtime_sales_result.py
├── test_orders_repository.py
├── test_realtime_sales_sheet.py
└── test_update_realtime_sales.py

main.py                                 # エントリポイント
pyproject.toml
.env.example
```

---

## Chunk 1: プロジェクトセットアップ + ドメイン層

### Task 1: プロジェクト初期化

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`

- [ ] **Step 1: pyproject.toml を作成**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "download-amazon-data"
version = "0.1.0"
description = "Amazon SP-API リアルタイム売上モニタリング"
requires-python = ">=3.12"

dependencies = [
    "python-amazon-sp-api>=0.3.0",
    "gspread>=6.1.2",
    "oauth2client>=4.1.3",
    "python-dotenv>=1.0.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.3",
    "pytest-mock>=3.14.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
addopts = "-v --tb=short"
```

- [ ] **Step 2: .env.example を作成**

```
# Amazon SP-API
SP_API_REFRESH_TOKEN=your_refresh_token
LWA_APP_ID=your_lwa_app_id
LWA_CLIENT_SECRET=your_lwa_client_secret
SP_API_ACCESS_KEY=your_aws_access_key
SP_API_SECRET_KEY=your_aws_secret_key
SP_API_ROLE_ARN=your_role_arn

# Google Sheets
GOOGLE_CREDENTIALS_FILE=service_account.json

# Target Sheet
SPREADSHEET_ID=1Z3P0iL19r3gA9-NG8x2e_42pGhrEs_wFMLWLbFvReAw
SHEET_NAME=売上/今
```

- [ ] **Step 3: ディレクトリ構造を作成**

```bash
mkdir -p src/domain/entities src/domain/value_objects src/infrastructure/api src/infrastructure/sheets src/usecases tests
touch src/__init__.py src/domain/__init__.py src/domain/entities/__init__.py src/domain/value_objects/__init__.py src/infrastructure/__init__.py src/infrastructure/api/__init__.py src/infrastructure/sheets/__init__.py src/usecases/__init__.py
```

- [ ] **Step 4: 依存関係をインストール**

```bash
pip install -e ".[dev]"
```

- [ ] **Step 5: コミット**

```bash
git add pyproject.toml .env.example src/ tests/
git commit -m "feat: Python版プロジェクト初期化"
```

---

### Task 2: Order エンティティ

**Files:**
- Create: `tests/test_order.py`
- Create: `src/domain/entities/order.py`

- [ ] **Step 1: テストを書く**

```python
# tests/test_order.py
from src.domain.entities.order import Order, OrderItem


class TestOrderItem:
    def test_from_api_response(self) -> None:
        api_data: dict = {
            "ASIN": "B00EXAMPLE",
            "QuantityOrdered": 2,
            "ItemPrice": {"CurrencyCode": "JPY", "Amount": "3000"},
        }
        item = OrderItem.from_api_response(api_data)

        assert item.asin == "B00EXAMPLE"
        assert item.quantity_ordered == 2
        assert item.item_price_amount == 3000.0

    def test_missing_item_price(self) -> None:
        api_data: dict = {
            "ASIN": "B00EXAMPLE",
            "QuantityOrdered": 1,
            "ItemPrice": None,
        }
        item = OrderItem.from_api_response(api_data)

        assert item.item_price_amount == 0.0

    def test_no_item_price_key(self) -> None:
        api_data: dict = {
            "ASIN": "B00EXAMPLE",
            "QuantityOrdered": 1,
        }
        item = OrderItem.from_api_response(api_data)

        assert item.item_price_amount == 0.0


class TestOrder:
    def test_from_api_response(self) -> None:
        order_data: dict = {
            "AmazonOrderId": "503-001",
            "OrderStatus": "Shipped",
            "PurchaseDate": "2026-03-15T10:00:00Z",
        }
        items_data: list[dict] = [
            {"ASIN": "B00EXAMPLE", "QuantityOrdered": 2, "ItemPrice": {"CurrencyCode": "JPY", "Amount": "3000"}},
        ]
        order = Order.from_api_response(order_data, items_data)

        assert order.order_id == "503-001"
        assert order.order_status == "Shipped"
        assert len(order.items) == 1

    def test_is_canceled_true(self) -> None:
        order = Order(order_id="503-001", order_status="Canceled", items=[])

        assert order.is_canceled is True

    def test_is_canceled_false(self) -> None:
        order = Order(order_id="503-001", order_status="Shipped", items=[])

        assert order.is_canceled is False
```

- [ ] **Step 2: テスト実行、失敗を確認**

```bash
pytest tests/test_order.py -v
```
Expected: FAIL (import error)

- [ ] **Step 3: 実装**

```python
# src/domain/entities/order.py
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class OrderItem:
    asin: str
    quantity_ordered: int
    item_price_amount: float

    @staticmethod
    def from_api_response(data: dict) -> OrderItem:
        price = data.get("ItemPrice")
        amount = float(price["Amount"]) if price else 0.0
        return OrderItem(
            asin=data["ASIN"],
            quantity_ordered=data["QuantityOrdered"],
            item_price_amount=amount,
        )


@dataclass(frozen=True)
class Order:
    order_id: str
    order_status: str
    items: list[OrderItem]

    @property
    def is_canceled(self) -> bool:
        return self.order_status == "Canceled"

    @staticmethod
    def from_api_response(order_data: dict, items_data: list[dict]) -> Order:
        return Order(
            order_id=order_data["AmazonOrderId"],
            order_status=order_data["OrderStatus"],
            items=[OrderItem.from_api_response(item) for item in items_data],
        )
```

- [ ] **Step 4: テスト実行、パスを確認**

```bash
pytest tests/test_order.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 5: コミット**

```bash
git add src/domain/entities/order.py tests/test_order.py
git commit -m "feat: Order エンティティを追加"
```

---

### Task 3: RealtimeSalesResult 値オブジェクト

**Files:**
- Create: `tests/test_realtime_sales_result.py`
- Create: `src/domain/value_objects/realtime_sales_result.py`

- [ ] **Step 1: テストを書く**

```python
# tests/test_realtime_sales_result.py
from src.domain.value_objects.realtime_sales_result import RealtimeSalesResult


class TestRealtimeSalesResult:
    def test_initial_values(self) -> None:
        result = RealtimeSalesResult(asin="B00EXAMPLE")

        assert result.unit_count == 0
        assert result.total_amount == 0.0

    def test_add_sale(self) -> None:
        result = RealtimeSalesResult(asin="B00EXAMPLE")
        result.add_sale(quantity=2, amount=3000.0)

        assert result.unit_count == 2
        assert result.total_amount == 3000.0

    def test_add_sale_accumulates(self) -> None:
        result = RealtimeSalesResult(asin="B00EXAMPLE")
        result.add_sale(quantity=2, amount=3000.0)
        result.add_sale(quantity=1, amount=1500.0)

        assert result.unit_count == 3
        assert result.total_amount == 4500.0
```

- [ ] **Step 2: テスト実行、失敗を確認**

```bash
pytest tests/test_realtime_sales_result.py -v
```

- [ ] **Step 3: 実装**

```python
# src/domain/value_objects/realtime_sales_result.py
from dataclasses import dataclass, field


@dataclass
class RealtimeSalesResult:
    asin: str
    unit_count: int = field(default=0)
    total_amount: float = field(default=0.0)

    def add_sale(self, quantity: int, amount: float) -> None:
        self.unit_count += quantity
        self.total_amount += amount
```

- [ ] **Step 4: テスト実行、パスを確認**

```bash
pytest tests/test_realtime_sales_result.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: コミット**

```bash
git add src/domain/value_objects/realtime_sales_result.py tests/test_realtime_sales_result.py
git commit -m "feat: RealtimeSalesResult 値オブジェクトを追加"
```

---

## Chunk 2: インフラ層 + ユースケース + エントリポイント

### Task 4: OrdersRepository（SP-API呼び出し）

**Files:**
- Create: `tests/test_orders_repository.py`
- Create: `src/infrastructure/api/orders_repository.py`

- [ ] **Step 1: テストを書く**

```python
# tests/test_orders_repository.py
from unittest.mock import Mock, patch, MagicMock
from src.infrastructure.api.orders_repository import OrdersRepository
from src.domain.entities.order import Order


class TestOrdersRepository:
    def test_get_orders_with_items(self) -> None:
        mock_orders_client = Mock()
        mock_orders_response = Mock()
        mock_orders_response.payload = {
            "Orders": [
                {
                    "AmazonOrderId": "503-001",
                    "OrderStatus": "Shipped",
                    "PurchaseDate": "2026-03-15T10:00:00Z",
                },
            ],
        }
        mock_orders_client.get_orders.return_value = mock_orders_response

        mock_items_response = Mock()
        mock_items_response.payload = {
            "OrderItems": [
                {
                    "ASIN": "B00EXAMPLE",
                    "QuantityOrdered": 2,
                    "ItemPrice": {"CurrencyCode": "JPY", "Amount": "3000"},
                },
            ],
        }
        mock_orders_client.get_order_items.return_value = mock_items_response

        repo = OrdersRepository(orders_client=mock_orders_client)
        orders = repo.get_orders_with_items(created_after="2026-03-15T00:00:00Z")

        assert len(orders) == 1
        assert orders[0].order_id == "503-001"
        assert orders[0].items[0].asin == "B00EXAMPLE"
        assert orders[0].items[0].quantity_ordered == 2

    def test_get_orders_with_items_empty(self) -> None:
        mock_orders_client = Mock()
        mock_orders_response = Mock()
        mock_orders_response.payload = {"Orders": []}
        mock_orders_client.get_orders.return_value = mock_orders_response

        repo = OrdersRepository(orders_client=mock_orders_client)
        orders = repo.get_orders_with_items(created_after="2026-03-15T00:00:00Z")

        assert len(orders) == 0

    def test_get_orders_with_items_pagination(self) -> None:
        mock_orders_client = Mock()

        page1 = Mock()
        page1.payload = {
            "Orders": [
                {"AmazonOrderId": "503-001", "OrderStatus": "Shipped", "PurchaseDate": "2026-03-15T10:00:00Z"},
            ],
            "NextToken": "token123",
        }
        page2 = Mock()
        page2.payload = {
            "Orders": [
                {"AmazonOrderId": "503-002", "OrderStatus": "Shipped", "PurchaseDate": "2026-03-15T11:00:00Z"},
            ],
        }
        mock_orders_client.get_orders.side_effect = [page1, page2]

        mock_items_response = Mock()
        mock_items_response.payload = {
            "OrderItems": [
                {"ASIN": "B00EXAMPLE", "QuantityOrdered": 1, "ItemPrice": {"CurrencyCode": "JPY", "Amount": "1000"}},
            ],
        }
        mock_orders_client.get_order_items.return_value = mock_items_response

        repo = OrdersRepository(orders_client=mock_orders_client)
        orders = repo.get_orders_with_items(created_after="2026-03-15T00:00:00Z")

        assert len(orders) == 2
```

- [ ] **Step 2: テスト実行、失敗を確認**

```bash
pytest tests/test_orders_repository.py -v
```

- [ ] **Step 3: 実装**

```python
# src/infrastructure/api/orders_repository.py
from __future__ import annotations
from sp_api.api import Orders
from sp_api.base import Marketplaces
from src.domain.entities.order import Order

MARKETPLACE_JP = "A1VC38T7YXB528"


class OrdersRepository:
    def __init__(self, orders_client: Orders | None = None) -> None:
        self._client = orders_client or Orders(marketplace=Marketplaces.JP)

    def get_orders_with_items(self, created_after: str) -> list[Order]:
        raw_orders = self._fetch_all_orders(created_after)
        if not raw_orders:
            return []
        return [self._build_order(raw) for raw in raw_orders]

    def _fetch_all_orders(self, created_after: str) -> list[dict]:
        all_orders: list[dict] = []
        response = self._client.get_orders(
            CreatedAfter=created_after,
            MarketplaceIds=[MARKETPLACE_JP],
        )
        all_orders.extend(response.payload.get("Orders", []))

        while response.payload.get("NextToken"):
            response = self._client.get_orders(
                CreatedAfter=created_after,
                MarketplaceIds=[MARKETPLACE_JP],
                NextToken=response.payload["NextToken"],
            )
            all_orders.extend(response.payload.get("Orders", []))

        return all_orders

    def _build_order(self, raw_order: dict) -> Order:
        response = self._client.get_order_items(raw_order["AmazonOrderId"])
        items_data = response.payload.get("OrderItems", [])
        return Order.from_api_response(raw_order, items_data)
```

- [ ] **Step 4: テスト実行、パスを確認**

```bash
pytest tests/test_orders_repository.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: コミット**

```bash
git add src/infrastructure/api/orders_repository.py tests/test_orders_repository.py
git commit -m "feat: OrdersRepository を追加（SP-API呼び出し）"
```

---

### Task 5: RealtimeSalesSheet（gspread）

**Files:**
- Create: `tests/test_realtime_sales_sheet.py`
- Create: `src/infrastructure/sheets/realtime_sales_sheet.py`

- [ ] **Step 1: テストを書く**

```python
# tests/test_realtime_sales_sheet.py
from unittest.mock import Mock
from src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet
from src.domain.value_objects.realtime_sales_result import RealtimeSalesResult


class TestRealtimeSalesSheet:
    def test_get_asin_list(self) -> None:
        mock_worksheet = Mock()
        mock_worksheet.col_values.return_value = ["ASIN", "B00EXAMPLE", "B00EXAMPLF", "B00EXAMPLG"]

        sheet = RealtimeSalesSheet(worksheet=mock_worksheet)
        asin_list = sheet.get_asin_list()

        assert asin_list == ["B00EXAMPLE", "B00EXAMPLF", "B00EXAMPLG"]

    def test_get_asin_list_filters_invalid(self) -> None:
        mock_worksheet = Mock()
        mock_worksheet.col_values.return_value = ["ASIN", "B00EXAMPLE", "", "SHORT", "B00EXAMPLF"]

        sheet = RealtimeSalesSheet(worksheet=mock_worksheet)
        asin_list = sheet.get_asin_list()

        assert asin_list == ["B00EXAMPLE", "B00EXAMPLF"]

    def test_write_realtime_sales(self) -> None:
        mock_worksheet = Mock()
        mock_worksheet.col_values.return_value = ["ASIN", "B00EXAMPLE", "B00EXAMPLF"]

        sheet = RealtimeSalesSheet(worksheet=mock_worksheet)
        sheet.get_asin_list()

        sales_map: dict[str, RealtimeSalesResult] = {
            "B00EXAMPLE": RealtimeSalesResult(asin="B00EXAMPLE", unit_count=5, total_amount=10000.0),
        }
        sheet.write_realtime_sales(sales_map)

        mock_worksheet.update.assert_called_once_with(
            "B2",
            [[5, 10000.0], [0, 0.0]],
        )
```

- [ ] **Step 2: テスト実行、失敗を確認**

```bash
pytest tests/test_realtime_sales_sheet.py -v
```

- [ ] **Step 3: 実装**

```python
# src/infrastructure/sheets/realtime_sales_sheet.py
from __future__ import annotations
from gspread import Worksheet
from src.domain.value_objects.realtime_sales_result import RealtimeSalesResult


class RealtimeSalesSheet:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet
        self._asin_list: list[str] = []

    def get_asin_list(self) -> list[str]:
        values = self._worksheet.col_values(1)
        self._asin_list = [v for v in values[1:] if v and len(v) == 10]
        return self._asin_list

    def write_realtime_sales(self, sales_map: dict[str, RealtimeSalesResult]) -> None:
        write_data = []
        for asin in self._asin_list:
            sales = sales_map.get(asin)
            if sales:
                write_data.append([sales.unit_count, sales.total_amount])
            else:
                write_data.append([0, 0.0])

        if write_data:
            self._worksheet.update("B2", write_data)
```

- [ ] **Step 4: テスト実行、パスを確認**

```bash
pytest tests/test_realtime_sales_sheet.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: コミット**

```bash
git add src/infrastructure/sheets/realtime_sales_sheet.py tests/test_realtime_sales_sheet.py
git commit -m "feat: RealtimeSalesSheet を追加（gspread）"
```

---

### Task 6: UpdateRealtimeSalesUseCase

**Files:**
- Create: `tests/test_update_realtime_sales.py`
- Create: `src/usecases/update_realtime_sales.py`

- [ ] **Step 1: テストを書く**

```python
# tests/test_update_realtime_sales.py
from unittest.mock import Mock
from src.usecases.update_realtime_sales import UpdateRealtimeSalesUseCase
from src.domain.entities.order import Order, OrderItem
from src.domain.value_objects.realtime_sales_result import RealtimeSalesResult


class TestUpdateRealtimeSalesUseCase:
    def test_aggregates_by_asin(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE", "B00EXAMPLF"]
        mock_repo = Mock()
        mock_repo.get_orders_with_items.return_value = [
            Order(
                order_id="503-001",
                order_status="Shipped",
                items=[
                    OrderItem(asin="B00EXAMPLE", quantity_ordered=2, item_price_amount=3000.0),
                    OrderItem(asin="B00EXAMPLF", quantity_ordered=1, item_price_amount=1500.0),
                ],
            ),
        ]

        usecase = UpdateRealtimeSalesUseCase(sheet=mock_sheet, repository=mock_repo)
        usecase.execute()

        mock_sheet.write_realtime_sales.assert_called_once()
        sales_map = mock_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 2
        assert sales_map["B00EXAMPLE"].total_amount == 3000.0
        assert sales_map["B00EXAMPLF"].unit_count == 1

    def test_excludes_canceled_orders(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_repo = Mock()
        mock_repo.get_orders_with_items.return_value = [
            Order(
                order_id="503-001",
                order_status="Canceled",
                items=[OrderItem(asin="B00EXAMPLE", quantity_ordered=2, item_price_amount=3000.0)],
            ),
        ]

        usecase = UpdateRealtimeSalesUseCase(sheet=mock_sheet, repository=mock_repo)
        usecase.execute()

        sales_map = mock_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 0

    def test_skips_write_on_api_failure(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_repo = Mock()
        mock_repo.get_orders_with_items.side_effect = Exception("API error")

        usecase = UpdateRealtimeSalesUseCase(sheet=mock_sheet, repository=mock_repo)
        usecase.execute()

        mock_sheet.write_realtime_sales.assert_not_called()

    def test_handles_zero_orders(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_repo = Mock()
        mock_repo.get_orders_with_items.return_value = []

        usecase = UpdateRealtimeSalesUseCase(sheet=mock_sheet, repository=mock_repo)
        usecase.execute()

        sales_map = mock_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 0
```

- [ ] **Step 2: テスト実行、失敗を確認**

```bash
pytest tests/test_update_realtime_sales.py -v
```

- [ ] **Step 3: 実装**

```python
# src/usecases/update_realtime_sales.py
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from src.domain.entities.order import Order
from src.domain.value_objects.realtime_sales_result import RealtimeSalesResult
from src.infrastructure.api.orders_repository import OrdersRepository
from src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet

JST = timezone(timedelta(hours=9))


class UpdateRealtimeSalesUseCase:
    def __init__(self, sheet: RealtimeSalesSheet, repository: OrdersRepository) -> None:
        self._sheet = sheet
        self._repository = repository

    def execute(self) -> None:
        asin_list = self._sheet.get_asin_list()
        created_after = self._get_today_start()

        try:
            orders = self._repository.get_orders_with_items(created_after=created_after)
        except Exception:
            return

        sales_map = self._aggregate_by_asin(orders, asin_list)
        self._sheet.write_realtime_sales(sales_map)

    def _get_today_start(self) -> str:
        now = datetime.now(JST)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return today_start.isoformat()

    def _aggregate_by_asin(
        self, orders: list[Order], asin_list: list[str]
    ) -> dict[str, RealtimeSalesResult]:
        sales_map: dict[str, RealtimeSalesResult] = {
            asin: RealtimeSalesResult(asin=asin) for asin in asin_list
        }
        active_orders = [o for o in orders if not o.is_canceled]
        for order in active_orders:
            for item in order.items:
                if item.asin in sales_map:
                    sales_map[item.asin].add_sale(item.quantity_ordered, item.item_price_amount)
        return sales_map
```

- [ ] **Step 4: テスト実行、パスを確認**

```bash
pytest tests/test_update_realtime_sales.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: コミット**

```bash
git add src/usecases/update_realtime_sales.py tests/test_update_realtime_sales.py
git commit -m "feat: UpdateRealtimeSalesUseCase を追加"
```

---

### Task 7: エントリポイント + 動作確認

**Files:**
- Create: `main.py`

- [ ] **Step 1: main.py を作成**

```python
# main.py
import os
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from sp_api.api import Orders
from sp_api.base import Marketplaces
from src.infrastructure.api.orders_repository import OrdersRepository
from src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet
from src.usecases.update_realtime_sales import UpdateRealtimeSalesUseCase


def main() -> None:
    load_dotenv()

    orders_client = Orders(
        credentials=_build_sp_api_credentials(),
        marketplace=Marketplaces.JP,
    )
    repository = OrdersRepository(orders_client=orders_client)

    worksheet = _open_worksheet()
    sheet = RealtimeSalesSheet(worksheet=worksheet)

    usecase = UpdateRealtimeSalesUseCase(sheet=sheet, repository=repository)
    usecase.execute()


def _build_sp_api_credentials() -> dict:
    return {
        "refresh_token": os.getenv("SP_API_REFRESH_TOKEN"),
        "lwa_app_id": os.getenv("LWA_APP_ID"),
        "lwa_client_secret": os.getenv("LWA_CLIENT_SECRET"),
        "aws_access_key": os.getenv("SP_API_ACCESS_KEY"),
        "aws_secret_key": os.getenv("SP_API_SECRET_KEY"),
        "role_arn": os.getenv("SP_API_ROLE_ARN"),
    }


def _open_worksheet() -> gspread.Worksheet:
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    sheet_name = os.getenv("SHEET_NAME", "売上/今")

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(spreadsheet_id)
    return spreadsheet.worksheet(sheet_name)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: .env を作成（実際の認証情報を設定）**

既存のGASプロジェクトの `.env` からSP-API認証情報をコピーし、Google Sheets用の認証情報を追加する。

- [ ] **Step 3: 全テスト実行**

```bash
pytest -v
```
Expected: 全15テスト PASS

- [ ] **Step 4: 手動で動作確認**

```bash
python main.py
```

スプレッドシート「売上/今」のB列・C列が更新されることを確認。

- [ ] **Step 5: コミット**

```bash
git add main.py
git commit -m "feat: エントリポイント main.py を追加"
```
