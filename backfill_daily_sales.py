from __future__ import annotations
import os
import sys
from datetime import date, datetime, timedelta, timezone

import gspread
from dotenv import load_dotenv

from py_src.domain.repositories.sales_repository import SalesRepository
from py_src.domain.value_objects.gross_profit_write_result import GrossProfitWriteResult
from py_src.domain.value_objects.sales_info import SalesInfo
from py_src.domain.value_objects.unit_costs import UnitCosts, estimate_gross_profit
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator
from py_src.infrastructure.api.sp_api_sales_repository import SpApiSalesRepository
from py_src.infrastructure.sheets.sales_sheet import SalesSheet
from py_src.infrastructure.sheets.spreadsheet_client import open_spreadsheet
from py_src.infrastructure.sheets.unit_cost_reader import UnitCostReader

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

    # 費用（販売手数料・FBA手数料・原価）は日付に依らないため、日数分読み直さず
    # ループの前に1度だけ読む。
    costs = UnitCostReader(worksheet).read()

    for target_date_str in target_dates:
        _backfill_one_day(
            sales_sheet, asin_list, sales_repository, target_date_str, costs,
        )


def _backfill_one_day(
    sales_sheet: SalesSheet,
    asin_list: list[str],
    sales_repository: SalesRepository,
    target_date_str: str,
    costs: dict[str, UnitCosts],
) -> None:
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").replace(tzinfo=JST)
    next_day = target_date + timedelta(days=1)
    start_date_utc = target_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_date_utc = next_day.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    label_serial = _date_serial(target_date)

    print(f"[{target_date_str}] SP-API 取得中... (シリアル: {label_serial})")
    asin_sales = sales_repository.get_daily_sales(asin_list, start_date_utc, end_date_utc)

    sales_sheet.write_sales_nums(asin_sales, target_date=target_date.date())
    profit_result = _write_gross_profit(sales_sheet, asin_sales, costs, target_date.date())
    print(f"[{target_date_str}] 完了: {sum(1 for s in asin_sales.values() if s.unit_count > 0)}件販売あり")
    print(f"[{target_date_str}] 粗利益: {profit_result.cells_written} セル")
    if profit_result.asins_without_row:
        print(
            f"[{target_date_str}] 粗利益の行が無い ASIN"
            f"（{len(profit_result.asins_without_row)}件）: "
            f"{', '.join(profit_result.asins_without_row)}"
        )


def _write_gross_profit(
    sales_sheet: SalesSheet,
    asin_sales: dict[str, SalesInfo],
    costs: dict[str, UnitCosts],
    target_date: date,
) -> GrossProfitWriteResult:
    profits = {
        asin: profit
        for asin, sales in asin_sales.items()
        if (profit := estimate_gross_profit(sales, costs.get(asin, UnitCosts()))) is not None
    }
    return sales_sheet.write_gross_profit(profits, target_date)


def _date_serial(jst_datetime: datetime) -> int:
    naive = datetime(jst_datetime.year, jst_datetime.month, jst_datetime.day)
    return (naive - SHEETS_EPOCH).days


def _open_spreadsheet() -> gspread.Spreadsheet:
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    return open_spreadsheet(credentials_file, spreadsheet_id)


if __name__ == "__main__":
    main()
