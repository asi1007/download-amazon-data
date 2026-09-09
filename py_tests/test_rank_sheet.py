from unittest.mock import Mock

from py_src.infrastructure.sheets.rank_sheet import RankSheet


def _worksheet() -> Mock:
    worksheet = Mock()
    worksheet.get_all_values.return_value = [
        ["ASIN", "商品名", "目標販売数", "09"],
        ["", "", "", ""],
        ["", "", "", ""],
        ["ASIN", "商品名", "目標販売数", "09"],
        ["B0EXAMPLE1", "商品名です", "", ""],
        ["", "順位", "", ""],
    ]
    worksheet.row_values.return_value = ["ASIN", "商品名", "目標販売数", 46274]
    return worksheet


class TestReadGrid:
    def test_returns_the_asin_column_the_name_column_and_the_header(self) -> None:
        worksheet = _worksheet()

        asins, names, header = RankSheet(worksheet).read_grid()

        assert asins[4] == "B0EXAMPLE1"
        assert names[5] == "順位"
        assert header == ["ASIN", "商品名", "目標販売数", 46274]

    def test_reads_the_header_unformatted_so_dates_stay_numbers(self) -> None:
        # 書式付きで読むと日付が "09" のような文字列になり、列を引けない
        worksheet = _worksheet()

        RankSheet(worksheet).read_grid()

        assert worksheet.row_values.call_args.kwargs["value_render_option"] == (
            "UNFORMATTED_VALUE"
        )

    def test_pads_rows_that_are_shorter_than_the_name_column(self) -> None:
        worksheet = _worksheet()
        worksheet.get_all_values.return_value = [
            ["ASIN", "商品名", "目標販売数"],
            [], [], ["ASIN", "商品名"], ["B0EXAMPLE1"],
        ]

        asins, names, _ = RankSheet(worksheet).read_grid()

        assert asins[4] == "B0EXAMPLE1"
        assert names[4] == ""


class TestApplyUpdates:
    def test_sends_one_batch(self) -> None:
        worksheet = _worksheet()

        RankSheet(worksheet).apply_updates([{"range": "D6", "values": [[12]]}])

        worksheet.batch_update.assert_called_once()

    def test_writes_nothing_when_there_is_nothing_to_write(self) -> None:
        worksheet = _worksheet()

        RankSheet(worksheet).apply_updates([])

        worksheet.batch_update.assert_not_called()
