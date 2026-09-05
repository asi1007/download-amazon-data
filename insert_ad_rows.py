from __future__ import annotations
import os
import sys

import gspread
from dotenv import load_dotenv

from py_src.infrastructure.sheets.label_rows import (
    ASIN_COLUMN,
    ASIN_LENGTH,
    HEADER_ROW,
    PRODUCT_NAME_HEADER,
    ROW_LABELS_IN_ORDER,
    find_column,
)
from py_src.infrastructure.sheets.retry import retry_on_transient_error
from py_src.infrastructure.sheets.spreadsheet_client import open_spreadsheet

SHEET_NAME = "売上/日"
LABEL_ROW_BACKGROUND = {"backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95}}


def existing_label_run(index: int, name_values: list[str]) -> int:
    run = 0
    for offset, label in enumerate(ROW_LABELS_IN_ORDER, start=1):
        position = index + offset
        name = name_values[position].strip() if position < len(name_values) else ""
        if name != label:
            break
        run += 1
    return run


def plan_label_row_insertions(
    asin_values: list[str], name_values: list[str]
) -> list[tuple[int, int]]:
    plan: list[tuple[int, int]] = []
    for index, value in enumerate(asin_values):
        if len(value.strip()) != ASIN_LENGTH:
            continue
        run = existing_label_run(index, name_values)
        missing = len(ROW_LABELS_IN_ORDER) - run
        if missing:
            plan.append((index + 1 + run, missing))
    return sorted(plan, reverse=True)


def build_insert_requests(sheet_id: int, plan: list[tuple[int, int]]) -> list[dict]:
    return [
        {
            "insertDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": row,
                    "endIndex": row + count,
                },
                "inheritFromBefore": False,
            }
        }
        for row, count in plan
    ]


def label_row_numbers(plan: list[tuple[int, int]]) -> list[tuple[int, str]]:
    ascending = sorted(plan)
    numbered: list[tuple[int, str]] = []
    shift = 0
    for row, count in ascending:
        for offset in range(count):
            label = ROW_LABELS_IN_ORDER[len(ROW_LABELS_IN_ORDER) - count + offset]
            numbered.append((row + shift + offset + 1, label))
        shift += count
    return numbered


def _open_worksheet() -> gspread.Worksheet:
    load_dotenv()
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
    spreadsheet = open_spreadsheet(credentials_file, os.getenv("SPREADSHEET_ID"))
    return spreadsheet.worksheet(SHEET_NAME)


@retry_on_transient_error
def _apply_label_row_plan(worksheet: gspread.Worksheet, name_column: int) -> list[tuple[int, str]]:
    # 呼び出しのたびに読み直して計画を立て直す。@retry_on_transient_error はこの関数
    # ごと再試行するため、「行の挿入(spreadsheet.batch_update)は成功したがラベル書き込み
    # (worksheet.batch_update)で失敗」のような部分失敗が起きても、リトライ時はその時点の
    # シート状態から再計画する。これにより同じ ASIN の下にラベル行が二重に挿入されることを防ぐ。
    asin_values = worksheet.col_values(ASIN_COLUMN)
    name_values = worksheet.col_values(name_column)
    plan = plan_label_row_insertions(asin_values, name_values)
    if not plan:
        return []

    worksheet.spreadsheet.batch_update({"requests": build_insert_requests(worksheet.id, plan)})

    labeled_rows = label_row_numbers(plan)
    label_column_letter = gspread.utils.rowcol_to_a1(1, name_column).rstrip("1")
    worksheet.batch_update(
        [
            {"range": f"{label_column_letter}{row}", "values": [[label]]}
            for row, label in labeled_rows
        ],
        value_input_option="RAW",
    )
    worksheet.batch_format(
        [
            {"range": f"A{row}:{label_column_letter}{row}", "format": LABEL_ROW_BACKGROUND}
            for row, _ in labeled_rows
        ]
    )
    return labeled_rows


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    worksheet = _open_worksheet()
    headers = worksheet.row_values(HEADER_ROW)
    name_column = find_column(headers, PRODUCT_NAME_HEADER)
    asin_values = worksheet.col_values(ASIN_COLUMN)
    name_values = worksheet.col_values(name_column)

    plan = plan_label_row_insertions(asin_values, name_values)
    total_missing = sum(missing for _, missing in plan)
    print(f"ラベル行を挿入する対象: {len(plan)} 件（不足 {total_missing} 行）")
    for row, missing in plan:
        asin_index = row - 1 - (len(ROW_LABELS_IN_ORDER) - missing)
        print(f"  行{row} ({asin_values[asin_index].strip()}) の直下に {missing} 行不足")
    if dry_run or not plan:
        return

    # 実際の書き込みは _apply_label_row_plan が改めて読み直して計画を立て直す（上記コメント参照）。
    labeled_rows = _apply_label_row_plan(worksheet, name_column)
    print(f"ラベル行を {len(labeled_rows)} 行入れました")


if __name__ == "__main__":
    main()
