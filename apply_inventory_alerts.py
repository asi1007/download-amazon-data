"""在庫日数の警告色を掛け直し、周辺のセルを普通の色に戻す。

    .venv/bin/python apply_inventory_alerts.py
"""
from __future__ import annotations
import os

from dotenv import load_dotenv

from py_src.infrastructure.sheets.inventory_alerts import InventoryAlerts
from py_src.infrastructure.sheets.spreadsheet_client import open_spreadsheet

SHEET_NAME = "売上/日"


def main() -> None:
    load_dotenv()
    spreadsheet = open_spreadsheet(
        os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json"),
        os.getenv("SPREADSHEET_ID"),
    )
    count = InventoryAlerts(spreadsheet.worksheet(SHEET_NAME)).apply()
    print(f"在庫日数の警告を {count} 件設定しました")


if __name__ == "__main__":
    main()
