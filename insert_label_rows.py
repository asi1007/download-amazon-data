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
from py_src.infrastructure.sheets.row_heights import RowHeights
from py_src.infrastructure.sheets.spreadsheet_client import open_spreadsheet

SHEET_NAME = "売上/日"
LABEL_ROW_BACKGROUND = {"backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95}}


def plan_label_insertions(
    asin_values: list[str], name_values: list[str]
) -> list[tuple[int, list[str]]]:
    # 期待するラベル列と既存のラベル行を先頭から突き合わせ、足りないものを
    # その位置へ挿入する計画にする。営業利益のように**途中**へ入るラベルが
    # あるため、「不足分は末尾」という前提は使えない。
    # 返すのは (挿入前の1起点の行番号, その位置へ入れるラベル) の並び。
    plan: list[tuple[int, list[str]]] = []
    for index, value in enumerate(asin_values):
        if len(value.strip()) != ASIN_LENGTH:
            continue
        cursor = index + 1
        pending: list[str] = []
        for label in ROW_LABELS_IN_ORDER:
            name = name_values[cursor].strip() if cursor < len(name_values) else ""
            if name == label:
                if pending:
                    plan.append((cursor + 1, pending))
                    pending = []
                cursor += 1
                continue
            # 挿入する行は既存の行を押し下げるだけなので cursor は進めない。
            # 次の期待ラベルは同じ既存行と突き合わせる
            pending.append(label)
        if pending:
            plan.append((cursor + 1, pending))
    return sorted(plan, reverse=True)


def build_insert_requests(sheet_id: int, plan: list[tuple[int, list[str]]]) -> list[dict]:
    return [
        {
            "insertDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": row - 1,
                    "endIndex": row - 1 + len(labels),
                },
                "inheritFromBefore": False,
            }
        }
        for row, labels in plan
    ]


def label_row_numbers(plan: list[tuple[int, list[str]]]) -> list[tuple[int, str]]:
    # 挿入は行番号の降順で送るので、ある挿入より前に適用されるのは自分より
    # 下の行の挿入だけ。よって自分の最終行番号は「自分より上で挿入された行数」
    # だけずれる。昇順に走査して累積すればよい
    numbered: list[tuple[int, str]] = []
    shift = 0
    for row, labels in sorted(plan):
        for offset, label in enumerate(labels):
            numbered.append((row + shift + offset, label))
        shift += len(labels)
    return numbered


def _label_grid_range(sheet_id: int, row: int, name_column: int) -> dict:
    # Sheets API の GridRange は0起点。label_row_numbers が返す行番号は1起点なので
    # ここで -1 する（endRowIndex は exclusive なのでそのまま row を使う）。
    return {
        "sheetId": sheet_id,
        "startRowIndex": row - 1,
        "endRowIndex": row,
        "startColumnIndex": name_column - 1,
        "endColumnIndex": name_column,
    }


def build_label_requests(
    sheet_id: int, name_column: int, labeled_rows: list[tuple[int, str]]
) -> list[dict]:
    return [
        {
            "updateCells": {
                "range": _label_grid_range(sheet_id, row, name_column),
                "rows": [{"values": [{"userEnteredValue": {"stringValue": label}}]}],
                "fields": "userEnteredValue",
            }
        }
        for row, label in labeled_rows
    ]


def build_background_requests(
    sheet_id: int, name_column: int, labeled_rows: list[tuple[int, str]]
) -> list[dict]:
    return [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row - 1,
                    "endRowIndex": row,
                    "startColumnIndex": 0,
                    "endColumnIndex": name_column,
                },
                "cell": {"userEnteredFormat": LABEL_ROW_BACKGROUND},
                "fields": "userEnteredFormat.backgroundColor",
            }
        }
        for row, _ in labeled_rows
    ]


def _open_worksheet() -> gspread.Worksheet:
    load_dotenv()
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
    spreadsheet = open_spreadsheet(credentials_file, os.getenv("SPREADSHEET_ID"))
    return spreadsheet.worksheet(SHEET_NAME)


@retry_on_transient_error
def _apply_label_row_plan(worksheet: gspread.Worksheet, name_column: int) -> list[tuple[int, str]]:
    # 呼び出しのたびに読み直して計画を立て直す。行の挿入・ラベル書き込み・背景色は
    # すべて1回の spreadsheet.batch_update にまとめて送る（原子的に適用される）ため、
    # 「挿入だけ成功してラベル書き込みが失敗する」という部分状態は起こらない。
    # @retry_on_transient_error による再試行時も、シートは「まだ何も反映されていない
    # 状態」のまま読み直すことになり、同じ計画を立てても二重挿入にはならない。
    asin_values = worksheet.col_values(ASIN_COLUMN)
    name_values = worksheet.col_values(name_column)
    plan = plan_label_insertions(asin_values, name_values)
    if not plan:
        return []

    labeled_rows = label_row_numbers(plan)
    requests = (
        build_insert_requests(worksheet.id, plan)
        + build_label_requests(worksheet.id, name_column, labeled_rows)
        + build_background_requests(worksheet.id, name_column, labeled_rows)
    )
    worksheet.spreadsheet.batch_update({"requests": requests})
    return labeled_rows


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    worksheet = _open_worksheet()
    headers = worksheet.row_values(HEADER_ROW)
    name_column = find_column(headers, PRODUCT_NAME_HEADER)
    asin_values = worksheet.col_values(ASIN_COLUMN)
    name_values = worksheet.col_values(name_column)

    plan = plan_label_insertions(asin_values, name_values)
    total_missing = sum(len(labels) for _, labels in plan)
    print(f"ラベル行を挿入する箇所: {len(plan)} 件（合計 {total_missing} 行）")
    for row, labels in sorted(plan):
        print(f"  行{row} の位置へ {', '.join(labels)}")
    if dry_run or not plan:
        return

    # 実際の書き込みは _apply_label_row_plan が改めて読み直して計画を立て直す（上記コメント参照）。
    labeled_rows = _apply_label_row_plan(worksheet, name_column)
    print(f"ラベル行を {len(labeled_rows)} 行入れました")
    # 挿入した行は ASIN 行と同じ高さで入る。縮めておかないと1商品が縦に長くなる
    shrunk = RowHeights(worksheet).shrink_label_rows()
    print(f"ラベル行 {shrunk} 行の高さを縮めました")


if __name__ == "__main__":
    main()
