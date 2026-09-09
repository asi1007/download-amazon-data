"""ラベル行の並びを ROW_LABELS_IN_ORDER に合わせる。

    .venv/bin/python reorder_label_rows.py

行ごと移動するので中身と書式は失われない。並びが既に正しければ何もしない。
"""
from __future__ import annotations
import os

from dotenv import load_dotenv

from sales_data.infrastructure.sheets.label_row_order import LabelRowOrder
from sales_data.infrastructure.sheets.spreadsheet_client import open_spreadsheet

SHEET_NAME = "売上/日"


def main() -> None:
    load_dotenv()
    spreadsheet = open_spreadsheet(
        os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json"),
        os.getenv("SPREADSHEET_ID"),
    )
    moved = LabelRowOrder(spreadsheet.worksheet(SHEET_NAME)).reorder()
    print(f"ラベル行を {moved} 回移動しました")


if __name__ == "__main__":
    main()
