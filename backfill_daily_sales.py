from __future__ import annotations
import os
import sys
from datetime import datetime, timedelta, timezone

import gspread
from dotenv import load_dotenv
from gspread.utils import rowcol_to_a1
from oauth2client.service_account import ServiceAccountCredentials

from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator
from py_src.infrastructure.api.sp_api_sales_repository import SpApiSalesRepository
from py_src.infrastructure.sheets.sales_sheet import (
    SalesSheet,
    HEADER_ROW,
    apply_date_label_format,
)

JST = timezone(timedelta(hours=9))
SHEETS_EPOCH = datetime(1899, 12, 30)


def main() -> None:
    target_dates = sorted(sys.argv[1:])
    if not target_dates:
        print("Usage: python backfill_daily_sales.py YYYY-MM-DD [YYYY-MM-DD ...]")
        sys.exit(1)

    load_dotenv()
    authenticator = SpApiAuthenticator(
        client_id=os.getenv("API_KEY", ""),
        client_secret=os.getenv("API_SECRET", ""),
        refresh_token=os.getenv("REFRESH_TOKEN", ""),
    )
    authenticator.authenticate()
    sales_repository = SpApiSalesRepository(authenticator=authenticator)

    spreadsheet = _open_spreadsheet()
    worksheet = spreadsheet.worksheet("売上/日")
    sales_sheet = SalesSheet(sales_worksheet=worksheet)
    asin_list = sales_sheet.get_asin_list()
    print(f"対象ASIN: {len(asin_list)}件")

    for target_date_str in target_dates:
        _backfill_one_day(
            worksheet, sales_sheet, asin_list, sales_repository, target_date_str,
        )


def _backfill_one_day(worksheet, sales_sheet, asin_list, sales_repository, target_date_str):
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").replace(tzinfo=JST)
    next_day = target_date + timedelta(days=1)
    start_date_utc = target_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_date_utc = next_day.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    label_serial = _date_serial(target_date)

    print(f"[{target_date_str}] SP-API 取得中... (シリアル: {label_serial})")
    asin_sales = sales_repository.get_daily_sales(asin_list, start_date_utc, end_date_utc)

    col = sales_sheet._resolve_column_for(label_serial)

    _write_sales_to_column(worksheet, sales_sheet, asin_list, asin_sales, label_serial, col)
    print(f"[{target_date_str}] 完了: {sum(1 for s in asin_sales.values() if s.unit_count > 0)}件販売あり")


def _write_sales_to_column(worksheet, sales_sheet, asin_list, asin_sales, label_serial, col):
    requests: list[dict] = []
    requests.append({"range": rowcol_to_a1(1, col), "values": [[label_serial]]})
    requests.append({"range": rowcol_to_a1(HEADER_ROW, col), "values": [[label_serial]]})

    total_amount = 0.0
    for asin in asin_list:
        if asin not in asin_sales:
            continue
        sales = asin_sales[asin]
        for row in sales_sheet._asin_to_rows[asin]:
            if row != 3:
                requests.append({"range": rowcol_to_a1(row, col), "values": [[sales.unit_count]]})
        total_amount += sales.total_sales_amount
    requests.append({"range": rowcol_to_a1(3, col), "values": [[total_amount]]})

    worksheet.batch_update(requests, value_input_option="RAW")
    apply_date_label_format(worksheet, col)


def _date_serial(jst_datetime: datetime) -> int:
    naive = datetime(jst_datetime.year, jst_datetime.month, jst_datetime.day)
    return (naive - SHEETS_EPOCH).days


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
