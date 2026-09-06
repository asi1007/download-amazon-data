from __future__ import annotations
from datetime import date

from gspread import Worksheet
from gspread.utils import ValueRenderOption

HEADER_ROW = 4
ASIN_COLUMN = 1
PRODUCT_NAME_HEADER = "商品名"
ASIN_LENGTH = 10
SHEETS_EPOCH = date(1899, 12, 30)

AD_ROW_LABEL = "広告経由"
GROSS_PROFIT_ROW_LABEL = "粗利益"
AD_COST_ROW_LABEL = "広告費"
ROW_LABELS_IN_ORDER: tuple[str, ...] = (
    AD_ROW_LABEL,
    GROSS_PROFIT_ROW_LABEL,
    AD_COST_ROW_LABEL,
)

# 粗利益・広告費は千円単位・小数点1桁で表示する。カンマ1個で 1/1000 に
# スケールされるので、セルには円のまま書いて表示だけを変える（総売上の
# `#,##0,"千円"` と同じ考え方）。整数だと1日あたり数百円の広告費が 0 に
# 潰れるため小数点1桁にしてある。単位の文字は付けない
K_YEN_NUMBER_FORMAT = {"type": "NUMBER", "pattern": "#,##0.0,"}


def date_serial(day: date) -> int:
    return (day - SHEETS_EPOCH).days


def bind_label_rows(
    asin_values: list[str], name_values: list[str], label: str
) -> dict[str, list[int]]:
    label_rows: dict[str, list[int]] = {}
    current_asin = ""
    for index in range(max(len(asin_values), len(name_values))):
        row = index + 1
        asin = asin_values[index].strip() if index < len(asin_values) else ""
        name = name_values[index].strip() if index < len(name_values) else ""
        if len(asin) == ASIN_LENGTH:
            current_asin = asin
            continue
        if asin:
            current_asin = ""
            continue
        if name == label and current_asin:
            label_rows.setdefault(current_asin, []).append(row)
    return label_rows


def read_date_columns(worksheet: Worksheet) -> dict[int, int]:
    # 同じ日付が2列にあるとき（0:00 の today と daily が競合した、手で足した等）、
    # 最も左の列を採る。SalesSheet._find_serial_column も左から探すので、
    # 個数と粗利益が別の列に入る事故を防ぐ。bool は int の派生なので除く
    header = worksheet.row_values(
        HEADER_ROW, value_render_option=ValueRenderOption.unformatted
    )
    columns: dict[int, int] = {}
    for index, value in enumerate(header, start=1):
        if isinstance(value, int) and not isinstance(value, bool):
            columns.setdefault(value, index)
    return columns


def find_column(headers: list[str], name: str) -> int:
    # 売上/日 のヘッダーは改行入り（'ライバル\nURL'）と大小文字の混在
    # （'SKU' と 'fnsku'）がある。素朴な完全一致だと黙って落ちる
    target = _normalize_header(name)
    for index, value in enumerate(headers, start=1):
        if _normalize_header(value) == target:
            return index
    raise ValueError(f"ヘッダーに '{name}' が見つかりません")


def _normalize_header(value: object) -> str:
    return str(value).replace("\n", "").strip().casefold()
