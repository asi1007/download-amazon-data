from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from gspread.utils import rowcol_to_a1

from py_src.domain.value_objects.category_rank import CategoryRank
from py_src.infrastructure.sheets.label_rows import (
    CATEGORY_OPEN,
    PRODUCT_NAME_HEADER,
    RANK_ROW_LABEL,
    bind_label_rows,
    date_serial,
    find_column,
)

CATEGORY_CLOSE = "）"
SERIAL_MIN = 40000
SERIAL_MAX = 60000


@dataclass(frozen=True)
class RankWriteResult:
    cells_written: int = 0
    label_updates: int = 0
    skipped_date: bool = False
    missing_rows: list[str] = field(default_factory=list)


def rank_label(category: str) -> str:
    if not category:
        return RANK_ROW_LABEL
    return f"{RANK_ROW_LABEL}{CATEGORY_OPEN}{category}{CATEGORY_CLOSE}"


def category_of(label: str) -> str:
    stripped = label.strip()
    if not stripped.startswith(f"{RANK_ROW_LABEL}{CATEGORY_OPEN}"):
        return ""
    return stripped[len(RANK_ROW_LABEL) + 1:].removesuffix(CATEGORY_CLOSE)


def known_categories(asin_values: list[str], name_values: list[str]) -> dict[str, str]:
    categories: dict[str, str] = {}
    for asin, rows in bind_label_rows(asin_values, name_values, RANK_ROW_LABEL).items():
        for row in rows:
            category = category_of(_at(name_values, row))
            if category:
                categories[asin] = category
    return categories


def build_rank_updates(
    asin_values: list[str],
    name_values: list[str],
    header: list[object],
    ranks: dict[str, CategoryRank],
    day: date,
) -> tuple[list[dict], RankWriteResult]:
    column = _date_columns(header).get(date_serial(day))
    if column is None:
        return [], RankWriteResult(skipped_date=True)

    rows = bind_label_rows(asin_values, name_values, RANK_ROW_LABEL)
    name_column = find_column(header, PRODUCT_NAME_HEADER)
    updates: list[dict] = []
    written = 0
    labels = 0
    missing: list[str] = []
    for asin, rank in ranks.items():
        target_rows = rows.get(asin)
        if not target_rows:
            missing.append(asin)
            continue
        for row in target_rows:
            written += _append_rank(updates, rank, row, column)
            labels += _append_label(updates, rank, row, name_column, name_values)
    return updates, RankWriteResult(
        cells_written=written, label_updates=labels, missing_rows=sorted(missing)
    )


def _append_rank(
    updates: list[dict], rank: CategoryRank, row: int, column: int
) -> int:
    # 順位が付いていない日は空欄のまま。0 を書くと「1位より下」に見える
    if rank.rank is None:
        return 0
    updates.append({"range": rowcol_to_a1(row, column), "values": [[rank.rank]]})
    return 1


def _append_label(
    updates: list[dict],
    rank: CategoryRank,
    row: int,
    name_column: int,
    name_values: list[str],
) -> int:
    if not rank.category or category_of(_at(name_values, row)) == rank.category:
        return 0
    updates.append(
        {"range": rowcol_to_a1(row, name_column), "values": [[rank_label(rank.category)]]}
    )
    return 1


def _date_columns(header: list[object]) -> dict[int, int]:
    # 同じ日付が2列にあるときは最も左を採る。bool は int の派生なので除く
    columns: dict[int, int] = {}
    for index, value in enumerate(header, start=1):
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        if SERIAL_MIN < value < SERIAL_MAX:
            columns.setdefault(value, index)
    return columns


def _at(values: list[str], row: int) -> str:
    return values[row - 1].strip() if row - 1 < len(values) else ""
