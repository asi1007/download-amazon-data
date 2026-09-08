"""売上個数セルの背景を、記録済みの価格ノートから塗り直す。既存の日付列すべてが対象。

    .venv/bin/python recolor_price_changes.py [--dry-run]

値上げ＝青、値下げ＝赤。変化なしのセルと、前日の価格ノートが無いセルは触らない。
"""
from __future__ import annotations
import os
import sys

from dotenv import load_dotenv

from py_src.infrastructure.sheets.sales_sheet import SalesSheet
from py_src.infrastructure.sheets.spreadsheet_client import open_spreadsheet

SHEET_NAME = "売上/日"


def main() -> None:
    load_dotenv()
    dry_run = "--dry-run" in sys.argv
    spreadsheet = open_spreadsheet(
        os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json"),
        os.getenv("SPREADSHEET_ID"),
    )
    sheet = SalesSheet(sales_worksheet=spreadsheet.worksheet(SHEET_NAME))
    asin_list = sheet.get_asin_list()
    print(f"対象ASIN: {len(asin_list)}件")

    if dry_run:
        cells = sheet.classify_price_changes()
        print("--dry-run のため書き込みません")
    else:
        cells = sheet.recolor_price_changes()
    print(f"値上げ（青）: {len(cells.pricier)} セル")
    print(f"値下げ（赤）: {len(cells.cheaper)} セル")
    print(f"変化なし（塗らない）: {len(cells.unchanged)} セル")


if __name__ == "__main__":
    main()
