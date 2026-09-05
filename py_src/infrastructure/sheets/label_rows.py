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

# 粗利益・広告費のセルに適用するK円表記（1,240 -> "1.2K"）。整数の
# `#,##0,"K"` だと広告費がほぼ 0K に潰れるため小数点1桁にしている。
K_YEN_NUMBER_FORMAT = {"type": "NUMBER", "pattern": '#,##0.0,"K"'}


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
    header = worksheet.row_values(
        HEADER_ROW, value_render_option=ValueRenderOption.unformatted
    )
    return {
        value: index
        for index, value in enumerate(header, start=1)
        if isinstance(value, int)
    }


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
