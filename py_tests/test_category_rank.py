import pytest

from py_src.domain.value_objects.category_rank import CategoryRank, pick_rank


class TestCategoryRank:
    def test_rejects_a_malformed_asin(self) -> None:
        with pytest.raises(ValueError):
            CategoryRank(asin="XXX", category="収納", rank=1)

    def test_rejects_a_non_positive_rank(self) -> None:
        with pytest.raises(ValueError):
            CategoryRank(asin="B0EXAMPLE1", category="収納", rank=0)

    def test_unranked_has_no_rank(self) -> None:
        rank = CategoryRank.unranked("B0EXAMPLE1")

        assert rank.is_ranked is False
        assert rank.category == ""


class TestPickRank:
    def test_prefers_classification_ranks_over_display_group(self) -> None:
        groups = [
            {
                "classificationRanks": [{"title": "ジュエリー収納", "rank": 60}],
                "displayGroupRanks": [{"title": "ホーム＆キッチン", "rank": 19888}],
            }
        ]

        rank = pick_rank("B0EXAMPLE1", groups, preferred=None)

        assert (rank.category, rank.rank) == ("ジュエリー収納", 60)

    def test_falls_back_to_display_group_when_there_is_no_classification(self) -> None:
        groups = [{"displayGroupRanks": [{"title": "ホーム＆キッチン", "rank": 19888}]}]

        rank = pick_rank("B0EXAMPLE1", groups, preferred=None)

        assert (rank.category, rank.rank) == ("ホーム＆キッチン", 19888)

    def test_keeps_following_the_category_already_recorded(self) -> None:
        # 毎回いちばん良い順位を採ると日によってカテゴリが入れ替わり、時系列が壊れる
        groups = [
            {
                "classificationRanks": [
                    {"title": "ジュエリー収納", "rank": 60},
                    {"title": "小物入れ", "rank": 12},
                ]
            }
        ]

        rank = pick_rank("B0EXAMPLE1", groups, preferred="ジュエリー収納")

        assert (rank.category, rank.rank) == ("ジュエリー収納", 60)

    def test_takes_the_best_rank_when_the_recorded_category_is_absent(self) -> None:
        groups = [
            {
                "classificationRanks": [
                    {"title": "ジュエリー収納", "rank": 60},
                    {"title": "小物入れ", "rank": 12},
                ]
            }
        ]

        rank = pick_rank("B0EXAMPLE1", groups, preferred="もう無いカテゴリ")

        assert (rank.category, rank.rank) == ("小物入れ", 12)

    def test_is_unranked_when_no_group_has_a_rank(self) -> None:
        assert pick_rank("B0EXAMPLE1", [], preferred=None).is_ranked is False

    def test_ignores_entries_without_a_usable_rank(self) -> None:
        groups = [
            {
                "classificationRanks": [
                    {"title": "収納", "rank": 0},
                    {"title": "", "rank": 5},
                    {"title": "小物入れ", "rank": "12"},
                ]
            }
        ]

        assert pick_rank("B0EXAMPLE1", groups, preferred=None).is_ranked is False
