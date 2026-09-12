from __future__ import annotations
import os
import sys

import gspread
from dotenv import load_dotenv

from sales_data.infrastructure.sheets.layout import (
    ASIN_COLUMN,
    ASIN_LENGTH,
    HEADER_ROW,
    PRODUCT_NAME_HEADER,
    ROW_LABELS_IN_ORDER,
    find_column,
    matches_label,
)
from sales_data.infrastructure.sheets.retry import retry_on_transient_error
from sales_data.infrastructure.sheets.row_groups import RowGroups
from sales_data.infrastructure.sheets.row_heights import RowHeights
from sales_data.infrastructure.sheets.spreadsheet_client import open_spreadsheet

SHEET_NAME = "売上/日"
BLACK = {"red": 0.0, "green": 0.0, "blue": 0.0}
# 挿入した行は直前の商品行から文字色を受け継ぐ。手で黄色を付けた商品ブロックでは
# うすい灰色の背景に黄色の文字が乗って読めなくなるので、文字色も黒で固定する。
# foregroundColorStyle まで書くのは、スタイル側の指定が残っていると
# そちらが勝って黄色のままになるため
LABEL_ROW_FORMAT = {
    "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
    "textFormat": {"foregroundColor": BLACK, "foregroundColorStyle": {"rgbColor": BLACK}},
}
LABEL_ROW_FORMAT_FIELDS = (
    "userEnteredFormat.backgroundColor,"
    "userEnteredFormat.textFormat.foregroundColor,"
    "userEnteredFormat.textFormat.foregroundColorStyle"
)


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
            # 順位行はラベルにカテゴリ名が入る。完全一致で見ると毎回「無い」と
            # 判定され、実行のたびに1本ずつ増える
            if matches_label(name, label):
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


def find_label_rows(
    asin_values: list[str], name_values: list[str]
) -> list[tuple[int, str]]:
    # 既に入っているラベル行を洗い出す。A列に手書きのメモだけが入る行があるので、
    # 商品名列がラベルと一致することを条件にする
    rows: list[tuple[int, str]] = []
    for index, value in enumerate(name_values):
        asin = asin_values[index].strip() if index < len(asin_values) else ""
        if len(asin) == ASIN_LENGTH:
            continue
        name = value.strip()
        if any(matches_label(name, label) for label in ROW_LABELS_IN_ORDER):
            rows.append((index + 1, name))
    return rows


def build_format_requests(
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
                "cell": {"userEnteredFormat": LABEL_ROW_FORMAT},
                "fields": LABEL_ROW_FORMAT_FIELDS,
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
        + build_format_requests(worksheet.id, name_column, labeled_rows)
    )
    worksheet.spreadsheet.batch_update({"requests": requests})
    return labeled_rows


# 塗り直しは既存のラベル行ぜんぶが対象になるので数百リクエストになる。
# 1回のペイロードが膨らんで 400 が返らないよう分割して送る
REPAINT_CHUNK_SIZE = 200


@retry_on_transient_error
def _repaint_label_rows(worksheet: gspread.Worksheet, name_column: int) -> int:
    asin_values = worksheet.col_values(ASIN_COLUMN)
    name_values = worksheet.col_values(name_column)
    label_rows = find_label_rows(asin_values, name_values)
    requests = build_format_requests(worksheet.id, name_column, label_rows)
    for start in range(0, len(requests), REPAINT_CHUNK_SIZE):
        worksheet.spreadsheet.batch_update(
            {"requests": requests[start:start + REPAINT_CHUNK_SIZE]}
        )
    return len(label_rows)


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    worksheet = _open_worksheet()
    headers = worksheet.row_values(HEADER_ROW)
    name_column = find_column(headers, PRODUCT_NAME_HEADER)
    asin_values = worksheet.col_values(ASIN_COLUMN)
    name_values = worksheet.col_values(name_column)

    if "--repaint" in sys.argv:
        label_rows = find_label_rows(asin_values, name_values)
        print(f"塗り直すラベル行: {len(label_rows)} 行")
        if dry_run:
            return
        print(f"ラベル行 {_repaint_label_rows(worksheet, name_column)} 行を塗り直しました")
        return

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
    grouped = RowGroups(worksheet).collapse_label_rows()
    print(f"行グループを {grouped} 件作り、折りたたみました")


if __name__ == "__main__":
    main()
