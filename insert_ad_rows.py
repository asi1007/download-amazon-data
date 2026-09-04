from __future__ import annotations
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import gspread
from dotenv import load_dotenv
from gspread.utils import rowcol_to_a1

from py_src.infrastructure.sheets.ad_sales_sheet import (
    AD_ROW_LABEL,
    ASIN_COLUMN,
    ASIN_LENGTH,
    HEADER_ROW,
    PRODUCT_NAME_HEADER,
)
from py_src.infrastructure.sheets.retry import retry_on_transient_error
from py_src.infrastructure.sheets.spreadsheet_client import open_spreadsheet

SHEET_NAME = "売上/日"
AD_ROW_BACKGROUND = {"backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95}}


def _each_asin_row_index(asin_values: list[str], name_values: list[str]) -> Iterator[int]:
    total = max(len(asin_values), len(name_values))
    for index in range(total):
        asin = asin_values[index].strip() if index < len(asin_values) else ""
        if len(asin) == ASIN_LENGTH:
            yield index


def _ad_row_status(index: int, asin_values: list[str], name_values: list[str]) -> str:
    below = index + 1
    total = max(len(asin_values), len(name_values))
    asin_below = asin_values[below].strip() if below < len(asin_values) else ""
    name_below = name_values[below].strip() if below < len(name_values) else ""
    if asin_below:
        return "needs_insertion"
    if name_below == AD_ROW_LABEL:
        return "already_labeled"
    if below < total:
        # ASIN・商品名ともに空だが、below行より先(いずれかの列)にまだデータが続いている
        # ＝below行は物理的に実在する。前回実行が「行の挿入(insertDimension)」までは
        # 成功したが「ラベル書き込み」で失敗して中断した状態とみなし、行を再挿入せず
        # ラベル・背景色だけ書き直す（plan_ad_row_recovery 参照）。
        #
        # 既知の限界: 対象ASINがシートの最終行の場合、col_values() は末尾の空セルを
        # 返さないため below >= total となり、この判定では「挿入済みで未ラベル」と
        # 「未挿入」を区別できない（安全側に倒し needs_insertion 扱いにする＝最悪でも
        # 従来通り1行だけ余分に挿入される。全77行が重複する事故は防げる）。
        return "unlabeled_row_exists"
    return "needs_insertion"


def plan_ad_row_insertions(asin_values: list[str], name_values: list[str]) -> list[int]:
    targets = [
        index + 1
        for index in _each_asin_row_index(asin_values, name_values)
        if _ad_row_status(index, asin_values, name_values) == "needs_insertion"
    ]
    return sorted(targets, reverse=True)


def plan_ad_row_recovery(asin_values: list[str], name_values: list[str]) -> list[int]:
    targets = [
        index + 1
        for index in _each_asin_row_index(asin_values, name_values)
        if _ad_row_status(index, asin_values, name_values) == "unlabeled_row_exists"
    ]
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


def _shift_count(row: int, insert_rows: list[int]) -> int:
    return sum(1 for inserted in insert_rows if inserted < row)


def _ad_row_numbers(insert_rows: list[int]) -> list[int]:
    return sorted(row + _shift_count(row, insert_rows) + 1 for row in insert_rows)


def _relabel_row_numbers(recovery_rows: list[int], insert_rows: list[int]) -> list[int]:
    # recovery_rows の行自体は挿入されないが、その上で行われた insert_rows の挿入分だけ
    # 実際の行番号は下へずれる。挿入は startIndex より上の行番号には影響しないため、
    # 「自分より小さい insert_rows の件数」がそのままずれ幅になる（_ad_row_numbers と同じ式）。
    return sorted(row + _shift_count(row, insert_rows) + 1 for row in recovery_rows)


def _open_worksheet() -> gspread.Worksheet:
    load_dotenv()
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
    spreadsheet = open_spreadsheet(credentials_file, os.getenv("SPREADSHEET_ID"))
    return spreadsheet.worksheet(SHEET_NAME)


def _find_column(headers: list[str], name: str) -> int:
    for index, value in enumerate(headers, start=1):
        if str(value).strip() == name:
            return index
    raise ValueError(f"ヘッダーに '{name}' が見つかりません")


@retry_on_transient_error
def _apply_ad_row_plan(worksheet: gspread.Worksheet, name_column: int) -> list[int]:
    # 呼び出しのたびに読み直して計画を立て直す。@retry_on_transient_error はこの関数
    # ごと再試行するため、「行の挿入(spreadsheet.batch_update)は成功したがラベル書き込み
    # (worksheet.batch_update)で失敗」のような部分失敗が起きても、リトライ時は古い計画を
    # 使い回さず、その時点のシート状態（挿入済みだが未ラベルの行）から再計画する。これにより
    # 同じ ASIN の下に広告行が二重に挿入されることを防ぐ。
    asin_values = worksheet.col_values(ASIN_COLUMN)
    name_values = worksheet.col_values(name_column)
    insert_rows = plan_ad_row_insertions(asin_values, name_values)
    recovery_rows = plan_ad_row_recovery(asin_values, name_values)
    if not (insert_rows or recovery_rows):
        return []

    if insert_rows:
        worksheet.spreadsheet.batch_update(
            {"requests": build_insert_requests(worksheet.id, insert_rows)}
        )

    label_column_letter = rowcol_to_a1(1, name_column).rstrip("1")
    ad_rows = sorted(
        _ad_row_numbers(insert_rows) + _relabel_row_numbers(recovery_rows, insert_rows)
    )
    worksheet.batch_update(
        [
            {"range": f"{label_column_letter}{row}", "values": [[AD_ROW_LABEL]]}
            for row in ad_rows
        ],
        value_input_option="RAW",
    )
    worksheet.batch_format(
        [{"range": f"A{row}:{label_column_letter}{row}", "format": AD_ROW_BACKGROUND} for row in ad_rows]
    )
    return ad_rows


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    worksheet = _open_worksheet()
    headers = worksheet.row_values(HEADER_ROW)
    name_column = _find_column(headers, PRODUCT_NAME_HEADER)
    asin_values = worksheet.col_values(ASIN_COLUMN)
    name_values = worksheet.col_values(name_column)

    insert_rows = plan_ad_row_insertions(asin_values, name_values)
    recovery_rows = plan_ad_row_recovery(asin_values, name_values)
    print(f"広告行を新規挿入する対象: {len(insert_rows)} 件")
    for row in reversed(insert_rows):
        print(f"  行{row} ({asin_values[row - 1].strip()}) の直下")
    if recovery_rows:
        print(
            f"前回実行の途中失敗でラベル未設定の行: {len(recovery_rows)} 件"
            "（再挿入せずラベルのみ書き直す）"
        )
        for row in reversed(recovery_rows):
            print(f"  行{row} ({asin_values[row - 1].strip()}) の直下")
    if dry_run or not (insert_rows or recovery_rows):
        return

    # 実際の書き込みは _apply_ad_row_plan が改めて読み直して計画を立て直す（上記コメント参照）。
    ad_rows = _apply_ad_row_plan(worksheet, name_column)
    print(f"広告行を {len(ad_rows)} 行入れました")


if __name__ == "__main__":
    main()
