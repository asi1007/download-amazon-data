"""営業利益の行に数式を入れ直す。既存の日付列すべてが対象。

    .venv/bin/python backfill_operating_profit.py [--days N]

`--days N` を付けると直近 N 日分の列だけに絞る（既定は全列）。
"""
from __future__ import annotations
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from sales_data.infrastructure.sheets.layout import date_serial, read_date_columns
from sales_data.infrastructure.sheets.repository import SheetsSalesRepository
from sales_data.infrastructure.sheets.spreadsheet_client import open_spreadsheet

JST = timezone(timedelta(hours=9))
SHEET_NAME = "売上/日"


def _recent_serials(days: int) -> set[int]:
    today = datetime.now(JST).date()
    return {date_serial(today - timedelta(days=n)) for n in range(days)}


def main() -> None:
    load_dotenv()
    days = None
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    spreadsheet = open_spreadsheet(
        os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json"),
        os.getenv("SPREADSHEET_ID"),
    )
    worksheet = spreadsheet.worksheet(SHEET_NAME)
    columns_by_serial = read_date_columns(worksheet)
    if days is not None:
        wanted = _recent_serials(days)
        columns_by_serial = {s: c for s, c in columns_by_serial.items() if s in wanted}
    columns = sorted(columns_by_serial.values())
    print(f"対象の日付列: {len(columns)} 列")
    written = SheetsSalesRepository(sales_worksheet=worksheet).write_operating_profit_formulas(columns)
    print(f"営業利益の数式を {written} セルに入れました")


if __name__ == "__main__":
    main()
