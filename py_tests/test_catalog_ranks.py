from unittest.mock import Mock

import pytest

from py_src.infrastructure.api.sp_api_catalog import SpApiCatalog, to_ranks


def _response(items: list[dict]) -> Mock:
    response = Mock()
    response.json.return_value = {"items": items}
    return response


class TestSpApiCatalog:
    def test_asks_for_sales_ranks_of_every_asin(self) -> None:
        auth = Mock()
        auth.request.return_value = _response([{"asin": "B0EXAMPLE1"}])

        items = SpApiCatalog(authenticator=auth).fetch(["B0EXAMPLE1"])

        assert items == [{"asin": "B0EXAMPLE1"}]
        url = auth.request.call_args[0][1]
        assert "identifiers=B0EXAMPLE1" in url
        assert "salesRanks" in url

    def test_splits_into_batches_of_twenty(self) -> None:
        # catalog items は1回に20件まで。全 ASIN を1本の URL に載せると 400 になる
        auth = Mock()
        auth.request.return_value = _response([])
        asins = [f"B0EXAMPL{i:02d}" for i in range(45)]

        SpApiCatalog(authenticator=auth, pause_seconds=0).fetch(asins)

        assert auth.request.call_count == 3

    def test_collects_items_from_every_batch(self) -> None:
        auth = Mock()
        auth.request.side_effect = [
            _response([{"asin": "B0EXAMPL01"}]),
            _response([{"asin": "B0EXAMPL02"}]),
        ]
        asins = [f"B0EXAMPL{i:02d}" for i in range(21)]

        items = SpApiCatalog(authenticator=auth, pause_seconds=0).fetch(asins)

        assert [i["asin"] for i in items] == ["B0EXAMPL01", "B0EXAMPL02"]

    def test_returns_nothing_for_an_empty_asin_list(self) -> None:
        auth = Mock()

        assert SpApiCatalog(authenticator=auth).fetch([]) == []
        auth.request.assert_not_called()


class TestToRanks:
    def test_builds_a_rank_per_asin(self) -> None:
        items = [
            {
                "asin": "B0EXAMPLE1",
                "salesRanks": [{"classificationRanks": [{"title": "収納", "rank": 12}]}],
            }
        ]

        ranks = to_ranks(items, known_categories={})

        assert (ranks["B0EXAMPLE1"].category, ranks["B0EXAMPLE1"].rank) == ("収納", 12)

    def test_keeps_following_the_recorded_category(self) -> None:
        items = [
            {
                "asin": "B0EXAMPLE1",
                "salesRanks": [
                    {
                        "classificationRanks": [
                            {"title": "収納", "rank": 12},
                            {"title": "小物入れ", "rank": 3},
                        ]
                    }
                ],
            }
        ]

        ranks = to_ranks(items, known_categories={"B0EXAMPLE1": "収納"})

        assert (ranks["B0EXAMPLE1"].category, ranks["B0EXAMPLE1"].rank) == ("収納", 12)

    def test_an_item_without_ranks_is_unranked(self) -> None:
        ranks = to_ranks([{"asin": "B0EXAMPLE1"}], known_categories={})

        assert ranks["B0EXAMPLE1"].is_ranked is False

    def test_skips_a_malformed_asin(self) -> None:
        assert to_ranks([{"asin": "not-an-asin"}], known_categories={}) == {}


class TestCatalogErrors:
    def test_raises_when_the_request_fails(self) -> None:
        auth = Mock()
        auth.request.side_effect = RuntimeError("HTTP 403")

        with pytest.raises(RuntimeError):
            SpApiCatalog(authenticator=auth).fetch(["B0EXAMPLE1"])
