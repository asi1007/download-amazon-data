from __future__ import annotations

from gspread import Worksheet

from py_src.infrastructure.sheets.label_rows import (
    ASIN_COLUMN,
    ASIN_LENGTH,
    HEADER_ROW,
    PRODUCT_NAME_HEADER,
    ROW_LABELS_IN_ORDER,
    find_column,
)
from py_src.infrastructure.sheets.retry import retry_on_transient_error


def plan_block_moves(first_row: int, current: list[str]) -> list[tuple[int, int]]:
    # ブロック内の並べ替えだけなので、ブロックの外の行番号は動かない。
    # 期待する順に1本ずつ引き上げ、そのたびに手元の並びも入れ替えて次を決める。
    # 返すのは (移動元の1起点の行番号, 移動先の1起点の行番号)
    order = list(current)
    moves: list[tuple[int, int]] = []
    for position, label in enumerate(ROW_LABELS_IN_ORDER):
        if position >= len(order) or order[position] == label:
            continue
        if label not in order[position:]:
            continue
        source = order.index(label, position)
        moves.append((first_row + source, first_row + position))
        order.insert(position, order.pop(source))
    return moves


def build_move_requests(sheet_id: int, moves: list[tuple[int, int]]) -> list[dict]:
    return [
        {
            "moveDimension": {
                "source": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": source - 1,
                    "endIndex": source,
                },
                "destinationIndex": destination - 1,
            }
        }
        for source, destination in moves
    ]


class LabelRowOrder:
    def __init__(self, worksheet: Worksheet) -> None:
        self._worksheet = worksheet

    @retry_on_transient_error
    def reorder(self) -> int:
        headers = self._worksheet.row_values(HEADER_ROW)
        name_column = find_column(headers, PRODUCT_NAME_HEADER)
        asin_values = self._worksheet.col_values(ASIN_COLUMN)
        name_values = self._worksheet.col_values(name_column)
        moves: list[tuple[int, int]] = []
        for index, value in enumerate(asin_values):
            if len(str(value).strip()) != ASIN_LENGTH or index + 1 <= HEADER_ROW:
                continue
            first_row = index + 2
            current = [
                str(name_values[first_row - 1 + offset]).strip()
                if first_row - 1 + offset < len(name_values)
                else ""
                for offset in range(len(ROW_LABELS_IN_ORDER))
            ]
            if set(current) != set(ROW_LABELS_IN_ORDER):
                continue
            moves.extend(plan_block_moves(first_row, current))
        if not moves:
            return 0
        self._worksheet.spreadsheet.batch_update(
            {"requests": build_move_requests(self._worksheet.id, moves)}
        )
        return len(moves)
