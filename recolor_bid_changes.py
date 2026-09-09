"""広告単価を変えた日を、営業利益の行に文字色で残す。

    .venv/bin/python recolor_bid_changes.py [--dry-run]

**安くした＝青、高くした＝赤。** 商品価格の色分け（値上げ＝青／値下げ＝赤）とは
逆の対応になる。広告費は下げるのが good、商品価格は上げるのが good だから。

入札の履歴は marketar/ad が残す docs/report/bids.json を読む。
Amazon の API は過去の入札を返さないため、記録が始まる前は色が付かない。
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from py_src.infrastructure.sheets.bid_change_cells import classify_bid_changes
from py_src.infrastructure.sheets.label_rows import (
    OPERATING_PROFIT_ROW_LABEL,
    bind_label_rows,
    read_date_columns,
)
from py_src.infrastructure.sheets.spreadsheet_client import open_spreadsheet

SHEET_NAME = "売上/日"
# ASIN は A 列、ラベル（営業利益 / 広告経由 / 粗利益 / 広告費）は H 列（商品名と同じ列）
ASIN_COLUMN = 1
LABEL_COLUMN = 8
AD_DIR = Path(__file__).resolve().parents[2] / "marketar/ad/docs/report"
BID_LOG = AD_DIR / "bids.json"
REPORT_HTML = AD_DIR / "ad-performance.html"
# 安くした＝青、高くした＝赤
CHEAPER_FORMAT = {
    "textFormat": {"foregroundColor": {"red": 0.0, "green": 0.25, "blue": 0.8}, "bold": True}
}
PRICIER_FORMAT = {
    "textFormat": {"foregroundColor": {"red": 0.8, "green": 0.0, "blue": 0.0}, "bold": True}
}
CHUNK = 200


def main() -> None:
    load_dotenv()
    dry_run = "--dry-run" in sys.argv

    history = _load_bids()
    targets = _load_target_asins()
    if not history or not targets:
        print("! 入札の履歴かターゲットの対応が読めません")
        return

    spreadsheet = open_spreadsheet(
        os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json"),
        os.getenv("SPREADSHEET_ID"),
    )
    worksheet = spreadsheet.worksheet(SHEET_NAME)

    # 営業利益はラベル行。ASIN 行の下に並ぶので、ASIN 列と商品名列から対応を作る
    profit_rows = {
        asin: rows[0]
        for asin, rows in bind_label_rows(
            worksheet.col_values(ASIN_COLUMN),
            worksheet.col_values(LABEL_COLUMN),
            OPERATING_PROFIT_ROW_LABEL,
        ).items()
        if rows
    }
    date_columns = {
        _serial_to_iso(serial): _column_letter(index)
        for serial, index in read_date_columns(worksheet).items()
    }

    cells = classify_bid_changes(history, targets, profit_rows, date_columns)
    print(f"入札の記録: {len(history)}日分 / 営業利益の行: {len(profit_rows)}件")
    print(f"安くした（青）: {len(cells.cheaper)} セル")
    print(f"高くした（赤）: {len(cells.pricier)} セル")

    if dry_run:
        print("--dry-run のため書き込みません")
        return

    _apply(worksheet, cells.cheaper, CHEAPER_FORMAT)
    _apply(worksheet, cells.pricier, PRICIER_FORMAT)
    print("営業利益の行に色を付けました")


def _load_bids() -> list[dict]:
    if not BID_LOG.exists():
        return []
    return json.loads(BID_LOG.read_text(encoding="utf-8"))


def _load_target_asins() -> dict[str, list[str]]:
    """ターゲットID → そのキャンペーンの ASIN。広告レポートの埋め込みから取る。"""
    if not REPORT_HTML.exists():
        return {}
    found = re.search(r"const DATA = (\{.*?\});", REPORT_HTML.read_text(encoding="utf-8"), re.S)
    if not found:
        return {}
    data = json.loads(found.group(1))
    mapping: dict[str, list[str]] = {}
    for campaign in data.get("campaigns", []):
        asins = campaign.get("asins") or []
        for target in campaign.get("targets", []):
            if target.get("id"):
                mapping[str(target["id"])] = asins
    return mapping


def _serial_to_iso(serial: int) -> str:
    return date.fromordinal(date(1899, 12, 30).toordinal() + serial).isoformat()


def _column_letter(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _apply(worksheet, cells: list[str], cell_format: dict) -> None:
    for start in range(0, len(cells), CHUNK):
        worksheet.format(cells[start : start + CHUNK], cell_format)


if __name__ == "__main__":
    main()
