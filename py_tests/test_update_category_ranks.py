from datetime import date
from unittest.mock import Mock

import pytest

from py_src.domain.value_objects.category_rank import CategoryRank
from py_src.usecases.update_category_ranks import (
    EmptyCatalogResultError,
    UpdateCategoryRanksUseCase,
)

ASIN_VALUES = ["ASIN", "", "", "header", "B0EXAMPLE1", "", "", "", "", ""]
NAME_VALUES = [
    "商品名", "", "", "header",
    "商品名です", "営業利益", "広告経由", "粗利益", "広告費", "順位",
]
HEADER = ["ASIN", "商品名", "目標販売数", 46274, 46273]
DAY = date(2026, 9, 9)


def _sheet() -> Mock:
    sheet = Mock()
    sheet.read_grid.return_value = (ASIN_VALUES, NAME_VALUES, HEADER)
    return sheet


def _catalog(ranks: dict[str, CategoryRank]) -> Mock:
    # 空を返すと EmptyCatalogResultError になるので、最低1件は返す
    catalog = Mock()
    catalog.fetch.return_value = [{"asin": a} for a in ranks] or [{"asin": "B0EXAMPLE1"}]
    return catalog


class TestUpdateCategoryRanks:
    def test_writes_the_ranks_it_built(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sheet = _sheet()
        ranks = {"B0EXAMPLE1": CategoryRank(asin="B0EXAMPLE1", category="収納", rank=12)}
        monkeypatch.setattr(
            "py_src.usecases.update_category_ranks.to_ranks", lambda items, **kw: ranks
        )

        result = UpdateCategoryRanksUseCase(
            sheet=sheet, catalog=_catalog(ranks)
        ).execute(DAY)

        assert result.cells_written == 1
        sheet.apply_updates.assert_called_once()

    def test_asks_the_catalog_only_for_asins_in_the_sheet(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sheet = _sheet()
        catalog = _catalog({})
        monkeypatch.setattr(
            "py_src.usecases.update_category_ranks.to_ranks", lambda items, **kw: {}
        )

        UpdateCategoryRanksUseCase(sheet=sheet, catalog=catalog).execute(DAY)

        assert catalog.fetch.call_args[0][0] == ["B0EXAMPLE1"]

    def test_passes_the_recorded_category_so_it_keeps_following_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sheet = _sheet()
        sheet.read_grid.return_value = (
            ASIN_VALUES, NAME_VALUES[:-1] + ["順位（収納）"], HEADER,
        )
        seen: dict = {}

        def spy(items: list, known_categories: dict) -> dict:
            seen.update(known_categories)
            return {}

        monkeypatch.setattr("py_src.usecases.update_category_ranks.to_ranks", spy)

        UpdateCategoryRanksUseCase(sheet=sheet, catalog=_catalog({})).execute(DAY)

        assert seen == {"B0EXAMPLE1": "収納"}

    def test_raises_when_the_catalog_returns_nothing(self) -> None:
        # 取得できていないだけの状態で「順位なし」と書いてはいけない
        sheet = _sheet()
        catalog = Mock()
        catalog.fetch.return_value = []

        with pytest.raises(EmptyCatalogResultError):
            UpdateCategoryRanksUseCase(sheet=sheet, catalog=catalog).execute(DAY)

        sheet.apply_updates.assert_not_called()

    def test_does_not_write_when_the_day_has_no_column(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sheet = _sheet()
        ranks = {"B0EXAMPLE1": CategoryRank(asin="B0EXAMPLE1", category="収納", rank=12)}
        monkeypatch.setattr(
            "py_src.usecases.update_category_ranks.to_ranks", lambda items, **kw: ranks
        )

        result = UpdateCategoryRanksUseCase(
            sheet=sheet, catalog=_catalog(ranks)
        ).execute(date(2026, 1, 1))

        assert result.skipped_date is True
        sheet.apply_updates.assert_not_called()

    def test_raises_when_the_sheet_has_no_asin(self) -> None:
        sheet = Mock()
        sheet.read_grid.return_value = (["ASIN"], ["商品名"], HEADER)

        with pytest.raises(ValueError):
            UpdateCategoryRanksUseCase(sheet=sheet, catalog=Mock()).execute(DAY)
