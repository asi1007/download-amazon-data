from __future__ import annotations
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from amazon_api import spapi_credentials
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from py_src.infrastructure.api.sp_api_authenticator import (
    SpApiAuthenticator,
    SP_API_BASE,
)
from sales_data.infrastructure.sheets.spreadsheet_client import open_spreadsheet
from sales_data.infrastructure.sheets.layout import HEADER_ROW, find_column, ASIN_LENGTH

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
MARKETPLACE_ID = "A1VC38T7YXB528"
FINANCES_MAX_PAGES = 10
ORDERS_MAX_PAGES = 50
SKU_HEADER = "SKU"


def _create_authenticator() -> SpApiAuthenticator:
    credentials = spapi_credentials()
    authenticator = SpApiAuthenticator(
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
        refresh_token=credentials.refresh_token,
    )
    authenticator.authenticate()
    return authenticator


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_finances_api(authenticator: SpApiAuthenticator) -> None:
    print("=== 1. Finances API 疎通確認 ===")
    now = datetime.now(timezone.utc)
    posted_after = now - timedelta(days=7)
    posted_before = now - timedelta(minutes=5)

    fee_type_counts: dict[str, int] = {}
    fee_type_examples: dict[str, list[float]] = {}
    shipment_event_count = 0
    shipment_item_count = 0
    shipment_item_with_sku = 0
    shipment_item_with_fees = 0

    params = {
        "PostedAfter": _iso(posted_after),
        "PostedBefore": _iso(posted_before),
        "MaxResultsPerPage": "100",
    }
    url = f"{SP_API_BASE}/finances/v0/financialEvents?{urlencode(params)}"
    page = 0
    try:
        while url and page < FINANCES_MAX_PAGES:
            page += 1
            response = authenticator.request("GET", url)
            body = response.json()
            payload = body.get("payload", {})
            events = payload.get("FinancialEvents", {})
            shipment_events = events.get("ShipmentEventList", [])
            shipment_event_count += len(shipment_events)
            for shipment_event in shipment_events:
                items = shipment_event.get("ShipmentItemList", [])
                shipment_item_count += len(items)
                for item in items:
                    if item.get("SellerSKU"):
                        shipment_item_with_sku += 1
                    fees = item.get("ItemFeeList", [])
                    if fees:
                        shipment_item_with_fees += 1
                    for fee in fees:
                        fee_type = fee.get("FeeType", "(不明)")
                        amount = fee.get("FeeAmount", {}).get("CurrencyAmount")
                        fee_type_counts[fee_type] = fee_type_counts.get(fee_type, 0) + 1
                        fee_type_examples.setdefault(fee_type, [])
                        if len(fee_type_examples[fee_type]) < 3 and amount is not None:
                            fee_type_examples[fee_type].append(amount)
            next_token = payload.get("NextToken")
            if next_token:
                url = f"{SP_API_BASE}/finances/v0/financialEvents?{urlencode({'NextToken': next_token})}"
            else:
                url = None
    except Exception as error:  # noqa: BLE001 — 疎通確認のため権限エラー等をそのまま報告する
        print(f"Finances API 呼び出しに失敗: {type(error).__name__}: {error}")
        return

    print(f"取得期間: {params['PostedAfter']} 〜 {params['PostedBefore']}（直近7日、最大{FINANCES_MAX_PAGES}ページ）")
    print(f"取得ページ数: {page}")
    print(f"ShipmentEvent 件数: {shipment_event_count}")
    print(f"ShipmentItem 件数: {shipment_item_count}（うち SellerSKU あり: {shipment_item_with_sku}）")
    print(f"ItemFeeList を持つ ShipmentItem: {shipment_item_with_fees}")
    print("FeeType の内訳（件数・金額の符号例）:")
    for fee_type, count in sorted(fee_type_counts.items(), key=lambda kv: -kv[1]):
        examples = fee_type_examples.get(fee_type, [])
        print(f"  {fee_type}: {count}件 例={examples}")


def check_orders_api(authenticator: SpApiAuthenticator) -> None:
    print()
    print("=== 2. 注文件数（1日分） ===")
    now = datetime.now(timezone.utc)
    target_day_start = (now - timedelta(days=2)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    target_day_end = target_day_start + timedelta(days=1)

    params = {
        "MarketplaceIds": MARKETPLACE_ID,
        "CreatedAfter": _iso(target_day_start),
        "CreatedBefore": _iso(target_day_end),
    }
    url = f"{SP_API_BASE}/orders/v0/orders?{urlencode(params)}"
    page = 0
    total_orders = 0
    started_at = datetime.now(timezone.utc)
    try:
        while url and page < ORDERS_MAX_PAGES:
            page += 1
            response = authenticator.request("GET", url)
            body = response.json()
            payload = body.get("payload", {})
            orders = payload.get("Orders", [])
            total_orders += len(orders)
            next_token = payload.get("NextToken")
            if next_token:
                url = f"{SP_API_BASE}/orders/v0/orders?{urlencode({'NextToken': next_token})}"
            else:
                url = None
    except Exception as error:  # noqa: BLE001
        print(f"Orders API 呼び出しに失敗: {type(error).__name__}: {error}")
        return
    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()

    print(f"対象日: {target_day_start.date()}（UTC 日付）")
    print(f"注文件数: {total_orders}件 / ページ数: {page}")
    if page >= ORDERS_MAX_PAGES:
        print(f"警告: 上限 {ORDERS_MAX_PAGES} ページに到達（実際の件数はもっと多い可能性）")
    print(f"1日分の取得にかかった時間: {elapsed:.1f}秒")
    if total_orders > 0:
        seconds_per_order = elapsed / total_orders
        estimate_10000 = seconds_per_order * 10000
        print(
            f"件数あたり {seconds_per_order:.3f}秒 → 14日分が1万件なら概算 {estimate_10000 / 60:.1f}分"
        )
        estimate_14x_today = elapsed * 14
        print(f"今日の件数がそのまま14日続くと仮定した単純14倍: {estimate_14x_today / 60:.1f}分")


def check_sku_column() -> None:
    print()
    print("=== 3. 売上/日 SKU列の欠損率 ===")
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    spreadsheet = open_spreadsheet(credentials_file, spreadsheet_id)
    worksheet = spreadsheet.worksheet("売上/日")

    headers = worksheet.row_values(HEADER_ROW)
    try:
        sku_column = find_column(headers, SKU_HEADER)
    except ValueError:
        print(f"見出し行(行{HEADER_ROW})に「{SKU_HEADER}」列が見つからない: {headers}")
        return

    asin_values = worksheet.col_values(1)
    sku_values = worksheet.col_values(sku_column)
    max_len = max(len(asin_values), len(sku_values))

    total = 0
    na_count = 0
    na_examples: list[str] = []
    asin_row_total = 0
    asin_row_na_count = 0
    asin_row_na_examples: list[str] = []
    for index in range(HEADER_ROW, max_len):
        sku = sku_values[index] if index < len(sku_values) else ""
        asin = asin_values[index] if index < len(asin_values) else ""
        if not sku:
            continue
        total += 1
        is_na = sku.strip() == "#N/A"
        if is_na:
            na_count += 1
            if len(na_examples) < 3 and asin:
                na_examples.append(asin)
        is_asin_row = len(asin) == ASIN_LENGTH and asin.isalnum()
        if is_asin_row:
            asin_row_total += 1
            if is_na:
                asin_row_na_count += 1
                if len(asin_row_na_examples) < 3:
                    asin_row_na_examples.append(asin)

    print(f"SKU列: {SKU_HEADER}（{HEADER_ROW}行目の見出しから列を解決）")
    print(f"SKU列 総数（メモ行・末尾の空行の数式含む）: {total}件 / #N/A: {na_count}件")
    print(f"#N/A の値の例（最大3件、メモ行・空行含む）: {na_examples}")
    print(f"うち ASIN({ASIN_LENGTH}桁英数字)を持つ実商品行のみ: {asin_row_total}件 / #N/A: {asin_row_na_count}件")
    print(f"実商品行で #N/A の ASIN 例（最大3件）: {asin_row_na_examples}")


def main() -> None:
    load_dotenv(ENV_PATH)
    authenticator = _create_authenticator()
    check_finances_api(authenticator)
    check_orders_api(authenticator)
    check_sku_column()


if __name__ == "__main__":
    main()
