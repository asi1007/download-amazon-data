from datetime import date

from backfill_ad_sales import split_into_chunks


class TestSplitIntoChunks:
    def test_range_within_the_limit_is_one_chunk(self) -> None:
        assert split_into_chunks(date(2026, 9, 1), date(2026, 9, 10)) == [
            (date(2026, 9, 1), date(2026, 9, 10))
        ]

    def test_exactly_31_days_is_one_chunk(self) -> None:
        assert split_into_chunks(date(2026, 9, 1), date(2026, 10, 1)) == [
            (date(2026, 9, 1), date(2026, 10, 1))
        ]

    def test_90_days_splits_into_three(self) -> None:
        chunks = split_into_chunks(date(2026, 6, 6), date(2026, 9, 3))

        assert len(chunks) == 3
        assert chunks[0][0] == date(2026, 6, 6)
        assert chunks[-1][1] == date(2026, 9, 3)
        for earlier, later in zip(chunks, chunks[1:]):
            assert (later[0] - earlier[1]).days == 1

    def test_start_after_end_raises(self) -> None:
        try:
            split_into_chunks(date(2026, 9, 3), date(2026, 9, 1))
        except ValueError as error:
            assert "開始日" in str(error)
        else:
            raise AssertionError("ValueError が上がらなかった")
