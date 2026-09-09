from datetime import date

from py_src.domain.value_objects.category_rank import CategoryRank
from py_src.usecases.build_rank_updates import (
    build_rank_updates,
    category_of,
    rank_label,
)

ASIN_VALUES = ["ASIN", "", "", "header", "B0EXAMPLE1", "", "", "", "", ""]
NAME_VALUES = [
    "商品名", "", "", "header",
    "商品名です", "営業利益", "広告経由", "粗利益", "広告費", "順位",
]
HEADER = ["ASIN", "商品名", "目標販売数", 46274, 46273]
DAY = date(2026, 9, 9)


class TestRankLabelText:
    def test_builds_a_label_with_the_category(self) -> None:
        assert rank_label("ジュエリー収納") == "順位（ジュエリー収納）"

    def test_builds_a_bare_label_when_the_category_is_unknown(self) -> None:
        assert rank_label("") == "順位"

    def test_reads_the_category_back(self) -> None:
        assert category_of("順位（ジュエリー収納）") == "ジュエリー収納"

    def test_returns_empty_when_the_label_has_no_category(self) -> None:
        assert category_of("順位") == ""


class TestBuildRankUpdates:
    def test_writes_the_rank_into_the_date_column_of_the_rank_row(self) -> None:
        ranks = {"B0EXAMPLE1": CategoryRank(asin="B0EXAMPLE1", category="収納", rank=12)}

        updates, result = build_rank_updates(ASIN_VALUES, NAME_VALUES, HEADER, ranks, DAY)

        assert {"range": "D10", "values": [[12]]} in updates
        assert result.cells_written == 1
        assert result.skipped_date is False

    def test_updates_the_label_when_the_category_is_new(self) -> None:
        ranks = {"B0EXAMPLE1": CategoryRank(asin="B0EXAMPLE1", category="収納", rank=12)}

        updates, result = build_rank_updates(ASIN_VALUES, NAME_VALUES, HEADER, ranks, DAY)

        assert {"range": "B10", "values": [["順位（収納）"]]} in updates
        assert result.label_updates == 1

    def test_leaves_the_label_alone_when_it_already_holds_the_category(self) -> None:
        name_values = NAME_VALUES[:-1] + ["順位（収納）"]
        ranks = {"B0EXAMPLE1": CategoryRank(asin="B0EXAMPLE1", category="収納", rank=12)}

        updates, result = build_rank_updates(ASIN_VALUES, name_values, HEADER, ranks, DAY)

        assert all(u["range"] != "B10" for u in updates)
        assert result.label_updates == 0

    def test_writes_nothing_for_an_unranked_asin(self) -> None:
        # 順位が付いていない日は空欄のまま。0 を書くと「1位より下」に見える
        ranks = {"B0EXAMPLE1": CategoryRank.unranked("B0EXAMPLE1")}

        updates, result = build_rank_updates(ASIN_VALUES, NAME_VALUES, HEADER, ranks, DAY)

        assert updates == []
        assert result.cells_written == 0

    def test_skips_a_day_that_has_no_date_column(self) -> None:
        # 列を作るのは main.py daily の責務。ここでは書き足すだけ
        ranks = {"B0EXAMPLE1": CategoryRank(asin="B0EXAMPLE1", category="収納", rank=12)}

        updates, result = build_rank_updates(
            ASIN_VALUES, NAME_VALUES, HEADER, ranks, date(2026, 1, 1)
        )

        assert updates == []
        assert result.skipped_date is True

    def test_reports_an_asin_without_a_rank_row(self) -> None:
        ranks = {"B0MISSING1": CategoryRank(asin="B0MISSING1", category="収納", rank=3)}

        _, result = build_rank_updates(ASIN_VALUES, NAME_VALUES, HEADER, ranks, DAY)

        assert result.missing_rows == ["B0MISSING1"]

    def test_finds_a_rank_row_that_already_has_a_category(self) -> None:
        name_values = NAME_VALUES[:-1] + ["順位（ジュエリー収納）"]
        ranks = {
            "B0EXAMPLE1": CategoryRank(
                asin="B0EXAMPLE1", category="ジュエリー収納", rank=7
            )
        }

        updates, result = build_rank_updates(ASIN_VALUES, name_values, HEADER, ranks, DAY)

        assert {"range": "D10", "values": [[7]]} in updates
        assert result.missing_rows == []
