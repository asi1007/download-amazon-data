"""広告経由・粗利益・広告費を折りたたむ（行グループ）。

    .venv/bin/python apply_row_groups.py

たたんだ状態でも ASIN行（売上個数）と営業利益は見えたままになる。
"""
from __future__ import annotations
import os

from dotenv import load_dotenv

from sales_data.infrastructure.sheets.row_groups import RowGroups
from sales_data.infrastructure.sheets.spreadsheet_client import open_spreadsheet

SHEET_NAME = "売上/日"


def main() -> None:
    load_dotenv()
    spreadsheet = open_spreadsheet(
        os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json"),
        os.getenv("SPREADSHEET_ID"),
    )
    count = RowGroups(spreadsheet.worksheet(SHEET_NAME)).collapse_label_rows()
    print(f"行グループを {count} 件作り、折りたたみました")


if __name__ == "__main__":
    main()
