"""ラベル行（広告経由 / 営業利益 / 粗利益 / 広告費）を ASIN 行の半分の高さにする。

    .venv/bin/python apply_row_heights.py
"""
from __future__ import annotations
import os

from dotenv import load_dotenv

from sales_data.infrastructure.sheets.row_heights import RowHeights
from sales_data.infrastructure.sheets.spreadsheet_client import open_spreadsheet

SHEET_NAME = "売上/日"


def main() -> None:
    load_dotenv()
    spreadsheet = open_spreadsheet(
        os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json"),
        os.getenv("SPREADSHEET_ID"),
    )
    count = RowHeights(spreadsheet.worksheet(SHEET_NAME)).shrink_label_rows()
    print(f"ラベル行 {count} 行の高さを縮めました")


if __name__ == "__main__":
    main()
