from __future__ import annotations

from py_src.infrastructure.sheets.price_change_colors import classify_price_changes


def _notes(cells: dict[tuple[int, int], str], rows: int = 8, cols: int = 8) -> list[list[str]]:
    grid = [["" for _ in range(cols)] for _ in range(rows)]
    for (row, col), note in cells.items():
        grid[row - 1][col - 1] = note
    return grid


class TestClassifyPriceChanges:
    def test_price_raised_since_previous_day(self) -> None:
        notes = _notes({(5, 3): "3500", (5, 4): "2800"})

        result = classify_price_changes(notes, [5], {46272: 3, 46271: 4})

        assert result.pricier == ["C5"]
        assert result.cheaper == []
        assert result.unchanged == []

    def test_price_lowered_since_previous_day(self) -> None:
        notes = _notes({(5, 3): "2000", (5, 4): "2800"})

        result = classify_price_changes(notes, [5], {46272: 3, 46271: 4})

        assert result.cheaper == ["C5"]
        assert result.pricier == []

    def test_same_price_is_unchanged(self) -> None:
        notes = _notes({(5, 3): "2800", (5, 4): "2800"})

        result = classify_price_changes(notes, [5], {46272: 3, 46271: 4})

        assert result.unchanged == ["C5"]
        assert result.pricier == []
        assert result.cheaper == []

    def test_missing_previous_note_is_left_alone(self) -> None:
        notes = _notes({(5, 3): "2800"})

        result = classify_price_changes(notes, [5], {46272: 3, 46271: 4})

        assert result.pricier == []
        assert result.cheaper == []
        assert result.unchanged == []

    def test_missing_previous_day_column_is_skipped(self) -> None:
        notes = _notes({(5, 3): "3500", (5, 4): "2800"})

        result = classify_price_changes(notes, [5], {46272: 3})

        assert result.pricier == []
        assert result.unchanged == []

    def test_non_numeric_note_is_ignored(self) -> None:
        notes = _notes({(5, 3): "取得 12:00", (5, 4): "2800"})

        result = classify_price_changes(notes, [5], {46272: 3, 46271: 4})

        assert result.pricier == []
        assert result.cheaper == []
        assert result.unchanged == []

    def test_price_with_comma_is_compared_as_number(self) -> None:
        notes = _notes({(5, 3): "12,800", (5, 4): "9,800"})

        result = classify_price_changes(notes, [5], {46272: 3, 46271: 4})

        assert result.pricier == ["C5"]

    def test_only_given_rows_are_examined(self) -> None:
        notes = _notes({(5, 3): "3500", (5, 4): "2800", (6, 3): "3500", (6, 4): "2800"})

        result = classify_price_changes(notes, [6], {46272: 3, 46271: 4})

        assert result.pricier == ["C6"]

    def test_covers_every_date_column(self) -> None:
        notes = _notes({(5, 3): "3500", (5, 4): "2800", (5, 5): "3000"})

        result = classify_price_changes(notes, [5], {46272: 3, 46271: 4, 46270: 5})

        assert result.pricier == ["C5"]
        assert result.cheaper == ["D5"]
