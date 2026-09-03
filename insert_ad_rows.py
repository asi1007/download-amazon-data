from __future__ import annotations
import os
import sys
from pathlib import Path

import gspread
from dotenv import load_dotenv
from gspread.utils import rowcol_to_a1
from oauth2client.service_account import ServiceAccountCredentials

from py_src.infrastructure.sheets.ad_sales_sheet import (
    AD_ROW_LABEL,
    ASIN_COLUMN,
    ASIN_LENGTH,
    HEADER_ROW,
    PRODUCT_NAME_HEADER,
)

SHEET_NAME = "売上/日"
AD_ROW_BACKGROUND = {"backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95}}


def plan_ad_row_insertions(asin_values: list[str], name_values: list[str]) -> list[int]:
    targets: list[int] = []
    total = max(len(asin_values), len(name_values))
    for index in range(total):
        asin = asin_values[index].strip() if index < len(asin_values) else ""
        if len(asin) != ASIN_LENGTH:
            continue
        below = index + 1
        name_below = name_values[below].strip() if below < len(name_values) else ""
        asin_below = asin_values[below].strip() if below < len(asin_values) else ""
        already_has_ad_row = not asin_below and name_below == AD_ROW_LABEL
        if already_has_ad_row:
            continue
        targets.append(index + 1)
    return sorted(targets, reverse=True)


def build_insert_requests(sheet_id: int, insert_rows: list[int]) -> list[dict]:
    return [
        {
            "insertDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": row,
                    "endIndex": row + 1,
                },
                "inheritFromBefore": False,
            }
        }
        for row in insert_rows
    ]


def _open_worksheet() -> gspread.Worksheet:
    load_dotenv()
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(os.getenv("SPREADSHEET_ID"))
    return spreadsheet.worksheet(SHEET_NAME)


def _find_column(headers: list[str], name: str) -> int:
    for index, value in enumerate(headers, start=1):
        if str(value).strip() == name:
            return index
    raise ValueError(f"ヘッダーに '{name}' が見つかりません")


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    worksheet = _open_worksheet()
    headers = worksheet.row_values(HEADER_ROW)
    name_column = _find_column(headers, PRODUCT_NAME_HEADER)
    asin_values = worksheet.col_values(ASIN_COLUMN)
    name_values = worksheet.col_values(name_column)

    insert_rows = plan_ad_row_insertions(asin_values, name_values)
    print(f"広告行を挿入する対象: {len(insert_rows)} 件")
    for row in reversed(insert_rows):
        print(f"  行{row} ({asin_values[row - 1].strip()}) の直下")
    if dry_run or not insert_rows:
        return

    worksheet.spreadsheet.batch_update(
        {"requests": build_insert_requests(worksheet.id, insert_rows)}
    )

    label_column_letter = rowcol_to_a1(1, name_column).rstrip("1")
    ad_rows = _ad_row_numbers(insert_rows)
    worksheet.batch_update(
        [
            {"range": f"{label_column_letter}{row}", "values": [[AD_ROW_LABEL]]}
            for row in ad_rows
        ],
        value_input_option="RAW",
    )
    worksheet.batch_format(
        [
            {"range": f"A{row}:{label_column_letter}{row}", "format": AD_ROW_BACKGROUND}
            for row in ad_rows
        ]
    )
    print(f"広告行を {len(ad_rows)} 行入れました")


def _ad_row_numbers(insert_rows: list[int]) -> list[int]:
    # 昇順に見ると、i 番目の挿入位置は自分より上に入った i 行分だけ下へずれる
    ascending = sorted(insert_rows)
    return [row + offset + 1 for offset, row in enumerate(ascending)]


if __name__ == "__main__":
    main()
