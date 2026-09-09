"""旧「カテゴリランキング」シートの順位を「売上/日」の順位行へ移す。1回限り。

    .venv/bin/python migrate_category_ranks.py [--dry-run]

売上/日 に日付列が無い日は移せないので、落とした日付を最後に出す。
移行が済んだらこのスクリプトは消す（旧シートが無くなると再実行できない）。
"""
from __future__ import annotations
import os
import sys
from datetime import date

from dotenv import load_dotenv
from gspread.utils import rowcol_to_a1

from py_src.infrastructure.sheets.label_rows import (
    PRODUCT_NAME_HEADER,
    RANK_ROW_LABEL,
    bind_label_rows,
    date_serial,
    find_column,
)
from py_src.infrastructure.sheets.rank_sheet import RankSheet
from py_src.infrastructure.sheets.spreadsheet_client import open_spreadsheet
from py_src.usecases.build_rank_updates import category_of, rank_label

SHEET_NAME = "売上/日"
OLD_SHEET_NAME = "カテゴリランキング"
COL_ASIN = 1
COL_CATEGORY = 4
FIXED_COLUMNS = 4
SERIAL_MIN = 40000
SERIAL_MAX = 60000


def build_migration_updates(
    old_table: list[list[str]],
    asin_values: list[str],
    name_values: list[str],
    header: list[object],
) -> tuple[list[dict], list[str]]:
    if not old_table or not old_table[0]:
        return [], []
    days = [cell.strip() for cell in old_table[0][FIXED_COLUMNS:]]
    columns = _date_columns(header)
    rows = bind_label_rows(asin_values, name_values, RANK_ROW_LABEL)
    name_column = find_column(header, PRODUCT_NAME_HEADER)

    updates: list[dict] = []
    dropped: list[str] = []
    for old_row in old_table[1:]:
        asin = _at(old_row, COL_ASIN)
        target_rows = rows.get(asin)
        if not asin or not target_rows:
            continue
        for row in target_rows:
            _append_label(updates, old_row, row, name_column, name_values)
            _append_ranks(updates, dropped, old_row, days, columns, row)
    return updates, dropped


def _append_ranks(
    updates: list[dict],
    dropped: list[str],
    old_row: list[str],
    days: list[str],
    columns: dict[int, int],
    row: int,
) -> None:
    for index, day in enumerate(days):
        value = _at(old_row, FIXED_COLUMNS + index + 1)
        if not value:
            continue
        column = columns.get(date_serial(date.fromisoformat(day)))
        if column is None:
            if day not in dropped:
                dropped.append(day)
            continue
        updates.append({"range": rowcol_to_a1(row, column), "values": [[int(value)]]})


def _append_label(
    updates: list[dict],
    old_row: list[str],
    row: int,
    name_column: int,
    name_values: list[str],
) -> None:
    category = _at(old_row, COL_CATEGORY)
    if not category:
        return
    current = name_values[row - 1] if row - 1 < len(name_values) else ""
    if category_of(current) == category:
        return
    updates.append(
        {"range": rowcol_to_a1(row, name_column), "values": [[rank_label(category)]]}
    )


def _date_columns(header: list[object]) -> dict[int, int]:
    columns: dict[int, int] = {}
    for index, value in enumerate(header, start=1):
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if SERIAL_MIN < value < SERIAL_MAX:
            columns.setdefault(value, index)
    return columns


def _at(row: list[str], column: int) -> str:
    return row[column - 1].strip() if len(row) >= column else ""


def main() -> None:
    load_dotenv()
    dry_run = "--dry-run" in sys.argv
    spreadsheet = open_spreadsheet(
        os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json"),
        os.getenv("SPREADSHEET_ID"),
    )
    sheet = RankSheet(worksheet=spreadsheet.worksheet(SHEET_NAME))
    asin_values, name_values, header = sheet.read_grid()
    old_table = spreadsheet.worksheet(OLD_SHEET_NAME).get_all_values()

    updates, dropped = build_migration_updates(
        old_table, asin_values, name_values, header
    )
    print(f"移す件数: {len(updates)} セル")
    if dropped:
        print(
            f"売上/日 に列が無く落とす日付（{len(dropped)}日）: "
            f"{', '.join(sorted(dropped))}"
        )
    if dry_run:
        print("--dry-run のため書き込みません")
        return

    sheet.apply_updates(updates)
    print("移行しました")


if __name__ == "__main__":
    main()
