from __future__ import annotations

from dataclasses import dataclass, field

from gspread.utils import rowcol_to_a1


@dataclass(frozen=True)
class PriceChangeCells:
    pricier: list[str] = field(default_factory=list)
    cheaper: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)


def classify_price_changes(
    notes: list[list[str]],
    asin_rows: list[int],
    column_by_serial: dict[int, int],
) -> PriceChangeCells:
    result = PriceChangeCells()
    for serial, column in sorted(column_by_serial.items()):
        previous_column = column_by_serial.get(serial - 1)
        if previous_column is None:
            continue
        _classify_one_column(notes, asin_rows, column, previous_column, result)
    return result


def _classify_one_column(
    notes: list[list[str]],
    asin_rows: list[int],
    column: int,
    previous_column: int,
    result: PriceChangeCells,
) -> None:
    for row in asin_rows:
        price = _note_price(notes, row, column)
        previous = _note_price(notes, row, previous_column)
        if price is None or previous is None:
            continue
        _bucket_for(price, previous, result).append(rowcol_to_a1(row, column))


def _bucket_for(price: float, previous: float, result: PriceChangeCells) -> list[str]:
    if price > previous:
        return result.pricier
    if price < previous:
        return result.cheaper
    return result.unchanged


def _note_price(notes: list[list[str]], row: int, column: int) -> float | None:
    if row - 1 >= len(notes):
        return None
    row_notes = notes[row - 1]
    if column - 1 >= len(row_notes):
        return None
    raw = str(row_notes[column - 1]).replace(",", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None
