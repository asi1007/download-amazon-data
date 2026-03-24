# 昨日の売上ダウンロード - 売上合計金額3行目記載 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** JS版とPython版の両方で、昨日の売上ダウンロード時に売上合計金額をシートの3行目に記載する

**Architecture:** JS版は既存の `SalesSheet.writeSalesNums` に合計金額書き込みを追加。Python版はDDDに基づき、SalesRepository（orderMetrics API）、PriceRepository（pricing API）、SalesSheet、UpdateDailySalesUseCase を新規作成。認証・リトライロジックは `SpApiAuthenticator` に共通化。

**Tech Stack:** JavaScript (Google Apps Script), Jest, Python 3.12+, pytest, requests, gspread

**Spec:** `docs/superpowers/specs/2026-03-24-daily-sales-total-amount-design.md`

---

### Task 1: JS版 - SalesSheet.writeSalesNums に売上合計金額を追加

**Files:**
- Modify: `src/infrastructure/sheets/SalesSheet.js:30-61`
- Test: `tests/getSPAPIdata.test.js`

- [ ] **Step 1: Jestテストを追加**

`tests/getSPAPIdata.test.js` の末尾に以下のテストを追加:

```javascript
describe('SalesSheet', () => {
  let salesSheet;
  let mockSetValue;
  let mockSheet;

  beforeEach(() => {
    mockSetValue = jest.fn();
    mockSheet = {
      getLastRow: jest.fn().mockReturnValue(7),
      getRange: jest.fn().mockReturnValue({
        getValues: jest.fn().mockReturnValue([
          ['header'],
          ['B00EXAMPLE'],
          ['B00EXAMPLF'],
          ['B00EXAMPLG'],
          ['header2'],
          ['B00EXAMPLH'],
          ['B00EXAMPLI'],
        ]),
        getValue: jest.fn(),
        setValue: mockSetValue,
        setValues: jest.fn(),
        setNumberFormat: jest.fn(),
      }),
      insertColumnBefore: jest.fn(),
      getFilter: jest.fn().mockReturnValue(null),
    };

    global.getSheetByName = jest.fn().mockImplementation((name) => {
      if (name === '設定') {
        return {
          getRange: jest.fn().mockImplementation((cell) => {
            if (cell === 'B2') return { getValue: jest.fn().mockReturnValue(3) };
            if (cell === 'B5') return { getValue: jest.fn().mockReturnValue(2) };
            return { getValue: jest.fn().mockReturnValue('') };
          }),
        };
      }
      return mockSheet;
    });

    global.Utilities = {
      formatDate: jest.fn().mockReturnValue('2026/03/24'),
    };

    salesSheet = new SalesSheet('売上/日', 'B2');
    salesSheet.asinList = ['B00EXAMPLE', 'B00EXAMPLF', 'B00EXAMPLG', 'B00EXAMPLH', 'B00EXAMPLI'];
    salesSheet.asinToRow = {
      'B00EXAMPLE': 2,
      'B00EXAMPLF': 3,
      'B00EXAMPLG': 4,
      'B00EXAMPLH': 6,
      'B00EXAMPLI': 7,
    };
  });

  test('writeSalesNums writes total sales amount to row 3', () => {
    const salesNums = {
      'B00EXAMPLE': { unitCount: 2, totalSales: { amount: 6000 }, orderCount: 1 },
      'B00EXAMPLF': { unitCount: 1, totalSales: { amount: 3000 }, orderCount: 1 },
      'B00EXAMPLG': { unitCount: 0, totalSales: { amount: 0 }, orderCount: 0 },
      'B00EXAMPLH': { unitCount: 3, totalSales: { amount: 4500 }, orderCount: 2 },
      'B00EXAMPLI': { unitCount: 0, totalSales: { amount: 0 }, orderCount: 0 },
    };

    salesSheet.writeSalesNums(salesNums);

    const row3Calls = mockSheet.getRange.mock.calls.filter(
      call => call[0] === 3 && call[1] === 3
    );
    expect(row3Calls.length).toBeGreaterThan(0);
    expect(mockSetValue).toHaveBeenCalledWith(13500);
  });
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `npm test`
Expected: FAIL

- [ ] **Step 3: writeSalesNums に合計金額書き込みを実装**

`src/infrastructure/sheets/SalesSheet.js` の `writeSalesNums` メソッドを修正。ループ内で `totalAmount` を合算し、ループ後に Row 3 へ書き込む:

```javascript
  writeSalesNums(salesNums) {
    this._refreshSheet();
    const filter = this.sheet.getFilter();
    let filterRange = null;
    if (filter) {
      filterRange = filter.getRange();
      filter.remove();
    }

    const HEADER_ROW = 4;
    const date = Utilities.formatDate(new Date(), "JST", "yyyy/MM/dd");
    this.sheet.insertColumnBefore(this.START_COLUMN);
    this.sheet.getRange(1, this.START_COLUMN).setValue(date);
    this.sheet.getRange(1, this.START_COLUMN).setNumberFormat("dd");
    this.sheet.getRange(HEADER_ROW, this.START_COLUMN).setValue(date);
    this.sheet.getRange(HEADER_ROW, this.START_COLUMN).setNumberFormat("dd");

    const values = this.asinRange.getValues();
    const writeData = [];
    let totalAmount = 0;

    for (let i = 2; i < values.length; i++) {
      const asin = values[i - 1][0];
      if (this.asinList.includes(asin)) {
        writeData.push([salesNums[asin].unitCount]);
        totalAmount += salesNums[asin].totalSales.amount;
      } else {
        writeData.push([""]);
      }
    }

    this.sheet.getRange(3, this.START_COLUMN).setValue(totalAmount);

    if (writeData.length > 0) {
      this.sheet.getRange(2, this.START_COLUMN, writeData.length, 1).setValues(writeData);
    }

    if (filterRange) {
      this.sheet.getRange(
        filterRange.getRow(),
        filterRange.getColumn(),
        filterRange.getNumRows(),
        filterRange.getNumColumns() + 1
      ).createFilter();
    }
  }
```

- [ ] **Step 4: テストが通ることを確認**

Run: `npm test`
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add src/infrastructure/sheets/SalesSheet.js tests/getSPAPIdata.test.js
git commit -m "feat: SalesSheet.writeSalesNums で売上合計金額を Row 3 に書き込み"
```

---

### Task 2: Python - SalesInfo Value Object を作成

**Files:**
- Create: `py_src/domain/value_objects/sales_info.py`
- Create: `py_tests/test_sales_info.py`

- [ ] **Step 1: テストを作成**

```python
import pytest
from py_src.domain.value_objects.sales_info import SalesInfo


class TestSalesInfo:
    def test_creation(self) -> None:
        info = SalesInfo(unit_count=5, total_sales_amount=15000.0, order_count=3)
        assert info.unit_count == 5
        assert info.total_sales_amount == 15000.0
        assert info.order_count == 3

    def test_immutable(self) -> None:
        info = SalesInfo(unit_count=5, total_sales_amount=15000.0, order_count=3)
        with pytest.raises(AttributeError):
            info.unit_count = 10

    def test_default_values(self) -> None:
        info = SalesInfo()
        assert info.unit_count == 0
        assert info.total_sales_amount == 0.0
        assert info.order_count == 0
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest py_tests/test_sales_info.py -v`
Expected: FAIL（`ImportError`）

- [ ] **Step 3: SalesInfo を実装**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SalesInfo:
    unit_count: int = 0
    total_sales_amount: float = 0.0
    order_count: int = 0
```

- [ ] **Step 4: テストが通ることを確認**

Run: `pytest py_tests/test_sales_info.py -v`
Expected: 3 passed

- [ ] **Step 5: コミット**

```bash
git add py_src/domain/value_objects/sales_info.py py_tests/test_sales_info.py
git commit -m "feat: SalesInfo value object を追加"
```

---

### Task 3: Python - Repository Protocol を domain 層に作成

**Files:**
- Create: `py_src/domain/repositories/__init__.py`
- Create: `py_src/domain/repositories/sales_repository.py`
- Create: `py_src/domain/repositories/price_repository.py`

- [ ] **Step 1: __init__.py を作成**

```python
```

- [ ] **Step 2: SalesRepository Protocol を作成**

```python
from __future__ import annotations
from typing import Protocol
from py_src.domain.value_objects.sales_info import SalesInfo


class SalesRepository(Protocol):
    def get_daily_sales(
        self, asin_list: list[str], start_date: str, end_date: str
    ) -> dict[str, SalesInfo]: ...
```

- [ ] **Step 3: PriceRepository Protocol を作成**

```python
from __future__ import annotations
from typing import Protocol


class PriceRepository(Protocol):
    def get_competitive_prices(self, asins: list[str]) -> dict[str, float]: ...
```

- [ ] **Step 4: コミット**

```bash
git add py_src/domain/repositories/
git commit -m "feat: SalesRepository, PriceRepository Protocol を追加"
```

---

### Task 4: Python - SpApiAuthenticator を作成（共通リクエストメソッド付き）

**Files:**
- Create: `py_src/infrastructure/api/sp_api_authenticator.py`
- Create: `py_tests/test_sp_api_authenticator.py`

- [ ] **Step 1: テストを作成**

```python
import pytest
from unittest.mock import Mock, patch
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator


def _make_response(json_data: dict, status_code: int = 200) -> Mock:
    resp = Mock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = Mock()
    return resp


class TestSpApiAuthenticator:
    def test_authenticate(self) -> None:
        session = Mock()
        session.post.return_value = _make_response({"access_token": "test_token"})
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )

        auth.authenticate()

        assert auth.headers()["x-amz-access-token"] == "test_token"

    def test_headers_format(self) -> None:
        session = Mock()
        session.post.return_value = _make_response({"access_token": "abc"})
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()

        h = auth.headers()
        assert h["Accept"] == "application/json"
        assert h["Content-Type"] == "application/json"

    @patch("py_src.infrastructure.api.sp_api_authenticator.time.sleep")
    def test_request_success(self, mock_sleep: Mock) -> None:
        session = Mock()
        session.post.return_value = _make_response({"access_token": "token"})
        session.get.return_value = _make_response({"data": "ok"})
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()

        resp = auth.request("GET", "https://example.com/api")
        assert resp.json() == {"data": "ok"}

    @patch("py_src.infrastructure.api.sp_api_authenticator.time.sleep")
    def test_request_retries_on_429(self, mock_sleep: Mock) -> None:
        session = Mock()
        session.post.return_value = _make_response({"access_token": "token"})
        rate_limited = _make_response({}, status_code=429)
        success = _make_response({"data": "ok"})
        session.request.side_effect = [rate_limited, success]
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()

        resp = auth.request("GET", "https://example.com/api")
        assert resp.json() == {"data": "ok"}

    @patch("py_src.infrastructure.api.sp_api_authenticator.time.sleep")
    def test_request_reauthenticates_on_403(self, mock_sleep: Mock) -> None:
        session = Mock()
        auth_resp1 = _make_response({"access_token": "token1"})
        auth_resp2 = _make_response({"access_token": "token2"})
        session.post.side_effect = [auth_resp1, auth_resp2]
        forbidden = _make_response({}, status_code=403)
        success = _make_response({"data": "ok"})
        session.request.side_effect = [forbidden, success]
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )
        auth.authenticate()

        resp = auth.request("GET", "https://example.com/api")
        assert resp.json() == {"data": "ok"}
        assert session.post.call_count == 2

    def test_authenticate_failure_raises(self) -> None:
        session = Mock()
        resp = Mock()
        resp.raise_for_status.side_effect = Exception("401 Unauthorized")
        session.post.return_value = resp
        auth = SpApiAuthenticator(
            client_id="id", client_secret="secret", refresh_token="refresh", session=session,
        )

        with pytest.raises(Exception, match="401"):
            auth.authenticate()
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest py_tests/test_sp_api_authenticator.py -v`
Expected: FAIL（`ImportError`）

- [ ] **Step 3: SpApiAuthenticator を実装**

```python
from __future__ import annotations
import time
import requests

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
SP_API_BASE = "https://sellingpartnerapi-fe.amazon.com"


class SpApiAuthenticator:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        session: requests.Session | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._session = session or requests.Session()
        self._access_token: str | None = None

    def authenticate(self) -> None:
        response = self._session.post(LWA_TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        })
        response.raise_for_status()
        self._access_token = response.json()["access_token"]

    def headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-amz-access-token": self._access_token or "",
        }

    def request(self, method: str, url: str, max_retries: int = 5) -> requests.Response:
        for attempt in range(max_retries):
            time.sleep(2 if attempt == 0 else 10)
            response = self._session.request(method, url, headers=self.headers())
            if response.status_code == 429:
                continue
            if response.status_code == 403:
                self.authenticate()
                continue
            response.raise_for_status()
            return response
        response.raise_for_status()
        return response
```

- [ ] **Step 4: テストが通ることを確認**

Run: `pytest py_tests/test_sp_api_authenticator.py -v`
Expected: 6 passed

- [ ] **Step 5: コミット**

```bash
git add py_src/infrastructure/api/sp_api_authenticator.py py_tests/test_sp_api_authenticator.py
git commit -m "feat: SpApiAuthenticator を追加（共通リクエスト・リトライ機能付き）"
```

---

### Task 5: Python - OrdersRepository を SpApiAuthenticator に移行

**Files:**
- Modify: `py_src/infrastructure/api/orders_repository.py`
- Modify: `py_tests/test_orders_repository.py`

- [ ] **Step 1: テストを先に SpApiAuthenticator 対応に更新**

```python
from unittest.mock import Mock, patch
from py_src.infrastructure.api.orders_repository import OrdersRepository
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator


def _make_response(json_data: dict, status_code: int = 200) -> Mock:
    resp = Mock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = Mock()
    return resp


class TestOrdersRepository:
    def _create_repo(self, mock_session: Mock) -> OrdersRepository:
        mock_session.post.return_value = _make_response({"access_token": "test_access_token"})
        auth = SpApiAuthenticator(
            client_id="test_id",
            client_secret="test_secret",
            refresh_token="test_token",
            session=mock_session,
        )
        return OrdersRepository(authenticator=auth)

    @patch("py_src.infrastructure.api.orders_repository.time.sleep")
    def test_get_orders_with_items(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        orders_response = _make_response({
            "payload": {
                "Orders": [
                    {"AmazonOrderId": "503-001", "OrderStatus": "Shipped", "PurchaseDate": "2026-03-15T10:00:00Z"},
                ],
            },
        })
        items_response = _make_response({
            "payload": {
                "OrderItems": [
                    {"ASIN": "B00EXAMPLE", "QuantityOrdered": 2, "ItemPrice": {"CurrencyCode": "JPY", "Amount": "3000"}},
                ],
            },
        })
        mock_session.get.side_effect = [orders_response, items_response]

        repo = self._create_repo(mock_session)
        orders = repo.get_orders_with_items(created_after="2026-03-15T00:00:00Z")

        assert len(orders) == 1
        assert orders[0].order_id == "503-001"
        assert orders[0].items[0].asin == "B00EXAMPLE"

    @patch("py_src.infrastructure.api.orders_repository.time.sleep")
    def test_get_orders_with_items_empty(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        orders_response = _make_response({"payload": {"Orders": []}})
        mock_session.get.return_value = orders_response

        repo = self._create_repo(mock_session)
        orders = repo.get_orders_with_items(created_after="2026-03-15T00:00:00Z")

        assert len(orders) == 0

    @patch("py_src.infrastructure.api.orders_repository.time.sleep")
    def test_get_orders_with_items_pagination(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        page1_response = _make_response({
            "payload": {
                "Orders": [
                    {"AmazonOrderId": "503-001", "OrderStatus": "Shipped", "PurchaseDate": "2026-03-15T10:00:00Z"},
                ],
                "NextToken": "token123",
            },
        })
        page2_response = _make_response({
            "payload": {
                "Orders": [
                    {"AmazonOrderId": "503-002", "OrderStatus": "Shipped", "PurchaseDate": "2026-03-15T11:00:00Z"},
                ],
            },
        })
        items_response = _make_response({
            "payload": {
                "OrderItems": [
                    {"ASIN": "B00EXAMPLE", "QuantityOrdered": 1, "ItemPrice": {"CurrencyCode": "JPY", "Amount": "1000"}},
                ],
            },
        })
        mock_session.get.side_effect = [page1_response, page2_response, items_response, items_response]

        repo = self._create_repo(mock_session)
        orders = repo.get_orders_with_items(created_after="2026-03-15T00:00:00Z")

        assert len(orders) == 2
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest py_tests/test_orders_repository.py -v`
Expected: FAIL（`OrdersRepository` がまだ旧インターフェース）

- [ ] **Step 3: OrdersRepository をリファクタリング**

```python
from __future__ import annotations
import time
from urllib.parse import quote
from py_src.domain.entities.order import Order
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator, SP_API_BASE

MARKETPLACE_JP = "A1VC38T7YXB528"


class OrdersRepository:
    def __init__(self, authenticator: SpApiAuthenticator) -> None:
        self._auth = authenticator

    def get_orders_with_items(self, created_after: str) -> list[Order]:
        self._auth.authenticate()
        raw_orders = self._fetch_all_orders(created_after)
        if not raw_orders:
            return []
        return [self._build_order(raw) for raw in raw_orders]

    def _fetch_all_orders(self, created_after: str) -> list[dict]:
        all_orders: list[dict] = []
        url = (
            f"{SP_API_BASE}/orders/v0/orders"
            f"?CreatedAfter={created_after}"
            f"&MarketplaceIds={MARKETPLACE_JP}"
        )

        while True:
            time.sleep(2)
            response = self._auth._session.get(url, headers=self._auth.headers())
            if response.status_code == 403:
                self._auth.authenticate()
                continue
            response.raise_for_status()
            payload = response.json().get("payload", {})
            all_orders.extend(payload.get("Orders", []))

            next_token = payload.get("NextToken")
            if not next_token:
                break
            url = (
                f"{SP_API_BASE}/orders/v0/orders"
                f"?CreatedAfter={created_after}"
                f"&MarketplaceIds={MARKETPLACE_JP}"
                f"&NextToken={quote(next_token)}"
            )

        return all_orders

    def _build_order(self, raw_order: dict) -> Order:
        order_id = raw_order["AmazonOrderId"]
        url = f"{SP_API_BASE}/orders/v0/orders/{order_id}/orderItems?marketplaceIds={MARKETPLACE_JP}"

        for attempt in range(5):
            time.sleep(3 if attempt == 0 else 15)
            response = self._auth._session.get(url, headers=self._auth.headers())
            if response.status_code == 429:
                continue
            if response.status_code == 403:
                self._auth.authenticate()
                continue
            response.raise_for_status()
            items_data = response.json().get("payload", {}).get("OrderItems", [])
            return Order.from_api_response(raw_order, items_data)

        response.raise_for_status()
        return Order.from_api_response(raw_order, [])
```

- [ ] **Step 4: テストが通ることを確認**

Run: `pytest py_tests/test_orders_repository.py -v`
Expected: 3 passed

- [ ] **Step 5: コミット**

```bash
git add py_src/infrastructure/api/orders_repository.py py_tests/test_orders_repository.py
git commit -m "refactor: OrdersRepository を SpApiAuthenticator に移行"
```

---

### Task 6: Python - UpdateRealtimeSalesUseCase を PriceRepository 対応に更新

**Files:**
- Modify: `py_src/usecases/update_realtime_sales.py`
- Modify: `py_tests/test_update_realtime_sales.py`
- Modify: `main.py`

- [ ] **Step 1: テストを PriceRepository 対応に更新**

`py_tests/test_update_realtime_sales.py` で `mock_repo.get_prices` を `mock_price_repo.get_competitive_prices` に変更:

```python
import pytest
from unittest.mock import Mock
from py_src.usecases.update_realtime_sales import UpdateRealtimeSalesUseCase
from py_src.domain.entities.order import Order, OrderItem


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
        mock_price_repo = Mock()
        mock_price_repo.get_competitive_prices.return_value = {}

        usecase = UpdateRealtimeSalesUseCase(sheet=mock_sheet, repository=mock_repo, price_repository=mock_price_repo)
        usecase.execute()

        sales_map = mock_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 2
        assert sales_map["B00EXAMPLE"].total_amount == 6000.0

    def test_excludes_canceled_orders(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_repo = Mock()
        mock_repo.get_orders_with_items.return_value = [
            Order(order_id="503-001", order_status="Canceled",
                  items=[OrderItem(asin="B00EXAMPLE", quantity_ordered=2, item_price_amount=3000.0)]),
        ]
        mock_price_repo = Mock()
        mock_price_repo.get_competitive_prices.return_value = {}

        usecase = UpdateRealtimeSalesUseCase(sheet=mock_sheet, repository=mock_repo, price_repository=mock_price_repo)
        usecase.execute()

        sales_map = mock_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 0

    def test_uses_current_price_for_zero_items(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_repo = Mock()
        mock_repo.get_orders_with_items.return_value = [
            Order(order_id="503-001", order_status="Pending",
                  items=[OrderItem(asin="B00EXAMPLE", quantity_ordered=3, item_price_amount=0.0)]),
        ]
        mock_price_repo = Mock()
        mock_price_repo.get_competitive_prices.return_value = {"B00EXAMPLE": 1500.0}

        usecase = UpdateRealtimeSalesUseCase(sheet=mock_sheet, repository=mock_repo, price_repository=mock_price_repo)
        usecase.execute()

        sales_map = mock_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].total_amount == 4500.0

    def test_raises_on_api_failure(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_repo = Mock()
        mock_repo.get_orders_with_items.side_effect = Exception("API error")

        usecase = UpdateRealtimeSalesUseCase(sheet=mock_sheet, repository=mock_repo)

        with pytest.raises(Exception, match="API error"):
            usecase.execute()

    def test_handles_zero_orders(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE"]
        mock_repo = Mock()
        mock_repo.get_orders_with_items.return_value = []
        mock_price_repo = Mock()
        mock_price_repo.get_competitive_prices.return_value = {}

        usecase = UpdateRealtimeSalesUseCase(sheet=mock_sheet, repository=mock_repo, price_repository=mock_price_repo)
        usecase.execute()

        sales_map = mock_sheet.write_realtime_sales.call_args[0][0]
        assert sales_map["B00EXAMPLE"].unit_count == 0
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest py_tests/test_update_realtime_sales.py -v`
Expected: FAIL（`price_repository` パラメータがまだないため）

- [ ] **Step 3: UpdateRealtimeSalesUseCase を更新**

`py_src/usecases/update_realtime_sales.py` を修正。`price_repository` を追加し、`self._repository.get_prices()` を置き換え:

```python
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from py_src.domain.entities.order import Order
from py_src.domain.value_objects.realtime_sales_result import RealtimeSalesResult
from py_src.domain.repositories.price_repository import PriceRepository
from py_src.infrastructure.api.orders_repository import OrdersRepository
from py_src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet

JST = timezone(timedelta(hours=9))


class UpdateRealtimeSalesUseCase:
    def __init__(
        self,
        sheet: RealtimeSalesSheet,
        repository: OrdersRepository,
        price_repository: PriceRepository | None = None,
    ) -> None:
        self._sheet = sheet
        self._repository = repository
        self._price_repository = price_repository

    def execute(self) -> None:
        asin_list = self._sheet.get_asin_list()
        created_after = self._get_today_start()
        orders = self._repository.get_orders_with_items(created_after=created_after)
        current_prices = self._fetch_prices_for_zero_items(orders, asin_list)
        sales_map = self._aggregate_by_asin(orders, asin_list, current_prices)
        self._sheet.write_realtime_sales(sales_map)

    def _get_today_start(self) -> str:
        now = datetime.now(JST)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        utc_start = today_start.astimezone(timezone.utc)
        return utc_start.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _fetch_prices_for_zero_items(
        self, orders: list[Order], asin_list: list[str]
    ) -> dict[str, float]:
        asin_set = set(asin_list)
        zero_price_asins: set[str] = set()
        for order in orders:
            if order.is_canceled:
                continue
            for item in order.items:
                if item.asin in asin_set and item.item_price_amount == 0.0:
                    zero_price_asins.add(item.asin)
        if not zero_price_asins or self._price_repository is None:
            return {}
        return self._price_repository.get_competitive_prices(list(zero_price_asins))

    def _aggregate_by_asin(
        self, orders: list[Order], asin_list: list[str], current_prices: dict[str, float]
    ) -> dict[str, RealtimeSalesResult]:
        sales_map: dict[str, RealtimeSalesResult] = {
            asin: RealtimeSalesResult(asin=asin) for asin in asin_list
        }
        active_orders = [o for o in orders if not o.is_canceled]
        for order in active_orders:
            for item in order.items:
                if item.asin in sales_map:
                    unit_price = item.item_price_amount
                    if unit_price == 0.0:
                        unit_price = current_prices.get(item.asin, 0.0)
                    sales_map[item.asin].add_sale(item.quantity_ordered, unit_price)
        return sales_map
```

- [ ] **Step 4: main.py を SpApiAuthenticator 対応に更新**

```python
import os

from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
import gspread

from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator
from py_src.infrastructure.api.orders_repository import OrdersRepository
from py_src.infrastructure.sheets.realtime_sales_sheet import RealtimeSalesSheet
from py_src.usecases.update_realtime_sales import UpdateRealtimeSalesUseCase


def main() -> None:
    load_dotenv()

    authenticator = _create_authenticator()
    repository = OrdersRepository(authenticator=authenticator)

    spreadsheet = _open_spreadsheet()
    sheet_name = os.getenv("SHEET_NAME", "売上/今")
    worksheet = spreadsheet.worksheet(sheet_name)
    sheet = RealtimeSalesSheet(worksheet=worksheet)

    usecase = UpdateRealtimeSalesUseCase(sheet=sheet, repository=repository)
    usecase.execute()


def _create_authenticator() -> SpApiAuthenticator:
    return SpApiAuthenticator(
        client_id=os.getenv("API_KEY", ""),
        client_secret=os.getenv("API_SECRET", ""),
        refresh_token=os.getenv("REFRESH_TOKEN", ""),
    )


def _open_spreadsheet() -> gspread.Spreadsheet:
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    client = gspread.authorize(creds)
    return client.open_by_key(spreadsheet_id)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 全テストが通ることを確認**

Run: `pytest py_tests/ -v`
Expected: ALL PASSED

- [ ] **Step 6: コミット**

```bash
git add py_src/usecases/update_realtime_sales.py py_tests/test_update_realtime_sales.py main.py
git commit -m "refactor: UpdateRealtimeSalesUseCase を PriceRepository 対応に更新、get_prices 削除"
```

---

### Task 7: Python - SpApiPriceRepository を作成

**Files:**
- Create: `py_src/infrastructure/api/sp_api_price_repository.py`
- Create: `py_tests/test_sp_api_price_repository.py`

- [ ] **Step 1: テストを作成**

```python
from unittest.mock import Mock, patch
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator
from py_src.infrastructure.api.sp_api_price_repository import SpApiPriceRepository


def _make_response(json_data: dict, status_code: int = 200) -> Mock:
    resp = Mock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = Mock()
    return resp


def _create_auth(mock_session: Mock) -> SpApiAuthenticator:
    mock_session.post.return_value = _make_response({"access_token": "token"})
    return SpApiAuthenticator(
        client_id="id", client_secret="secret", refresh_token="refresh", session=mock_session,
    )


class TestSpApiPriceRepository:
    @patch("py_src.infrastructure.api.sp_api_price_repository.time.sleep")
    def test_get_competitive_prices(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        auth = _create_auth(mock_session)
        auth.authenticate()
        mock_session.request.return_value = _make_response({
            "payload": [{
                "ASIN": "B00EXAMPLE", "status": "Success",
                "Product": {"Offers": [{"BuyingPrice": {"ListingPrice": {"Amount": 3000.0}}}]},
            }],
        })

        repo = SpApiPriceRepository(authenticator=auth)
        prices = repo.get_competitive_prices(["B00EXAMPLE"])

        assert prices == {"B00EXAMPLE": 3000.0}

    @patch("py_src.infrastructure.api.sp_api_price_repository.time.sleep")
    def test_skips_failed_asin(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        auth = _create_auth(mock_session)
        auth.authenticate()
        mock_session.request.return_value = _make_response({
            "payload": [{"ASIN": "B00EXAMPLE", "status": "ClientError"}],
        })

        repo = SpApiPriceRepository(authenticator=auth)
        prices = repo.get_competitive_prices(["B00EXAMPLE"])

        assert prices == {}

    @patch("py_src.infrastructure.api.sp_api_price_repository.time.sleep")
    def test_batches_over_20_asins(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        auth = _create_auth(mock_session)
        auth.authenticate()
        asins = [f"B00EXAMPL{i:02d}" for i in range(25)]
        batch1 = [{"ASIN": a, "status": "Success", "Product": {"Offers": [{"BuyingPrice": {"ListingPrice": {"Amount": 1000.0}}}]}} for a in asins[:20]]
        batch2 = [{"ASIN": a, "status": "Success", "Product": {"Offers": [{"BuyingPrice": {"ListingPrice": {"Amount": 2000.0}}}]}} for a in asins[20:]]
        mock_session.request.side_effect = [
            _make_response({"payload": batch1}),
            _make_response({"payload": batch2}),
        ]

        repo = SpApiPriceRepository(authenticator=auth)
        prices = repo.get_competitive_prices(asins)

        assert len(prices) == 25
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest py_tests/test_sp_api_price_repository.py -v`
Expected: FAIL（`ImportError`）

- [ ] **Step 3: SpApiPriceRepository を実装**

```python
from __future__ import annotations
import time
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator, SP_API_BASE

MARKETPLACE_JP = "A1VC38T7YXB528"


class SpApiPriceRepository:
    def __init__(self, authenticator: SpApiAuthenticator) -> None:
        self._auth = authenticator

    def get_competitive_prices(self, asins: list[str]) -> dict[str, float]:
        prices: dict[str, float] = {}
        for i in range(0, len(asins), 20):
            if i > 0:
                time.sleep(3)
            batch = asins[i:i + 20]
            url = (
                f"{SP_API_BASE}/products/pricing/v0/price"
                f"?MarketplaceId={MARKETPLACE_JP}"
                f"&ItemType=Asin"
                f"&Asins={','.join(batch)}"
            )
            response = self._auth.request("GET", url)
            batch_prices = self._parse_prices(response.json().get("payload", []))
            prices.update(batch_prices)
        return prices

    @staticmethod
    def _parse_prices(payload: list[dict]) -> dict[str, float]:
        prices: dict[str, float] = {}
        for item in payload:
            if item.get("status") != "Success":
                continue
            asin = item.get("ASIN", "")
            offers = item.get("Product", {}).get("Offers", [])
            if offers:
                listing_price = offers[0].get("BuyingPrice", {}).get("ListingPrice", {})
                amount = float(listing_price.get("Amount", 0))
                if amount > 0:
                    prices[asin] = amount
        return prices
```

- [ ] **Step 4: テストが通ることを確認**

Run: `pytest py_tests/test_sp_api_price_repository.py -v`
Expected: 3 passed

- [ ] **Step 5: コミット**

```bash
git add py_src/infrastructure/api/sp_api_price_repository.py py_tests/test_sp_api_price_repository.py
git commit -m "feat: SpApiPriceRepository を追加"
```

---

### Task 8: Python - SpApiSalesRepository を作成

**Files:**
- Create: `py_src/infrastructure/api/sp_api_sales_repository.py`
- Create: `py_tests/test_sp_api_sales_repository.py`

- [ ] **Step 1: テストを作成**

```python
from unittest.mock import Mock, patch
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator
from py_src.infrastructure.api.sp_api_sales_repository import SpApiSalesRepository


def _make_response(json_data: dict, status_code: int = 200) -> Mock:
    resp = Mock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = Mock()
    return resp


def _create_auth(mock_session: Mock) -> SpApiAuthenticator:
    mock_session.post.return_value = _make_response({"access_token": "token"})
    return SpApiAuthenticator(
        client_id="id", client_secret="secret", refresh_token="refresh", session=mock_session,
    )


class TestSpApiSalesRepository:
    @patch("py_src.infrastructure.api.sp_api_sales_repository.time.sleep")
    def test_get_daily_sales_single_asin(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        auth = _create_auth(mock_session)
        auth.authenticate()
        mock_session.request.return_value = _make_response({
            "payload": [{"unitCount": 5, "totalSales": {"currencyCode": "JPY", "amount": 15000.0}, "orderCount": 3}],
        })

        repo = SpApiSalesRepository(authenticator=auth)
        result = repo.get_daily_sales(["B00EXAMPLE"], "2026-03-23T15:00:00Z", "2026-03-24T15:00:00Z")

        assert result["B00EXAMPLE"].unit_count == 5
        assert result["B00EXAMPLE"].total_sales_amount == 15000.0
        assert result["B00EXAMPLE"].order_count == 3

    @patch("py_src.infrastructure.api.sp_api_sales_repository.time.sleep")
    def test_get_daily_sales_empty_payload(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        auth = _create_auth(mock_session)
        auth.authenticate()
        mock_session.request.return_value = _make_response({"payload": []})

        repo = SpApiSalesRepository(authenticator=auth)
        result = repo.get_daily_sales(["B00EXAMPLE"], "2026-03-23T15:00:00Z", "2026-03-24T15:00:00Z")

        assert result["B00EXAMPLE"].unit_count == 0
        assert result["B00EXAMPLE"].total_sales_amount == 0.0

    @patch("py_src.infrastructure.api.sp_api_sales_repository.time.sleep")
    def test_get_daily_sales_multiple_asins(self, mock_sleep: Mock) -> None:
        mock_session = Mock()
        auth = _create_auth(mock_session)
        auth.authenticate()
        mock_session.request.side_effect = [
            _make_response({"payload": [{"unitCount": 2, "totalSales": {"amount": 6000.0}, "orderCount": 1}]}),
            _make_response({"payload": [{"unitCount": 1, "totalSales": {"amount": 3000.0}, "orderCount": 1}]}),
        ]

        repo = SpApiSalesRepository(authenticator=auth)
        result = repo.get_daily_sales(["B00EXAMPLE", "B00EXAMPLF"], "2026-03-23T15:00:00Z", "2026-03-24T15:00:00Z")

        assert result["B00EXAMPLE"].unit_count == 2
        assert result["B00EXAMPLF"].unit_count == 1
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest py_tests/test_sp_api_sales_repository.py -v`
Expected: FAIL（`ImportError`）

- [ ] **Step 3: SpApiSalesRepository を実装**

```python
from __future__ import annotations
import time
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator, SP_API_BASE

MARKETPLACE_JP = "A1VC38T7YXB528"


class SpApiSalesRepository:
    def __init__(self, authenticator: SpApiAuthenticator) -> None:
        self._auth = authenticator

    def get_daily_sales(
        self, asin_list: list[str], start_date: str, end_date: str
    ) -> dict[str, SalesInfo]:
        result: dict[str, SalesInfo] = {}
        for i, asin in enumerate(asin_list):
            if i > 0:
                time.sleep(4)
            result[asin] = self._fetch_sales(asin, start_date, end_date)
        return result

    def _fetch_sales(self, asin: str, start_date: str, end_date: str) -> SalesInfo:
        interval = f"{start_date}--{end_date}"
        url = (
            f"{SP_API_BASE}/sales/v1/orderMetrics"
            f"?marketplaceIds={MARKETPLACE_JP}"
            f"&interval={interval}"
            f"&granularity=Day"
            f"&granularityTimeZone=Asia/Tokyo"
            f"&asin={asin}"
        )
        response = self._auth.request("GET", url)
        return self._parse_sales(response.json())

    @staticmethod
    def _parse_sales(data: dict) -> SalesInfo:
        payload = data.get("payload", [])
        if not payload:
            return SalesInfo()
        entry = payload[0]
        return SalesInfo(
            unit_count=entry.get("unitCount", 0),
            total_sales_amount=float(entry.get("totalSales", {}).get("amount", 0)),
            order_count=entry.get("orderCount", 0),
        )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `pytest py_tests/test_sp_api_sales_repository.py -v`
Expected: 3 passed

- [ ] **Step 5: コミット**

```bash
git add py_src/infrastructure/api/sp_api_sales_repository.py py_tests/test_sp_api_sales_repository.py
git commit -m "feat: SpApiSalesRepository を追加"
```

---

### Task 9: Python - SalesSheet を作成

**Files:**
- Create: `py_src/infrastructure/sheets/sales_sheet.py`
- Create: `py_tests/test_sales_sheet.py`

- [ ] **Step 1: テストを作成**

```python
from unittest.mock import Mock, call
from gspread.utils import rowcol_to_a1
from py_src.infrastructure.sheets.sales_sheet import SalesSheet
from py_src.domain.value_objects.sales_info import SalesInfo


def _create_mock_worksheets() -> tuple[Mock, Mock]:
    settings_ws = Mock()
    settings_ws.acell.side_effect = lambda cell: Mock(value="3" if cell == "B2" else "2")

    sales_ws = Mock()
    sales_ws.col_values.return_value = [
        "header", "B00EXAMPLE", "B00EXAMPLF", "", "header2", "B00EXAMPLG",
    ]
    return sales_ws, settings_ws


class TestSalesSheet:
    def test_get_asin_list(self) -> None:
        sales_ws, settings_ws = _create_mock_worksheets()
        sheet = SalesSheet(sales_worksheet=sales_ws, settings_worksheet=settings_ws)

        asin_list = sheet.get_asin_list()

        assert asin_list == ["B00EXAMPLE", "B00EXAMPLF", "B00EXAMPLG"]

    def test_write_sales_nums_total_amount_to_row3(self) -> None:
        sales_ws, settings_ws = _create_mock_worksheets()
        sheet = SalesSheet(sales_worksheet=sales_ws, settings_worksheet=settings_ws)
        sheet.get_asin_list()

        asin_sales = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
            "B00EXAMPLF": SalesInfo(unit_count=1, total_sales_amount=3000.0, order_count=1),
            "B00EXAMPLG": SalesInfo(unit_count=3, total_sales_amount=4500.0, order_count=2),
        }
        sheet.write_sales_nums(asin_sales)

        sales_ws.insert_cols.assert_called_once_with(3)
        row3_range = rowcol_to_a1(3, 3)
        update_calls = sales_ws.update.call_args_list
        row3_call = [c for c in update_calls if c[0][0] == row3_range]
        assert len(row3_call) == 1
        assert row3_call[0][0][1] == [[13500.0]]

    def test_write_sales_nums_missing_asin_uses_default(self) -> None:
        sales_ws, settings_ws = _create_mock_worksheets()
        sheet = SalesSheet(sales_worksheet=sales_ws, settings_worksheet=settings_ws)
        sheet.get_asin_list()

        asin_sales = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
        }
        sheet.write_sales_nums(asin_sales)

        row3_range = rowcol_to_a1(3, 3)
        update_calls = sales_ws.update.call_args_list
        row3_call = [c for c in update_calls if c[0][0] == row3_range]
        assert row3_call[0][0][1] == [[6000.0]]

    def test_write_prices_updates_cells(self) -> None:
        sales_ws, settings_ws = _create_mock_worksheets()
        sales_ws.cell.return_value = Mock(value="2800")
        sheet = SalesSheet(sales_worksheet=sales_ws, settings_worksheet=settings_ws)
        sheet.get_asin_list()

        prices = {"B00EXAMPLE": 3000.0}
        sheet.write_prices(prices)

        sales_ws.update_cell.assert_called()
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest py_tests/test_sales_sheet.py -v`
Expected: FAIL（`ImportError`）

- [ ] **Step 3: SalesSheet を実装**

```python
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from gspread import Worksheet
from gspread.utils import rowcol_to_a1
from py_src.domain.value_objects.sales_info import SalesInfo

JST = timezone(timedelta(hours=9))
HEADER_ROW = 4


class SalesSheet:
    def __init__(self, sales_worksheet: Worksheet, settings_worksheet: Worksheet) -> None:
        self._worksheet = sales_worksheet
        self._settings = settings_worksheet
        self._asin_list: list[str] = []
        self._asin_to_row: dict[str, int] = {}
        self._start_column: int = 0
        self._price_column: int = 0

    def get_asin_list(self) -> list[str]:
        self._start_column = int(self._settings.acell("B2").value)
        self._price_column = int(self._settings.acell("B5").value)
        values = self._worksheet.col_values(1)
        self._asin_list = []
        self._asin_to_row = {}
        for i, v in enumerate(values):
            stripped = v.strip() if v else ""
            if len(stripped) == 10:
                self._asin_list.append(stripped)
                self._asin_to_row[stripped] = i + 1
        return self._asin_list

    def write_sales_nums(self, asin_sales: dict[str, SalesInfo]) -> None:
        col = self._start_column
        self._worksheet.insert_cols(col)

        date_str = datetime.now(JST).strftime("%d")
        self._worksheet.update(rowcol_to_a1(1, col), [[date_str]])
        self._worksheet.update(rowcol_to_a1(HEADER_ROW, col), [[date_str]])

        total_amount = 0.0
        for asin in self._asin_list:
            row = self._asin_to_row[asin]
            sales = asin_sales.get(asin, SalesInfo())
            self._worksheet.update(rowcol_to_a1(row, col), [[sales.unit_count]])
            total_amount += sales.total_sales_amount

        self._worksheet.update(rowcol_to_a1(3, col), [[total_amount]])

    def write_prices(self, prices: dict[str, float]) -> None:
        col = self._start_column
        for asin, price in prices.items():
            if asin not in self._asin_to_row:
                continue
            row = self._asin_to_row[asin]
            self._worksheet.update_cell(row, self._price_column, price)
            self._worksheet.update_note(rowcol_to_a1(row, col), str(price))
            prev_cell = self._worksheet.cell(row, col + 1)
            prev_price_str = prev_cell.value if prev_cell.value else ""
            if prev_price_str:
                prev_price = float(prev_price_str)
                if price < prev_price:
                    self._worksheet.format(rowcol_to_a1(row, col), {"backgroundColor": {"red": 1, "green": 0, "blue": 0}})
                elif price > prev_price:
                    self._worksheet.format(rowcol_to_a1(row, col), {"backgroundColor": {"red": 0, "green": 1, "blue": 1}})
```

- [ ] **Step 4: テストが通ることを確認**

Run: `pytest py_tests/test_sales_sheet.py -v`
Expected: 4 passed

- [ ] **Step 5: コミット**

```bash
git add py_src/infrastructure/sheets/sales_sheet.py py_tests/test_sales_sheet.py
git commit -m "feat: SalesSheet を追加（売上/日シートへの書き込み、Row 3 に合計金額）"
```

---

### Task 10: Python - UpdateDailySalesUseCase を作成

**Files:**
- Create: `py_src/usecases/update_daily_sales.py`
- Create: `py_tests/test_update_daily_sales.py`

- [ ] **Step 1: テストを作成**

```python
from unittest.mock import Mock
from py_src.usecases.update_daily_sales import UpdateDailySalesUseCase
from py_src.domain.value_objects.sales_info import SalesInfo


class TestUpdateDailySalesUseCase:
    def test_execute_writes_sales_and_prices(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = ["B00EXAMPLE", "B00EXAMPLF"]
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {
            "B00EXAMPLE": SalesInfo(unit_count=2, total_sales_amount=6000.0, order_count=1),
            "B00EXAMPLF": SalesInfo(unit_count=1, total_sales_amount=3000.0, order_count=1),
        }
        mock_price_repo = Mock()
        mock_price_repo.get_competitive_prices.return_value = {"B00EXAMPLE": 3200.0, "B00EXAMPLF": 1600.0}

        usecase = UpdateDailySalesUseCase(
            sales_sheet=mock_sheet, sales_repository=mock_sales_repo, price_repository=mock_price_repo,
        )
        usecase.execute()

        mock_sheet.get_asin_list.assert_called_once()
        mock_sales_repo.get_daily_sales.assert_called_once()
        mock_sheet.write_sales_nums.assert_called_once()
        mock_price_repo.get_competitive_prices.assert_called_once_with(["B00EXAMPLE", "B00EXAMPLF"])
        mock_sheet.write_prices.assert_called_once()

    def test_yesterday_date_range_is_valid(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {}
        mock_price_repo = Mock()
        mock_price_repo.get_competitive_prices.return_value = {}

        usecase = UpdateDailySalesUseCase(
            sales_sheet=mock_sheet, sales_repository=mock_sales_repo, price_repository=mock_price_repo,
        )
        usecase.execute()

        args = mock_sales_repo.get_daily_sales.call_args
        start_date = args[1].get("start_date", args[0][1] if len(args[0]) > 1 else None)
        end_date = args[1].get("end_date", args[0][2] if len(args[0]) > 2 else None)
        assert start_date.endswith("Z")
        assert end_date.endswith("Z")
        assert start_date < end_date

    def test_empty_asin_list(self) -> None:
        mock_sheet = Mock()
        mock_sheet.get_asin_list.return_value = []
        mock_sales_repo = Mock()
        mock_sales_repo.get_daily_sales.return_value = {}
        mock_price_repo = Mock()
        mock_price_repo.get_competitive_prices.return_value = {}

        usecase = UpdateDailySalesUseCase(
            sales_sheet=mock_sheet, sales_repository=mock_sales_repo, price_repository=mock_price_repo,
        )
        usecase.execute()

        mock_sheet.write_sales_nums.assert_called_once_with({})
        mock_price_repo.get_competitive_prices.assert_called_once_with([])
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `pytest py_tests/test_update_daily_sales.py -v`
Expected: FAIL（`ImportError`）

- [ ] **Step 3: UpdateDailySalesUseCase を実装**

```python
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from py_src.domain.repositories.sales_repository import SalesRepository
from py_src.domain.repositories.price_repository import PriceRepository
from py_src.domain.value_objects.sales_info import SalesInfo

JST = timezone(timedelta(hours=9))


class UpdateDailySalesUseCase:
    def __init__(
        self,
        sales_sheet: object,
        sales_repository: SalesRepository,
        price_repository: PriceRepository,
    ) -> None:
        self._sheet = sales_sheet
        self._sales_repo = sales_repository
        self._price_repo = price_repository

    def execute(self) -> None:
        asin_list = self._sheet.get_asin_list()
        start_date, end_date = self._get_yesterday_range()
        asin_sales = self._sales_repo.get_daily_sales(
            asin_list=asin_list, start_date=start_date, end_date=end_date,
        )
        self._sheet.write_sales_nums(asin_sales)
        prices = self._price_repo.get_competitive_prices(asin_list)
        self._sheet.write_prices(prices)

    @staticmethod
    def _get_yesterday_range() -> tuple[str, str]:
        now = datetime.now(JST)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        utc_start = yesterday_start.astimezone(timezone.utc)
        utc_end = today_start.astimezone(timezone.utc)
        return (
            utc_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            utc_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `pytest py_tests/test_update_daily_sales.py -v`
Expected: 3 passed

- [ ] **Step 5: コミット**

```bash
git add py_src/usecases/update_daily_sales.py py_tests/test_update_daily_sales.py
git commit -m "feat: UpdateDailySalesUseCase を追加"
```

---

### Task 11: Python - main.py にエントリポイント追加 + 全テスト確認 + バージョン更新

**Files:**
- Modify: `main.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: main.py に update_daily_sales 関数を追加**

以下の import を追加:

```python
from py_src.infrastructure.api.sp_api_sales_repository import SpApiSalesRepository
from py_src.infrastructure.api.sp_api_price_repository import SpApiPriceRepository
from py_src.infrastructure.sheets.sales_sheet import SalesSheet
from py_src.usecases.update_daily_sales import UpdateDailySalesUseCase
```

`update_daily_sales` 関数を追加:

```python
def update_daily_sales() -> None:
    load_dotenv()

    authenticator = _create_authenticator()
    sales_repository = SpApiSalesRepository(authenticator=authenticator)
    price_repository = SpApiPriceRepository(authenticator=authenticator)

    spreadsheet = _open_spreadsheet()
    sales_ws = spreadsheet.worksheet("売上/日")
    settings_ws = spreadsheet.worksheet("設定")
    sales_sheet = SalesSheet(sales_worksheet=sales_ws, settings_worksheet=settings_ws)

    usecase = UpdateDailySalesUseCase(
        sales_sheet=sales_sheet,
        sales_repository=sales_repository,
        price_repository=price_repository,
    )
    usecase.execute()
```

`if __name__` を更新:

```python
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "daily":
        update_daily_sales()
    else:
        main()
```

- [ ] **Step 2: pyproject.toml のバージョンを 0.3.0 に更新**

`version = "0.2.0"` → `version = "0.3.0"`

- [ ] **Step 3: 全テストが通ることを確認**

Run: `pytest py_tests/ -v && npm test`
Expected: ALL PASSED

- [ ] **Step 4: コミット**

```bash
git add main.py pyproject.toml
git commit -m "feat: 昨日の売上ダウンロード機能追加 v0.3.0"
```
