# 「売上/日」に広告経由の売上個数を並べる 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 「売上/日」の各 ASIN 行の直下に広告行を1本足し、Amazon Ads の広告経由売上個数を日付列に毎日書き込む。

**Architecture:** 既存の日次売上ジョブ（`main.py daily`）とは別のサブコマンド `main.py ads` を新設し、launchd で売上ジョブの1時間後に走らせる。広告ジョブは日付列を**作らず**、売上ジョブが作った列に書き足すだけにする。Amazon Ads API の非同期レポート（`spAdvertisedProduct` / DAILY）から `date × advertisedAsin × unitsSoldSameSku14d` を取得し、シート上の広告行へ `batch_update` 1回でまとめて書く。

**Tech Stack:** Python 3.12 / gspread 6.x / requests / pytest / launchd

**Spec:** `docs/superpowers/specs/2026-09-03-ad-attributed-sales-design.md`

## Global Constraints

- 作業対象リポジトリは `data-engineer/download-amazon-data`（**親の automation とは別リポジトリ**、ブランチ `refactor/ddd-structure`）。git コマンドはこのディレクトリ内で実行する。Task 8 のみ親リポジトリ側を触る
- DDD 構成に従う。`py_src/domain/` `py_src/usecases/` `py_src/infrastructure/` に分ける
- **docstring は書かない。** 型ヒントは必須。変数名で意図を表す
- 各関数の中で呼ぶ関数の粒度を揃える（SLAP）
- スプレッドシートの列は**ヘッダー行（4行目）の列名で引く**。列インデックス固定は禁止
- gspread の書き込みは `batch_update` にまとめる。1セルずつ呼ぶと 60req/min のクォータを超える
- コミットのたびに `pyproject.toml` の `version` を更新する（現在 `0.12.1`）。機能追加は MINOR、修正は PATCH
- テストは `py_tests/` に pytest で置く。ワークシートは `unittest.mock.Mock` で差し替える（既存テストに倣う）
- **欠測に 0 を書かない。** レポートに現れなかった ASIN・日付はセルに触れない
- 実行は `.venv/bin/python`。テストは `.venv/bin/python -m pytest`

---

### Task 1: Ads API の資格情報を読む値オブジェクト

**Files:**
- Create: `py_src/domain/value_objects/ads_credentials.py`
- Test: `py_tests/test_ads_credentials.py`

**Interfaces:**
- Produces: `AdsCredentials`（frozen dataclass、フィールド `client_id: str` / `client_secret: str` / `refresh_token: str` / `profile_id: str` / `region: str`、プロパティ `api_base_url: str`、クラスメソッド `from_env_file(path: Path) -> AdsCredentials`）

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_ads_credentials.py`:

```python
from pathlib import Path
import pytest
from py_src.domain.value_objects.ads_credentials import AdsCredentials


class TestAdsCredentials:
    def test_api_base_url_for_far_east(self) -> None:
        credentials = AdsCredentials(
            client_id="id", client_secret="secret", refresh_token="token",
            profile_id="123", region="FE",
        )
        assert credentials.api_base_url == "https://advertising-api-fe.amazon.com"

    def test_from_env_file(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            "# コメント行\n"
            "AMAZON_CLIENT_ID=amzn1.application-oa2-client.abc\n"
            "AMAZON_CLIENT_SECRET=secret\n"
            "AMAZON_REFRESH_TOKEN=Atzr|refresh\n"
            "AMAZON_PROFILE_ID=1234567890\n"
            "AMAZON_REGION=FE\n"
            "GOOGLE_SHEET_NAME=Amazon広告\n"
        )
        credentials = AdsCredentials.from_env_file(env_file)

        assert credentials.client_id == "amzn1.application-oa2-client.abc"
        assert credentials.refresh_token == "Atzr|refresh"
        assert credentials.profile_id == "1234567890"
        assert credentials.api_base_url == "https://advertising-api-fe.amazon.com"

    def test_from_env_file_missing_key_raises(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("AMAZON_CLIENT_ID=abc\n")

        with pytest.raises(ValueError, match="AMAZON_CLIENT_SECRET"):
            AdsCredentials.from_env_file(env_file)

    def test_from_env_file_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            AdsCredentials.from_env_file(tmp_path / "no-such.env")
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_ads_credentials.py -v`
Expected: FAIL（`ModuleNotFoundError: py_src.domain.value_objects.ads_credentials`）

- [ ] **Step 3: 実装する**

`py_src/domain/value_objects/ads_credentials.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

REGION_URLS = {
    "NA": "https://advertising-api.amazon.com",
    "EU": "https://advertising-api-eu.amazon.com",
    "FE": "https://advertising-api-fe.amazon.com",
}
REQUIRED_KEYS = (
    "AMAZON_CLIENT_ID",
    "AMAZON_CLIENT_SECRET",
    "AMAZON_REFRESH_TOKEN",
    "AMAZON_PROFILE_ID",
    "AMAZON_REGION",
)


@dataclass(frozen=True)
class AdsCredentials:
    client_id: str
    client_secret: str
    refresh_token: str
    profile_id: str
    region: str

    @property
    def api_base_url(self) -> str:
        return REGION_URLS[self.region]

    @classmethod
    def from_env_file(cls, path: Path) -> AdsCredentials:
        if not path.exists():
            raise FileNotFoundError(f"Ads API の資格情報が見つかりません: {path}")
        values = {k: v for k, v in dotenv_values(path).items() if v}
        missing = [key for key in REQUIRED_KEYS if key not in values]
        if missing:
            raise ValueError(f"{path} に足りないキー: {', '.join(missing)}")
        return cls(
            client_id=values["AMAZON_CLIENT_ID"],
            client_secret=values["AMAZON_CLIENT_SECRET"],
            refresh_token=values["AMAZON_REFRESH_TOKEN"],
            profile_id=values["AMAZON_PROFILE_ID"],
            region=values["AMAZON_REGION"],
        )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_ads_credentials.py -v`
Expected: PASS（4件）

- [ ] **Step 5: コミット**

`pyproject.toml` の `version` を `0.13.0` にしてから:

```bash
git add py_src/domain/value_objects/ads_credentials.py py_tests/test_ads_credentials.py pyproject.toml
git commit -m "feat(ads): Ads API の資格情報を .env から読む値オブジェクト v0.13.0"
```

---

### Task 2: 広告レポートの取得

**Files:**
- Create: `py_src/infrastructure/api/ads_units_repository.py`
- Test: `py_tests/test_ads_units_repository.py`

**Interfaces:**
- Consumes: `AdsCredentials`（Task 1）
- Produces: `AdsUnitsRepository(credentials: AdsCredentials, session: HttpSession = requests, poll_interval_seconds: int = 12)`、メソッド `get_daily_units(start: date, end: date) -> dict[str, dict[str, int]]`（`{"2026-09-02": {"B0HH5DR13D": 3}}`）。例外 `AdsReportError`

レポートは作成 → ポーリング → GZIP_JSON のダウンロードという3段階。`marketar/ad/tools/daily_report.py` の `AdsReports` と同じ流れだが、こちらは注入可能な `session` を取り、テストできる形にする。

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_ads_units_repository.py`:

```python
import gzip
import json
from datetime import date
from unittest.mock import Mock

import pytest

from py_src.domain.value_objects.ads_credentials import AdsCredentials
from py_src.infrastructure.api.ads_units_repository import (
    AdsReportError,
    AdsUnitsRepository,
)

CREDENTIALS = AdsCredentials(
    client_id="id", client_secret="secret", refresh_token="token",
    profile_id="123", region="FE",
)


def _response(status_code: int = 200, payload: dict | None = None, content: bytes = b"") -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload or {}
    response.content = content
    response.text = json.dumps(payload or {})
    return response


def _gzipped(rows: list[dict]) -> bytes:
    return gzip.compress(json.dumps(rows).encode())


class TestAdsUnitsRepository:
    def test_returns_units_by_date_and_asin(self) -> None:
        rows = [
            {"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D", "unitsSoldSameSku14d": 3},
            {"date": "2026-09-01", "advertisedAsin": "B0GQPRJNPF", "unitsSoldSameSku14d": 0},
            {"date": "2026-09-02", "advertisedAsin": "B0HH5DR13D", "unitsSoldSameSku14d": 5},
        ]
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.side_effect = [
            _response(payload={"status": "PENDING"}),
            _response(payload={"status": "COMPLETED", "url": "https://example.com/report.gz"}),
            _response(content=_gzipped(rows)),
        ]
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        units = repository.get_daily_units(date(2026, 9, 1), date(2026, 9, 2))

        assert units == {
            "2026-09-01": {"B0HH5DR13D": 3, "B0GQPRJNPF": 0},
            "2026-09-02": {"B0HH5DR13D": 5},
        }

    def test_report_creation_failure_raises(self) -> None:
        session = Mock()
        session.post.return_value = _response(status_code=422, payload={"detail": "bad column"})
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        with pytest.raises(AdsReportError, match="422"):
            repository.get_daily_units(date(2026, 9, 1), date(2026, 9, 2))

    def test_report_failure_status_raises(self) -> None:
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.return_value = _response(payload={"status": "FAILURE"})
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0,
        )
        repository._access_token = "cached"  # noqa: SLF001

        with pytest.raises(AdsReportError, match="FAILURE"):
            repository.get_daily_units(date(2026, 9, 1), date(2026, 9, 2))

    def test_polling_timeout_raises(self) -> None:
        session = Mock()
        session.post.return_value = _response(payload={"reportId": "r1"})
        session.get.return_value = _response(payload={"status": "PROCESSING"})
        repository = AdsUnitsRepository(
            credentials=CREDENTIALS, session=session, poll_interval_seconds=0, max_polls=3,
        )
        repository._access_token = "cached"  # noqa: SLF001

        with pytest.raises(AdsReportError, match="タイムアウト"):
            repository.get_daily_units(date(2026, 9, 1), date(2026, 9, 2))

    def test_rows_without_asin_or_date_are_skipped(self) -> None:
        rows = [
            {"date": "2026-09-01", "advertisedAsin": "", "unitsSoldSameSku14d": 3},
            {"date": "", "advertisedAsin": "B0HH5DR13D", "unitsSoldSameSku14d": 3},
            {"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D", "unitsSoldSameSku14d": 2},
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

        units = repository.get_daily_units(date(2026, 9, 1), date(2026, 9, 1))

        assert units == {"2026-09-01": {"B0HH5DR13D": 2}}

    def test_same_asin_appearing_twice_is_summed(self) -> None:
        rows = [
            {"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D", "unitsSoldSameSku14d": 2},
            {"date": "2026-09-01", "advertisedAsin": "B0HH5DR13D", "unitsSoldSameSku14d": 1},
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

        units = repository.get_daily_units(date(2026, 9, 1), date(2026, 9, 1))

        assert units == {"2026-09-01": {"B0HH5DR13D": 3}}
```

同じ ASIN が複数回現れるのは、複数キャンペーンに同じ商品を出しているとき。合算する。

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_ads_units_repository.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 実装する**

`py_src/infrastructure/api/ads_units_repository.py`:

```python
from __future__ import annotations
import gzip
import json
import time
from datetime import date
from typing import Any, Protocol

import requests

from py_src.domain.value_objects.ads_credentials import AdsCredentials

TOKEN_URL = "https://api.amazon.com/auth/o2/token"
REPORT_MEDIA = "application/vnd.createasyncreportrequest.v3+json"
REPORT_TYPE_ID = "spAdvertisedProduct"
UNITS_COLUMN = "unitsSoldSameSku14d"
COLUMNS = ["date", "advertisedAsin", UNITS_COLUMN]
TIMEOUT_SECONDS = 90
DOWNLOAD_TIMEOUT_SECONDS = 180
DEFAULT_POLL_INTERVAL_SECONDS = 12
DEFAULT_MAX_POLLS = 40


class AdsReportError(RuntimeError):
    pass


class HttpSession(Protocol):
    def post(self, url: str, **kwargs: Any) -> Any: ...
    def get(self, url: str, **kwargs: Any) -> Any: ...


class AdsUnitsRepository:
    def __init__(
        self,
        credentials: AdsCredentials,
        session: HttpSession = requests,
        poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
        max_polls: int = DEFAULT_MAX_POLLS,
    ) -> None:
        self._credentials = credentials
        self._session = session
        self._poll_interval_seconds = poll_interval_seconds
        self._max_polls = max_polls
        self._access_token: str = ""

    def get_daily_units(self, start: date, end: date) -> dict[str, dict[str, int]]:
        report_id = self._create_report(start, end)
        download_url = self._wait_for_report(report_id)
        rows = self._download_rows(download_url)
        return self._group_by_date(rows)

    def _create_report(self, start: date, end: date) -> str:
        body = {
            "name": f"ad-units-{start.isoformat()}-{end.isoformat()}",
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "configuration": {
                "adProduct": "SPONSORED_PRODUCTS",
                "groupBy": ["advertiser"],
                "columns": COLUMNS,
                "reportTypeId": REPORT_TYPE_ID,
                "timeUnit": "DAILY",
                "format": "GZIP_JSON",
            },
        }
        response = self._session.post(
            f"{self._credentials.api_base_url}/reporting/reports",
            headers=self._headers(),
            json=body,
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            raise AdsReportError(
                f"広告レポートの作成に失敗: {response.status_code} {response.text[:200]}"
            )
        return str(response.json()["reportId"])

    def _wait_for_report(self, report_id: str) -> str:
        url = f"{self._credentials.api_base_url}/reporting/reports/{report_id}"
        for _ in range(self._max_polls):
            status = self._session.get(
                url, headers=self._headers(), timeout=TIMEOUT_SECONDS
            ).json()
            if status.get("status") == "COMPLETED":
                return str(status["url"])
            if status.get("status") == "FAILURE":
                raise AdsReportError(f"広告レポートが FAILURE で終了: {status}")
            time.sleep(self._poll_interval_seconds)
        raise AdsReportError(f"広告レポート {report_id} の生成がタイムアウトしました")

    def _download_rows(self, download_url: str) -> list[dict[str, Any]]:
        raw = self._session.get(download_url, timeout=DOWNLOAD_TIMEOUT_SECONDS).content
        return json.loads(gzip.decompress(raw).decode())

    @staticmethod
    def _group_by_date(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        grouped: dict[str, dict[str, int]] = {}
        for row in rows:
            day = str(row.get("date") or "")
            asin = str(row.get("advertisedAsin") or "")
            if not day or not asin:
                continue
            units = int(row.get(UNITS_COLUMN) or 0)
            by_asin = grouped.setdefault(day, {})
            by_asin[asin] = by_asin.get(asin, 0) + units
        return grouped

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._authenticate()}",
            "Amazon-Advertising-API-ClientId": self._credentials.client_id,
            "Amazon-Advertising-API-Scope": self._credentials.profile_id,
            "Accept": REPORT_MEDIA,
            "Content-Type": REPORT_MEDIA,
        }

    def _authenticate(self) -> str:
        if self._access_token:
            return self._access_token
        response = self._session.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._credentials.refresh_token,
                "client_id": self._credentials.client_id,
                "client_secret": self._credentials.client_secret,
            },
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            raise AdsReportError(
                f"Ads API のトークン取得に失敗: {response.status_code} {response.text[:200]}"
            )
        self._access_token = str(response.json()["access_token"])
        return self._access_token
```

`_group_by_date` の直前で `grouped` にキーを作らないことが要点。レポートに出ない ASIN は
辞書に現れず、後段でセルに触れられない。

- [ ] **Step 4: テストが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_ads_units_repository.py -v`
Expected: PASS（6件）

- [ ] **Step 5: コミット**

`pyproject.toml` を `0.13.1` に:

```bash
git add py_src/infrastructure/api/ads_units_repository.py py_tests/test_ads_units_repository.py pyproject.toml
git commit -m "feat(ads): spAdvertisedProduct レポートから日別ASIN別の広告経由個数を取る v0.13.1"
```

---

### Task 3: 実物で列名の疎通を確認する

**Files:**
- Create: `tools/check_ads_columns.py`（使い捨てだがリポジトリに残す。列名を疑ったとき再実行できる）

**Interfaces:**
- Consumes: `AdsCredentials`（Task 1）、`AdsUnitsRepository`（Task 2）

`groupBy: ["advertiser"]` で `unitsSoldSameSku14d` が使えるかは Amazon のドキュメントからは
確定できない。**ここで実物を1日分だけ叩いて確かめる。** ここが通らないと以降のタスクの前提が崩れる。

- [ ] **Step 1: 確認スクリプトを書く**

`tools/check_ads_columns.py`:

```python
from __future__ import annotations
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from py_src.domain.value_objects.ads_credentials import AdsCredentials
from py_src.infrastructure.api.ads_units_repository import AdsUnitsRepository

ADS_ENV = Path(__file__).resolve().parents[2] / "dwld-ad-data" / ".env"


def main() -> None:
    credentials = AdsCredentials.from_env_file(ADS_ENV)
    repository = AdsUnitsRepository(credentials=credentials)
    target = date.today() - timedelta(days=2)
    units = repository.get_daily_units(target, target)
    print(f"{target} の行数: {sum(len(v) for v in units.values())}")
    for day, by_asin in units.items():
        for asin, count in sorted(by_asin.items(), key=lambda kv: -kv[1])[:10]:
            print(f"  {day} {asin} {count}")


if __name__ == "__main__":
    main()
```

`ADS_ENV` は `data-engineer/dwld-ad-data/.env` を指す（`download-amazon-data` から見て
`../dwld-ad-data/.env`）。

- [ ] **Step 2: 実行して列名が通ることを確認**

Run: `.venv/bin/python tools/check_ads_columns.py`
Expected: 行数と ASIN ごとの個数が出る。

**`422` や "column not supported" で落ちた場合**、`py_src/infrastructure/api/ads_units_repository.py` の
`UNITS_COLUMN` を `unitsSoldClicks14d` に変え、`COLUMNS` もそれに合わせて再実行する。
それでも落ちる場合は `groupBy` を `["advertiser", "campaign"]` にして再実行する
（`_group_by_date` が ASIN 単位で合算するので、キャンペーンが分かれても結果は変わらない）。

**どの組み合わせで通ったかを spec の「リスクと未検証事項」に追記し、未検証の記述を消す。**

- [ ] **Step 3: 結果を spec に反映してコミット**

`pyproject.toml` を `0.13.2` に:

```bash
git add tools/check_ads_columns.py docs/superpowers/specs/2026-09-03-ad-attributed-sales-design.md pyproject.toml
git commit -m "chore(ads): 広告レポートの列名を実物で確認し spec に反映 v0.13.2"
```

---

### Task 4: 広告行の解決と書き込み

**Files:**
- Create: `py_src/infrastructure/sheets/ad_sales_sheet.py`
- Test: `py_tests/test_ad_sales_sheet.py`

**Interfaces:**
- Produces: `AdSalesSheet(worksheet: Worksheet)`、メソッド `get_ad_rows() -> dict[str, list[int]]`（ASIN → 広告行の行番号リスト）と `write_ad_units(units_by_date: dict[str, dict[str, int]]) -> int`（書いたセル数を返す）

シートの前提（spec より）: ヘッダーは4行目、A列が ASIN、商品名列のヘッダー名は「商品名」、
日付列は4行目にシリアル値（整数）で入る。広告行は「A列が空 かつ 商品名列が『広告経由』
かつ 直前に ASIN 行がある」行。

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_ad_sales_sheet.py`:

```python
from unittest.mock import Mock

from gspread.utils import rowcol_to_a1

from py_src.infrastructure.sheets.ad_sales_sheet import AD_ROW_LABEL, AdSalesSheet

# 4行目がヘッダー。A列=ASIN, B列=商品名, C列以降が日付列
HEADER = ["ASIN", "商品名", 46266, 46265]
# 行1..3 はラベル行、行4 がヘッダー、行5 以降がデータ
COL_A = ["", "", "", "ASIN", "新商品", "B00EXAMPLE", "", "B00EXAMPLF", "", "B00EXAMPLE", ""]
COL_NAME = [
    "", "", "", "商品名", "", "ルーペ", AD_ROW_LABEL, "ボールネット", AD_ROW_LABEL,
    "ルーペ 2個組", AD_ROW_LABEL,
]


def _make_worksheet(
    col_a: list[str] | None = None, col_name: list[str] | None = None
) -> Mock:
    worksheet = Mock()
    worksheet.row_values.return_value = HEADER
    worksheet.col_values.side_effect = lambda col, **kwargs: (
        (col_a if col_a is not None else COL_A)
        if col == 1
        else (col_name if col_name is not None else COL_NAME)
    )
    return worksheet


class TestAdSalesSheet:
    def test_ad_row_is_bound_to_the_asin_above_it(self) -> None:
        sheet = AdSalesSheet(worksheet=_make_worksheet())

        assert sheet.get_ad_rows() == {"B00EXAMPLE": [7, 11], "B00EXAMPLF": [9]}

    def test_label_row_without_asin_above_is_ignored(self) -> None:
        col_a = ["", "", "", "ASIN", "新商品", "", "B00EXAMPLE", ""]
        col_name = ["", "", "", "商品名", "", AD_ROW_LABEL, "ルーペ", AD_ROW_LABEL]
        sheet = AdSalesSheet(worksheet=_make_worksheet(col_a, col_name))

        assert sheet.get_ad_rows() == {"B00EXAMPLE": [8]}

    def test_row_with_asin_in_column_a_is_never_an_ad_row(self) -> None:
        col_a = ["", "", "", "ASIN", "B00EXAMPLE", "B00EXAMPLF"]
        col_name = ["", "", "", "商品名", "ルーペ", AD_ROW_LABEL]
        sheet = AdSalesSheet(worksheet=_make_worksheet(col_a, col_name))

        assert sheet.get_ad_rows() == {}

    def test_writes_units_to_matching_date_column(self) -> None:
        worksheet = _make_worksheet()
        sheet = AdSalesSheet(worksheet=worksheet)
        sheet.get_ad_rows()

        written = sheet.write_ad_units({"2026-09-01": {"B00EXAMPLE": 3, "B00EXAMPLF": 1}})

        assert written == 3
        requests = worksheet.batch_update.call_args[0][0]
        by_range = {r["range"]: r["values"] for r in requests}
        assert by_range[rowcol_to_a1(7, 3)] == [[3]]
        assert by_range[rowcol_to_a1(11, 3)] == [[3]]
        assert by_range[rowcol_to_a1(9, 3)] == [[1]]

    def test_skips_dates_without_a_column(self) -> None:
        worksheet = _make_worksheet()
        sheet = AdSalesSheet(worksheet=worksheet)
        sheet.get_ad_rows()

        written = sheet.write_ad_units({"2026-08-01": {"B00EXAMPLE": 3}})

        assert written == 0
        worksheet.batch_update.assert_not_called()

    def test_does_not_touch_cells_for_asins_absent_from_the_report(self) -> None:
        worksheet = _make_worksheet()
        sheet = AdSalesSheet(worksheet=worksheet)
        sheet.get_ad_rows()

        sheet.write_ad_units({"2026-09-01": {"B00EXAMPLE": 3}})

        requests = worksheet.batch_update.call_args[0][0]
        assert rowcol_to_a1(9, 3) not in {r["range"] for r in requests}

    def test_writes_all_dates_in_one_batch(self) -> None:
        worksheet = _make_worksheet()
        sheet = AdSalesSheet(worksheet=worksheet)
        sheet.get_ad_rows()

        sheet.write_ad_units(
            {"2026-09-01": {"B00EXAMPLF": 1}, "2026-08-31": {"B00EXAMPLF": 2}}
        )

        assert worksheet.batch_update.call_count == 1
        requests = worksheet.batch_update.call_args[0][0]
        by_range = {r["range"]: r["values"] for r in requests}
        assert by_range[rowcol_to_a1(9, 3)] == [[1]]
        assert by_range[rowcol_to_a1(9, 4)] == [[2]]
```

`46266` は 2026-09-01、`46265` は 2026-08-31 のシリアル値（1899-12-30 起点）。
実シートでは 2026-09-02 が `46267`。`.venv/bin/python -c "from datetime import date; print((date(2026,9,1)-date(1899,12,30)).days)"` で確かめられる。

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_ad_sales_sheet.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 実装する**

`py_src/infrastructure/sheets/ad_sales_sheet.py`:

```python
from __future__ import annotations
from datetime import date, datetime

from gspread import Worksheet
from gspread.utils import rowcol_to_a1, ValueRenderOption

from py_src.infrastructure.sheets.retry import retry_on_transient_error

HEADER_ROW = 4
ASIN_COLUMN = 1
PRODUCT_NAME_HEADER = "商品名"
AD_ROW_LABEL = "広告経由"
ASIN_LENGTH = 10
SHEETS_EPOCH = date(1899, 12, 30)


def _date_serial(day: date) -> int:
    return (day - SHEETS_EPOCH).days


class AdSalesSheet:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet
        self._ad_rows: dict[str, list[int]] = {}
        self._serial_to_column: dict[int, int] = {}

    def get_ad_rows(self) -> dict[str, list[int]]:
        headers = self._worksheet.row_values(HEADER_ROW)
        name_column = self._find_column(headers, PRODUCT_NAME_HEADER)
        asin_values = self._worksheet.col_values(ASIN_COLUMN)
        name_values = self._worksheet.col_values(name_column)
        self._ad_rows = self._bind_ad_rows(asin_values, name_values)
        return self._ad_rows

    @retry_on_transient_error
    def write_ad_units(self, units_by_date: dict[str, dict[str, int]]) -> int:
        self._serial_to_column = self._read_date_columns()
        requests = [
            {"range": rowcol_to_a1(row, column), "values": [[units]]}
            for day, by_asin in units_by_date.items()
            for column in self._columns_for(day)
            for asin, units in by_asin.items()
            for row in self._ad_rows.get(asin, [])
        ]
        if not requests:
            return 0
        self._worksheet.batch_update(requests, value_input_option="RAW")
        return len(requests)

    def _columns_for(self, day: str) -> list[int]:
        serial = _date_serial(datetime.strptime(day, "%Y-%m-%d").date())
        column = self._serial_to_column.get(serial)
        return [column] if column else []

    def _read_date_columns(self) -> dict[int, int]:
        header = self._worksheet.row_values(
            HEADER_ROW, value_render_option=ValueRenderOption.unformatted
        )
        return {
            value: index
            for index, value in enumerate(header, start=1)
            if isinstance(value, int)
        }

    @staticmethod
    def _bind_ad_rows(asin_values: list[str], name_values: list[str]) -> dict[str, list[int]]:
        ad_rows: dict[str, list[int]] = {}
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
            if name == AD_ROW_LABEL and current_asin:
                ad_rows.setdefault(current_asin, []).append(row)
        return ad_rows

    @staticmethod
    def _find_column(headers: list[str], name: str) -> int:
        for index, value in enumerate(headers, start=1):
            if str(value).strip() == name:
                return index
        raise ValueError(f"ヘッダーに '{name}' が見つかりません")
```

`_bind_ad_rows` で、A列に ASIN 以外の文字列（「新商品」「様子見」などの見出し）が来たら
`current_asin` を空に戻す。見出しをまたいで前の ASIN に紐づけないため。

`_read_date_columns` は 4行目の**未整形値**を読む。日付列はシリアル値（整数）なので、
`isinstance(value, int)` だけで日付列と他の列を分けられる。

- [ ] **Step 4: テストが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_ad_sales_sheet.py -v`
Expected: PASS（7件）

- [ ] **Step 5: コミット**

`pyproject.toml` を `0.14.0` に:

```bash
git add py_src/infrastructure/sheets/ad_sales_sheet.py py_tests/test_ad_sales_sheet.py pyproject.toml
git commit -m "feat(ads): 広告行を解決して日付列へ個数を書く AdSalesSheet v0.14.0"
```

---

### Task 5: ユースケースと `main.py ads` サブコマンド

**Files:**
- Create: `py_src/usecases/update_ad_sales.py`
- Modify: `main.py`
- Test: `py_tests/test_update_ad_sales.py`

**Interfaces:**
- Consumes: `AdsUnitsRepository.get_daily_units`（Task 2）、`AdSalesSheet.get_ad_rows` / `write_ad_units`（Task 4）
- Produces: `UpdateAdSalesUseCase(ad_sheet: AdSalesSheet, ads_repository: AdsUnitsRepository, days: int = 14)`、メソッド `execute() -> int`（書いたセル数）。`main.py` に `update_ad_sales()` を追加し、`sys.argv[1] == "ads"` で呼ぶ

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_update_ad_sales.py`:

```python
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock

from py_src.usecases.update_ad_sales import UpdateAdSalesUseCase

JST = timezone(timedelta(hours=9))


class TestUpdateAdSalesUseCase:
    def test_requests_the_last_14_days_ending_yesterday(self) -> None:
        ad_sheet = Mock()
        ad_sheet.write_ad_units.return_value = 0
        ads_repository = Mock()
        ads_repository.get_daily_units.return_value = {}
        usecase = UpdateAdSalesUseCase(
            ad_sheet=ad_sheet, ads_repository=ads_repository, days=14,
        )

        usecase.execute()

        start, end = ads_repository.get_daily_units.call_args[0]
        yesterday = (datetime.now(JST) - timedelta(days=1)).date()
        assert end == yesterday
        assert start == yesterday - timedelta(days=13)

    def test_resolves_ad_rows_before_writing(self) -> None:
        ad_sheet = Mock()
        ad_sheet.write_ad_units.return_value = 5
        ads_repository = Mock()
        ads_repository.get_daily_units.return_value = {"2026-09-01": {"B00EXAMPLE": 3}}
        usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)

        written = usecase.execute()

        ad_sheet.get_ad_rows.assert_called_once()
        ad_sheet.write_ad_units.assert_called_once_with({"2026-09-01": {"B00EXAMPLE": 3}})
        assert written == 5

    def test_report_failure_writes_nothing(self) -> None:
        ad_sheet = Mock()
        ads_repository = Mock()
        ads_repository.get_daily_units.side_effect = RuntimeError("レポート失敗")
        usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)

        try:
            usecase.execute()
        except RuntimeError:
            pass

        ad_sheet.write_ad_units.assert_not_called()

    def test_backfill_range_overrides_the_default_window(self) -> None:
        ad_sheet = Mock()
        ad_sheet.write_ad_units.return_value = 0
        ads_repository = Mock()
        ads_repository.get_daily_units.return_value = {}
        usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)

        usecase.execute_range(date(2026, 6, 1), date(2026, 6, 30))

        assert ads_repository.get_daily_units.call_args[0] == (
            date(2026, 6, 1), date(2026, 6, 30),
        )
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_update_ad_sales.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: ユースケースを実装する**

`py_src/usecases/update_ad_sales.py`:

```python
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
DEFAULT_DAYS = 14


class UpdateAdSalesUseCase:
    def __init__(
        self, ad_sheet: object, ads_repository: object, days: int = DEFAULT_DAYS,
    ) -> None:
        self._ad_sheet = ad_sheet
        self._ads_repository = ads_repository
        self._days = days

    def execute(self) -> int:
        end = (datetime.now(JST) - timedelta(days=1)).date()
        start = end - timedelta(days=self._days - 1)
        return self.execute_range(start, end)

    def execute_range(self, start: date, end: date) -> int:
        self._ad_sheet.get_ad_rows()
        units_by_date = self._ads_repository.get_daily_units(start, end)
        return self._ad_sheet.write_ad_units(units_by_date)
```

`get_ad_rows()` を取得より先に呼ぶ。レポート取得に数分かかるため、シートを読むのが先の方が
「シートが壊れている」ことに早く気づける。

- [ ] **Step 4: `main.py` にサブコマンドを足す**

`main.py` の import 群に追加:

```python
from py_src.domain.value_objects.ads_credentials import AdsCredentials
from py_src.infrastructure.api.ads_units_repository import AdsUnitsRepository
from py_src.infrastructure.sheets.ad_sales_sheet import AdSalesSheet
from py_src.usecases.update_ad_sales import UpdateAdSalesUseCase
```

ファイル冒頭の `import os` の下に:

```python
from pathlib import Path

ADS_ENV_PATH = Path(__file__).resolve().parents[1] / "dwld-ad-data" / ".env"
```

`update_inventory_status()` の下に関数を追加:

```python
def update_ad_sales() -> None:
    load_dotenv()
    credentials = AdsCredentials.from_env_file(ADS_ENV_PATH)
    ads_repository = AdsUnitsRepository(credentials=credentials)
    spreadsheet = _open_spreadsheet()
    ad_sheet = AdSalesSheet(worksheet=spreadsheet.worksheet("売上/日"))
    usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)
    written = usecase.execute()
    print(f"広告経由の売上個数を {written} セル書き込みました")
```

`__main__` ブロックの `elif` 連鎖に追加（`inventory` の分岐の下）:

```python
    elif len(sys.argv) > 1 and sys.argv[1] == "ads":
        update_ad_sales()
```

- [ ] **Step 5: テストが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/ -v`
Expected: 全 PASS（既存テストを壊していないこと）

- [ ] **Step 6: コミット**

`pyproject.toml` を `0.15.0` に:

```bash
git add py_src/usecases/update_ad_sales.py py_tests/test_update_ad_sales.py main.py pyproject.toml
git commit -m "feat(ads): main.py ads で広告経由の売上個数を売上/日へ書く v0.15.0"
```

---

### Task 6: 広告行を挿入する移行スクリプト

**Files:**
- Create: `insert_ad_rows.py`
- Test: `py_tests/test_insert_ad_rows.py`

**Interfaces:**
- Produces: `plan_ad_row_insertions(asin_values: list[str], name_values: list[str]) -> list[int]`（挿入位置＝ASIN 行の行番号のリスト、**降順**）と `build_insert_requests(sheet_id: int, insert_rows: list[int]) -> list[dict]`

74行を1行ずつ `insert_row` すると 60req/min のクォータに掛かる。**`insertDimension` を
1回の `batch_update` にまとめる。** 挿入位置を**降順**に並べれば、上の行の行番号は挿入の
影響を受けないので、まとめて投げても位置がずれない。

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_insert_ad_rows.py`:

```python
from insert_ad_rows import build_insert_requests, plan_ad_row_insertions

AD_LABEL = "広告経由"


class TestPlanAdRowInsertions:
    def test_plans_one_row_under_each_asin_in_descending_order(self) -> None:
        asin_values = ["", "", "", "ASIN", "新商品", "B00EXAMPLE", "B00EXAMPLF"]
        name_values = ["", "", "", "商品名", "", "ルーペ", "ボールネット"]

        assert plan_ad_row_insertions(asin_values, name_values) == [7, 6]

    def test_skips_asins_that_already_have_an_ad_row(self) -> None:
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE", "", "B00EXAMPLF"]
        name_values = ["", "", "", "商品名", "ルーペ", AD_LABEL, "ボールネット"]

        assert plan_ad_row_insertions(asin_values, name_values) == [7]

    def test_ignores_heading_rows(self) -> None:
        asin_values = ["", "", "", "ASIN", "様子見", "やめる", "過去"]
        name_values = ["", "", "", "商品名", "", "", ""]

        assert plan_ad_row_insertions(asin_values, name_values) == []

    def test_last_asin_at_the_end_of_the_sheet_gets_a_row(self) -> None:
        asin_values = ["", "", "", "ASIN", "B00EXAMPLE"]
        name_values = ["", "", "", "商品名", "ルーペ"]

        assert plan_ad_row_insertions(asin_values, name_values) == [5]


class TestBuildInsertRequests:
    def test_inserts_after_each_target_row(self) -> None:
        requests = build_insert_requests(sheet_id=551300985, insert_rows=[7, 6])

        ranges = [r["insertDimension"]["range"] for r in requests]
        assert ranges[0] == {
            "sheetId": 551300985, "dimension": "ROWS", "startIndex": 7, "endIndex": 8,
        }
        assert ranges[1] == {
            "sheetId": 551300985, "dimension": "ROWS", "startIndex": 6, "endIndex": 7,
        }

    def test_does_not_inherit_formatting_from_the_row_above(self) -> None:
        requests = build_insert_requests(sheet_id=1, insert_rows=[5])

        assert requests[0]["insertDimension"]["inheritFromBefore"] is False
```

`insertDimension` の `startIndex` は0起点。行 `n` の**直後**に挿入するには `startIndex = n`。

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_insert_ad_rows.py -v`
Expected: FAIL（`ModuleNotFoundError: insert_ad_rows`）

- [ ] **Step 3: 実装する**

`insert_ad_rows.py`:

```python
from __future__ import annotations
import os
import sys
from pathlib import Path

import gspread
from dotenv import load_dotenv
from gspread.utils import rowcol_to_a1
from oauth2client.service_account import ServiceAccountCredentials

from py_src.infrastructure.sheets.ad_sales_sheet import (
    AD_ROW_LABEL,
    ASIN_COLUMN,
    ASIN_LENGTH,
    HEADER_ROW,
    PRODUCT_NAME_HEADER,
)

SHEET_NAME = "売上/日"
AD_ROW_BACKGROUND = {"backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95}}


def plan_ad_row_insertions(asin_values: list[str], name_values: list[str]) -> list[int]:
    targets: list[int] = []
    total = max(len(asin_values), len(name_values))
    for index in range(total):
        asin = asin_values[index].strip() if index < len(asin_values) else ""
        if len(asin) != ASIN_LENGTH:
            continue
        below = index + 1
        name_below = name_values[below].strip() if below < len(name_values) else ""
        asin_below = asin_values[below].strip() if below < len(asin_values) else ""
        already_has_ad_row = not asin_below and name_below == AD_ROW_LABEL
        if already_has_ad_row:
            continue
        targets.append(index + 1)
    return sorted(targets, reverse=True)


def build_insert_requests(sheet_id: int, insert_rows: list[int]) -> list[dict]:
    return [
        {
            "insertDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": row,
                    "endIndex": row + 1,
                },
                "inheritFromBefore": False,
            }
        }
        for row in insert_rows
    ]


def _open_worksheet() -> gspread.Worksheet:
    load_dotenv()
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(os.getenv("SPREADSHEET_ID"))
    return spreadsheet.worksheet(SHEET_NAME)


def _find_column(headers: list[str], name: str) -> int:
    for index, value in enumerate(headers, start=1):
        if str(value).strip() == name:
            return index
    raise ValueError(f"ヘッダーに '{name}' が見つかりません")


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    worksheet = _open_worksheet()
    headers = worksheet.row_values(HEADER_ROW)
    name_column = _find_column(headers, PRODUCT_NAME_HEADER)
    asin_values = worksheet.col_values(ASIN_COLUMN)
    name_values = worksheet.col_values(name_column)

    insert_rows = plan_ad_row_insertions(asin_values, name_values)
    print(f"広告行を挿入する対象: {len(insert_rows)} 件")
    for row in reversed(insert_rows):
        print(f"  行{row} ({asin_values[row - 1].strip()}) の直下")
    if dry_run or not insert_rows:
        return

    worksheet.spreadsheet.batch_update(
        {"requests": build_insert_requests(worksheet.id, insert_rows)}
    )

    label_column_letter = rowcol_to_a1(1, name_column).rstrip("1")
    ad_rows = _ad_row_numbers(insert_rows)
    worksheet.batch_update(
        [
            {"range": f"{label_column_letter}{row}", "values": [[AD_ROW_LABEL]]}
            for row in ad_rows
        ],
        value_input_option="RAW",
    )
    worksheet.batch_format(
        [
            {"range": f"A{row}:{label_column_letter}{row}", "format": AD_ROW_BACKGROUND}
            for row in ad_rows
        ]
    )
    print(f"広告行を {len(ad_rows)} 行入れました")


def _ad_row_numbers(insert_rows: list[int]) -> list[int]:
    # 昇順に見ると、i 番目の挿入位置は自分より上に入った i 行分だけ下へずれる
    ascending = sorted(insert_rows)
    return [row + offset + 1 for offset, row in enumerate(ascending)]


if __name__ == "__main__":
    main()
```

`AdSalesSheet` から定数を import する。同じ「広告経由」という文字列を2箇所に書かないため。

- [ ] **Step 4: `_ad_row_numbers` のテストを足す**

`py_tests/test_insert_ad_rows.py` に追記:

```python
from insert_ad_rows import _ad_row_numbers


class TestAdRowNumbers:
    def test_each_insertion_shifts_the_ones_below_it(self) -> None:
        # 行6と行7のASINの直下へ入れると、広告行は7と9になる
        assert _ad_row_numbers([7, 6]) == [7, 9]

    def test_single_insertion(self) -> None:
        assert _ad_row_numbers([5]) == [6]
```

- [ ] **Step 5: テストが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_insert_ad_rows.py -v`
Expected: PASS（8件）

- [ ] **Step 6: dry-run で対象を確認する**

Run: `.venv/bin/python insert_ad_rows.py --dry-run`
Expected: 対象が約74件で、列挙された ASIN が実際の商品と合っている

- [ ] **Step 7: 本実行してシートを確認する**

Run: `.venv/bin/python insert_ad_rows.py`

ブラウザで [売上/日](https://docs.google.com/spreadsheets/d/1Z3P0iL19r3gA9-NG8x2e_42pGhrEs_wFMLWLbFvReAw/edit?gid=551300985) を開き、以下を目で確かめる:

- 各 ASIN 行の直下に「広告経由」の行があり、薄いグレーになっている
- 売上行の売上個数・価格・数式列が変わっていない
- 「新商品」「様子見」「過去」などの見出し行の直下に広告行が入っていない

- [ ] **Step 8: 再実行しても増えないことを確認**

Run: `.venv/bin/python insert_ad_rows.py --dry-run`
Expected: 「広告行を挿入する対象: 0 件」

- [ ] **Step 9: コミット**

`pyproject.toml` を `0.16.0` に:

```bash
git add insert_ad_rows.py py_tests/test_insert_ad_rows.py pyproject.toml
git commit -m "feat(ads): 各ASIN行の直下へ広告行を挿入する移行スクリプト v0.16.0"
```

---

### Task 7: 実データで `main.py ads` を通す

**Files:**
- Modify: `CLAUDE.md`

Task 5 で書いたコードを、Task 6 で作った実際の広告行に対して初めて走らせる。

- [ ] **Step 1: 実行する**

Run: `.venv/bin/python main.py ads`
Expected: 「広告経由の売上個数を N セル書き込みました」（N は 0 より大きい）

- [ ] **Step 2: シートを目で確かめる**

- 広告行の直近14日分に数字が入っている
- **売上行の値・ノート（価格）・総売上（3行目）・日付ラベル（1行目/4行目）が変わっていない**
- 広告経由の個数が、同じ日の売上個数を超えていない（超えていたら指標の取り違い。Task 3 に戻る）

- [ ] **Step 3: `CLAUDE.md` に追記する**

「Python エントリポイント (`main.py`)」の表に行を足す:

```markdown
| `ads` | `UpdateAdSalesUseCase` | 広告経由の売上個数を「売上/日」の広告行へ書く（直近14日を毎日上書き）|
```

さらに「日次売上の取得と書き込み」の節の後ろに、新しい節を足す:

```markdown
## 広告経由の売上個数（v0.15.0〜）

「売上/日」は各 ASIN 行の直下に**広告行**を1本持つ。A列は空、商品名列に「広告経由」。
`main.py ads` が Amazon Ads の `spAdvertisedProduct` レポート（DAILY）から
`unitsSoldSameSku14d` を取り、この行へ書く。

- **日付列は作らない。** 列を作るのは `main.py daily` の責務で、広告ジョブは既にある列に
  書き足すだけ。無い日付はスキップする
- **毎日、直近14日分を上書きする。** 広告の成果はクリックから14日後まで加算されるため、
  昨日分を1回書いて終わりにすると全ての過去日が過小のまま固定される
- **日次売上ジョブとは別ジョブにしてある**（`com.automation.download-amazon-data-ads`、毎日 2:00）。
  日次売上は SP-API だけで4分かかり10%失敗で中断する設計で、ここに Ads のレポート生成待ちを
  足すと片方の失敗が両方を巻き込む
- 資格情報は `data-engineer/dwld-ad-data/.env` を参照する（SP-API とは**別の** refresh_token）
- 広告行は「A列が空 かつ 商品名列が『広告経由』かつ 直前に ASIN 行がある」で特定する。
  位置だけに頼っていないので、空行が紛れ込んでも誤って書かない
- 行を足すのは `insert_ad_rows.py`（冪等。`--dry-run` あり）。過去分は `backfill_ad_sales.py`
```

- [ ] **Step 4: コミット**

`pyproject.toml` を `0.16.1` に:

```bash
git add CLAUDE.md pyproject.toml
git commit -m "docs: 広告経由の売上個数の運用を追記 v0.16.1"
```

---

### Task 8: 過去分のバックフィル

**Files:**
- Create: `backfill_ad_sales.py`
- Test: `py_tests/test_backfill_ad_sales.py`

**Interfaces:**
- Consumes: `UpdateAdSalesUseCase.execute_range`（Task 5）
- Produces: `split_into_chunks(start: date, end: date, max_days: int = 31) -> list[tuple[date, date]]`

Amazon Ads のレポートは1リクエストあたり最大31日。90日を埋めるには分割する。

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_backfill_ad_sales.py`:

```python
from datetime import date

from backfill_ad_sales import split_into_chunks


class TestSplitIntoChunks:
    def test_range_within_the_limit_is_one_chunk(self) -> None:
        assert split_into_chunks(date(2026, 9, 1), date(2026, 9, 10)) == [
            (date(2026, 9, 1), date(2026, 9, 10))
        ]

    def test_exactly_31_days_is_one_chunk(self) -> None:
        assert split_into_chunks(date(2026, 9, 1), date(2026, 10, 1)) == [
            (date(2026, 9, 1), date(2026, 10, 1))
        ]

    def test_90_days_splits_into_three(self) -> None:
        chunks = split_into_chunks(date(2026, 6, 6), date(2026, 9, 3))

        assert len(chunks) == 3
        assert chunks[0][0] == date(2026, 6, 6)
        assert chunks[-1][1] == date(2026, 9, 3)
        for earlier, later in zip(chunks, chunks[1:]):
            assert (later[0] - earlier[1]).days == 1

    def test_start_after_end_raises(self) -> None:
        try:
            split_into_chunks(date(2026, 9, 3), date(2026, 9, 1))
        except ValueError as error:
            assert "開始日" in str(error)
        else:
            raise AssertionError("ValueError が上がらなかった")
```

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_backfill_ad_sales.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 実装する**

`backfill_ad_sales.py`:

```python
from __future__ import annotations
import sys
from datetime import date, datetime, timedelta

from main import ADS_ENV_PATH, _open_spreadsheet
from py_src.domain.value_objects.ads_credentials import AdsCredentials
from py_src.infrastructure.api.ads_units_repository import AdsUnitsRepository
from py_src.infrastructure.sheets.ad_sales_sheet import AdSalesSheet
from py_src.usecases.update_ad_sales import UpdateAdSalesUseCase

MAX_DAYS_PER_REPORT = 31


def split_into_chunks(
    start: date, end: date, max_days: int = MAX_DAYS_PER_REPORT
) -> list[tuple[date, date]]:
    if start > end:
        raise ValueError(f"開始日が終了日より後です: {start} > {end}")
    chunks: list[tuple[date, date]] = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=max_days - 1), end)
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end + timedelta(days=1)
    return chunks


def main() -> None:
    if len(sys.argv) < 3:
        print("使い方: backfill_ad_sales.py <開始日 YYYY-MM-DD> <終了日 YYYY-MM-DD>")
        sys.exit(1)
    start = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    end = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()

    credentials = AdsCredentials.from_env_file(ADS_ENV_PATH)
    ads_repository = AdsUnitsRepository(credentials=credentials)
    spreadsheet = _open_spreadsheet()
    ad_sheet = AdSalesSheet(worksheet=spreadsheet.worksheet("売上/日"))
    usecase = UpdateAdSalesUseCase(ad_sheet=ad_sheet, ads_repository=ads_repository)

    total = 0
    for chunk_start, chunk_end in split_into_chunks(start, end):
        written = usecase.execute_range(chunk_start, chunk_end)
        print(f"{chunk_start} 〜 {chunk_end}: {written} セル")
        total += written
    print(f"合計 {total} セル書き込みました")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: テストが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_backfill_ad_sales.py -v`
Expected: PASS（4件）

- [ ] **Step 5: 90日分を埋める**

Run: `.venv/bin/python backfill_ad_sales.py 2026-06-06 2026-09-02`
Expected: 3チャンクそれぞれのセル数が出る。日付列が無い日はセル数に含まれない

- [ ] **Step 6: コミット**

`pyproject.toml` を `0.17.0` に:

```bash
git add backfill_ad_sales.py py_tests/test_backfill_ad_sales.py pyproject.toml
git commit -m "feat(ads): 過去分の広告経由売上個数を31日ずつ埋めるバックフィル v0.17.0"
```

---

### Task 9: 「売上/今」の行ずれを直す

**Files:**
- Modify: `py_src/infrastructure/sheets/realtime_sales_sheet.py`
- Test: `py_tests/test_realtime_sales_sheet.py`

`RealtimeSalesSheet` は A列から10文字の値だけを抜き出してリストにし、**2行目から詰めて**
「個数」「売上」を書いている。A列は `=ARRAYFORMULA('売上/日'!A4:A)` で見出し行も含めて
流れてくるため、**見出し行の数だけ値が上にずれる**。広告行を74本挟んだ今、これは決定的にずれる。

**A列の実際の行位置に書く**方式へ直す。ASIN でない行は空白で埋める。

- [ ] **Step 1: 失敗するテストを書く**

`py_tests/test_realtime_sales_sheet.py` に追記:

```python
    def test_writes_values_at_the_row_where_the_asin_actually_is(self) -> None:
        ws = self._make_worksheet(
            ["ASIN", "個数", "売上"],
            ["ASIN", "新商品", "B00EXAMPLE", "", "B00EXAMPLF"],
        )
        sheet = RealtimeSalesSheet(worksheet=ws)
        sheet.get_asin_list()

        sales_map: dict[str, RealtimeSalesResult] = {
            "B00EXAMPLE": RealtimeSalesResult(
                asin="B00EXAMPLE", unit_count=5, total_amount=10000.0
            ),
            "B00EXAMPLF": RealtimeSalesResult(
                asin="B00EXAMPLF", unit_count=2, total_amount=4000.0
            ),
        }
        sheet.write_realtime_sales(sales_map)

        # A列: 行2=新商品, 行3=B00EXAMPLE, 行4=空, 行5=B00EXAMPLF
        ws.update.assert_any_call("B2", [[""], [5], [""], [2]])
        ws.update.assert_any_call("C2", [[""], [10000.0], [""], [4000.0]])

    def test_ad_rows_between_asins_are_left_blank(self) -> None:
        ws = self._make_worksheet(
            ["ASIN", "個数", "売上"],
            ["ASIN", "B00EXAMPLE", "", "B00EXAMPLF", ""],
        )
        sheet = RealtimeSalesSheet(worksheet=ws)
        sheet.get_asin_list()

        sales_map: dict[str, RealtimeSalesResult] = {
            "B00EXAMPLE": RealtimeSalesResult(
                asin="B00EXAMPLE", unit_count=1, total_amount=500.0
            ),
        }
        sheet.write_realtime_sales(sales_map)

        # 書き込む範囲は行2から「最後のASIN行」まで。末尾の広告行(行5)は範囲に入らない
        ws.update.assert_any_call("B2", [[1], [""], [0]])
        ws.update.assert_any_call("C2", [[500.0], [""], [0.0]])
```

既存の `test_write_realtime_sales` と `test_write_to_non_adjacent_columns` は、A列が
見出し行を含まないため**期待値が変わらない**。そのまま通ること。

- [ ] **Step 2: テストが落ちることを確認**

Run: `.venv/bin/python -m pytest py_tests/test_realtime_sales_sheet.py -v`
Expected: 新しい2件が FAIL、既存4件は PASS

- [ ] **Step 3: 実装する**

`py_src/infrastructure/sheets/realtime_sales_sheet.py` の `get_asin_list` と
`write_realtime_sales` を差し替える:

```python
    def get_asin_list(self) -> list[str]:
        header = self._worksheet.row_values(1)
        self._unit_col = self._find_column(header, "個数")
        self._sales_col = self._find_column(header, "売上")
        values = self._worksheet.col_values(1)
        self._asin_rows = [
            (value.strip(), index + 1)
            for index, value in enumerate(values)
            if index > 0 and value and len(value.strip()) == ASIN_LENGTH
        ]
        self._asin_list = [asin for asin, _ in self._asin_rows]
        return self._asin_list

    def write_realtime_sales(self, sales_map: dict[str, RealtimeSalesResult]) -> None:
        if not self._asin_rows:
            return
        last_row = self._asin_rows[-1][1]
        unit_data: list[list[int | str]] = [[""] for _ in range(last_row - 1)]
        sales_data: list[list[float | str]] = [[""] for _ in range(last_row - 1)]
        for asin, row in self._asin_rows:
            sales = sales_map.get(asin)
            unit_data[row - 2] = [sales.unit_count if sales else 0]
            sales_data[row - 2] = [sales.total_amount if sales else 0.0]
        self._worksheet.update(rowcol_to_a1(2, self._unit_col), unit_data)
        self._worksheet.update(rowcol_to_a1(2, self._sales_col), sales_data)
        self._write_updated_at()
```

`__init__` に `self._asin_rows: list[tuple[str, int]] = []` を足し、モジュール定数
`ASIN_LENGTH = 10` を冒頭に置く。

行2から最後の ASIN 行までを1レンジで送る。ASIN 行以外は `""` なので、見出し行と広告行の
セルは空になる。

- [ ] **Step 4: テストが通ることを確認**

Run: `.venv/bin/python -m pytest py_tests/ -v`
Expected: 全 PASS

- [ ] **Step 5: 実データで確認する**

Run: `.venv/bin/python main.py`

[売上/今](https://docs.google.com/spreadsheets/d/1Z3P0iL19r3gA9-NG8x2e_42pGhrEs_wFMLWLbFvReAw/edit?gid=0) を開き、
**「個数」「売上」が、同じ行に表示されている商品名と対応している**ことを確かめる。
広告行と見出し行のセルは空になっている。

- [ ] **Step 6: コミット**

`pyproject.toml` を `0.17.1` に:

```bash
git add py_src/infrastructure/sheets/realtime_sales_sheet.py py_tests/test_realtime_sales_sheet.py pyproject.toml
git commit -m "fix: 売上/今 の個数と売上を ASIN の実際の行位置へ書く v0.17.1"
```

---

### Task 10: launchd ジョブを登録する

**Files:**
- Create: `/Users/wadaatsushi/Documents/automation/ops/launchd/com.automation.download-amazon-data-ads.plist`

**このタスクだけ親リポジトリ（automation 本体）を触る。**

plist の正本は `ops/launchd/` に置き、`sync_agents.py` が `~/Library/LaunchAgents/` へ
**実ファイルとして cp で配る**。`ops/launchd/*.plist` を glob で拾うので、置くだけで対象になる。

**plist を symlink にしてはいけない。** シェルから bootstrap すれば動くが、ログイン時の
自動ロードが `~/Documents` を読めず、次の再起動で全ジョブが消える（2026-08-18 に18ジョブが
2日間停止した）。

- [ ] **Step 1: plist を作る**

`ops/launchd/com.automation.download-amazon-data-ads.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>EnvironmentVariables</key>
	<dict>
		<key>LANG</key>
		<string>ja_JP.UTF-8</string>
		<key>PATH</key>
		<string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
	</dict>
	<key>Label</key>
	<string>com.automation.download-amazon-data-ads</string>
	<key>ProcessType</key>
	<string>Background</string>
	<key>ProgramArguments</key>
	<array>
		<string>/Users/wadaatsushi/Library/LaunchAgents/scripts/notify-on-failure.sh</string>
		<string>com.automation.download-amazon-data-ads</string>
		<string>/Users/wadaatsushi/Documents/automation/data-engineer/download-amazon-data/.venv/bin/python</string>
		<string>/Users/wadaatsushi/Documents/automation/data-engineer/download-amazon-data/main.py</string>
		<string>ads</string>
	</array>
	<key>RunAtLoad</key>
	<false/>
	<key>StandardErrorPath</key>
	<string>/Users/wadaatsushi/Library/Logs/download-amazon-data-ads.err</string>
	<key>StandardOutPath</key>
	<string>/Users/wadaatsushi/Library/Logs/download-amazon-data-ads.log</string>
	<key>StartCalendarInterval</key>
	<dict>
		<key>Hour</key>
		<integer>2</integer>
		<key>Minute</key>
		<integer>0</integer>
	</dict>
	<key>WorkingDirectory</key>
	<string>/Users/wadaatsushi/Documents/automation/data-engineer/download-amazon-data</string>
</dict>
</plist>
```

`ProgramArguments[0]`（notify-on-failure.sh）と std path は `~/Documents` の外。
`WorkingDirectory` だけは `~/Documents` 配下でよい。

- [ ] **Step 2: 配布して登録する**

```bash
cd /Users/wadaatsushi/Documents/automation/ops && python3 sync_agents.py
```

- [ ] **Step 3: 検査を通す**

```bash
cd /Users/wadaatsushi/Documents/automation/ops && python3 check_launchd.py
```

Expected: exit 0（参照パス・symlink 混入・未ロードなし）

- [ ] **Step 4: 手動起動して結果を確認する**

```bash
launchctl start com.automation.download-amazon-data-ads
launchctl print gui/$(id -u)/com.automation.download-amazon-data-ads | grep -E "runs|last exit code"
```

Expected: `runs = 1` 以上、`last exit code = 0`

**シェルから直接 `main.py ads` を実行しても検証にならない。** シェルには TCC 許可があり、
launchd 経由でしか起きない失敗（インタプリタや std path が読めない）が再現しないため。

- [ ] **Step 5: 親リポジトリでコミット**

```bash
cd /Users/wadaatsushi/Documents/automation
git add ops/launchd/com.automation.download-amazon-data-ads.plist
git diff --cached --name-only
git commit -m "feat(ops): 広告経由の売上個数を毎日2:00に取り込む launchd ジョブ"
```

`git add` はファイルを個別に指定する。`git diff --cached --name-only` で
自分の担当範囲外が0件であることを必ず確認する（複数セッションが同じ作業ディレクトリを共有している）。

---

### Task 11: 新商品追加時に広告行も作る

**Files:**
- Modify: `/Users/wadaatsushi/Documents/automation/marketar/listing-creator/write_sales_sheet.py`

**このタスクも親リポジトリ側。**

`write_sales_data()` は `sales_ws.insert_row([], index=INSERT_ROW)` で1行だけ挿入している。
広告行が必要になったので**2行**挿入し、2行目を広告行に仕立てる。

あわせて `copy_formula_columns(source_start_row=INSERT_ROW + 1)` を **`INSERT_ROW + 2`** に直す。
移行後は `INSERT_ROW + 1` が広告行（数式なし）になり、コピー元として使えないため。

- [ ] **Step 1: 現在の実装を確認する**

```bash
cd /Users/wadaatsushi/Documents/automation/marketar/listing-creator
grep -n "insert_row\|copy_formula_columns\|INSERT_ROW" write_sales_sheet.py
```

- [ ] **Step 2: 2行挿入に変える**

`sales_ws.insert_row([], index=INSERT_ROW)` を次に置き換える:

```python
    # ASIN行と、その直下の広告行。広告経由の売上個数は「売上/日」の広告行に入る
    sales_ws.insert_rows([[], []], row=INSERT_ROW)
    if "商品名" in col_map:
        sales_ws.update_cell(INSERT_ROW + 1, col_map["商品名"], AD_ROW_LABEL)
```

ファイル冒頭の定数群に追加:

```python
AD_ROW_LABEL = "広告経由"
```

- [ ] **Step 3: 数式のコピー元をずらす**

```python
    copy_formula_columns(sales_ws, target_row=INSERT_ROW, source_start_row=INSERT_ROW + 1)
```

を次に変える:

```python
    # INSERT_ROW + 1 は広告行で数式が入っていないため、その下から拾う
    copy_formula_columns(sales_ws, target_row=INSERT_ROW, source_start_row=INSERT_ROW + 2)
```

- [ ] **Step 4: 既存テストを走らせる**

```bash
cd /Users/wadaatsushi/Documents/automation/marketar/listing-creator
.venv/bin/python -m pytest src/tests/ -v
```

Expected: 全 PASS（落ちたテストがあれば、期待値を2行挿入に合わせて直す）

- [ ] **Step 5: コミット**

`marketar/listing-creator/pyproject.toml` の version を MINOR 更新してから:

```bash
cd /Users/wadaatsushi/Documents/automation
git add marketar/listing-creator/write_sales_sheet.py marketar/listing-creator/pyproject.toml
git diff --cached --name-only
git commit -m "feat(listing): 売上/日 の新規行に広告行も作る"
```

---

### Task 12: 全体の受け入れ確認

**Files:**
- Modify: `/Users/wadaatsushi/Documents/automation/CLAUDE.md`

- [ ] **Step 1: spec の受け入れ基準を1つずつ確かめる**

```bash
cd /Users/wadaatsushi/Documents/automation/data-engineer/download-amazon-data
.venv/bin/python -m pytest py_tests/ -v
.venv/bin/python insert_ad_rows.py --dry-run          # 0 件
launchctl print gui/$(id -u)/com.automation.download-amazon-data-ads | grep -E "runs|last exit code"
```

シート上で確認:

1. 「売上/日」が148行になり、再実行しても増えない
2. 広告行の直近14日と過去90日に値が入り、売上行の値・ノート・総売上・日付ラベルが無傷
3. 「売上/今」の個数・売上が商品名と同じ行に並ぶ
4. 広告経由の個数が同じ日の売上個数を超えていない

- [ ] **Step 2: 翌日の定期実行を確認する**

翌朝、`~/Library/Logs/download-amazon-data-ads.log` と Obsidian daily note の
「## 定期実行ログ」で、1:00 の売上ジョブと 2:00 の広告ジョブがどちらも成功していることを見る。

**売上ジョブが失敗した日は、その日の日付列が無いので広告ジョブはその日をスキップする**
（異常ではない）。翌日 `backfill_ad_sales.py <その日> <その日>` で埋める。

- [ ] **Step 3: 親リポジトリの `CLAUDE.md` に追記する**

「### 13. 売上/日の画像列は画像登録の後で埋める」の後ろに節を足す:

```markdown
### 売上/日 は ASIN 1件につき2行

各 ASIN 行の直下に**広告行**がある。A列は空、商品名列に「広告経由」、薄いグレー。
`main.py ads`（毎日 2:00）が広告経由の売上個数を書く。詳細は
`data-engineer/download-amazon-data/CLAUDE.md`。

- **ASIN で行を探すスクリプトは影響を受けない**（広告行の A列は空）
- **行番号で特定してはいけない。** 新商品追加のたびに2行ずつ増える
- 新商品を足すときは `write_sales_sheet.py` が2行挿入する。手で1行だけ足さないこと
```

- [ ] **Step 4: コミット**

```bash
cd /Users/wadaatsushi/Documents/automation
git add CLAUDE.md
git diff --cached --name-only
git commit -m "docs: 売上/日 が ASIN 1件につき2行になったことを追記"
```
