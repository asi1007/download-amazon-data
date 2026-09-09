from __future__ import annotations

from datetime import date

from py_src.domain.value_objects.category_rank import ASIN_PATTERN
from py_src.infrastructure.api.sp_api_catalog import to_ranks
from py_src.usecases.build_rank_updates import (
    RankWriteResult,
    build_rank_updates,
    known_categories,
)


class EmptyCatalogResultError(RuntimeError):
    pass


class UpdateCategoryRanksUseCase:
    def __init__(self, sheet: object, catalog: object) -> None:
        self._sheet = sheet
        self._catalog = catalog

    def execute(self, day: date) -> RankWriteResult:
        asin_values, name_values, header = self._sheet.read_grid()
        asins = [a.strip() for a in asin_values if ASIN_PATTERN.match(a.strip())]
        if not asins:
            raise ValueError("売上/日 から ASIN を取得できませんでした")

        items = self._catalog.fetch(asins)
        # 1件も返らないのは権限や API 障害。取得できていないだけの状態で
        # 「順位なし」と書くと、実際に順位を失ったのか区別できなくなる
        if not items:
            raise EmptyCatalogResultError(
                f"{len(asins)}件の ASIN に対しカタログが1件も返りませんでした"
            )

        ranks = to_ranks(
            items, known_categories=known_categories(asin_values, name_values)
        )
        updates, result = build_rank_updates(
            asin_values, name_values, header, ranks, day
        )
        if updates:
            self._sheet.apply_updates(updates)
        return result
