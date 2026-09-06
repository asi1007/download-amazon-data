"""売上/日 の個数行と営業利益行にグラデーションを掛け直す。

    .venv/bin/python apply_gradients.py

商品ごとに独立したスケールにする。全商品を1つのスケールに載せると、
販売数の多い商品以外がすべて同じ色になって読めないため。
"""
from __future__ import annotations
import os

from dotenv import load_dotenv

from py_src.infrastructure.sheets.gradient_rules import GradientRules
from py_src.infrastructure.sheets.spreadsheet_client import open_spreadsheet

SHEET_NAME = "売上/日"


def main() -> None:
    load_dotenv()
    spreadsheet = open_spreadsheet(
        os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json"),
        os.getenv("SPREADSHEET_ID"),
    )
    count = GradientRules(spreadsheet.worksheet(SHEET_NAME)).apply()
    print(f"条件付き書式を {count} 件設定しました")


if __name__ == "__main__":
    main()
