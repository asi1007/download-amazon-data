from migrate_category_ranks import build_migration_updates

ASIN_VALUES = ["ASIN", "", "", "header", "B0EXAMPLE1", "", "", "", "", ""]
NAME_VALUES = [
    "商品名", "", "", "header",
    "商品名です", "営業利益", "広告経由", "粗利益", "広告費", "順位",
]
HEADER = ["ASIN", "商品名", "目標販売数", 46274, 46273]


class TestBuildMigrationUpdates:
    def test_writes_each_day_into_its_own_column(self) -> None:
        old = [
            ["ASIN", "画像", "商品名", "カテゴリ", "2026-09-08", "2026-09-09"],
            ["B0EXAMPLE1", "", "商品名です", "収納", "14", "12"],
        ]

        updates, dropped = build_migration_updates(old, ASIN_VALUES, NAME_VALUES, HEADER)

        assert {"range": "E10", "values": [[14]]} in updates
        assert {"range": "D10", "values": [[12]]} in updates
        assert dropped == []

    def test_writes_the_rank_as_a_number(self) -> None:
        # 文字列のまま書くとグラデーションが効かない
        old = [
            ["ASIN", "画像", "商品名", "カテゴリ", "2026-09-09"],
            ["B0EXAMPLE1", "", "商品名です", "収納", "12"],
        ]

        updates, _ = build_migration_updates(old, ASIN_VALUES, NAME_VALUES, HEADER)

        written = [u for u in updates if u["range"] == "D10"][0]
        assert written["values"] == [[12]]
        assert isinstance(written["values"][0][0], int)

    def test_sets_the_label_from_the_old_category_column(self) -> None:
        old = [
            ["ASIN", "画像", "商品名", "カテゴリ", "2026-09-09"],
            ["B0EXAMPLE1", "", "商品名です", "収納", "12"],
        ]

        updates, _ = build_migration_updates(old, ASIN_VALUES, NAME_VALUES, HEADER)

        assert {"range": "B10", "values": [["順位（収納）"]]} in updates

    def test_leaves_the_label_alone_when_it_already_matches(self) -> None:
        name_values = NAME_VALUES[:-1] + ["順位（収納）"]
        old = [
            ["ASIN", "画像", "商品名", "カテゴリ", "2026-09-09"],
            ["B0EXAMPLE1", "", "商品名です", "収納", "12"],
        ]

        updates, _ = build_migration_updates(old, ASIN_VALUES, name_values, HEADER)

        assert all(u["range"] != "B10" for u in updates)

    def test_drops_days_that_have_no_column_in_the_sales_sheet(self) -> None:
        old = [
            ["ASIN", "画像", "商品名", "カテゴリ", "2026-01-01"],
            ["B0EXAMPLE1", "", "商品名です", "収納", "12"],
        ]

        updates, dropped = build_migration_updates(old, ASIN_VALUES, NAME_VALUES, HEADER)

        assert all(u["values"] != [[12]] for u in updates)
        assert dropped == ["2026-01-01"]

    def test_skips_empty_cells(self) -> None:
        old = [
            ["ASIN", "画像", "商品名", "カテゴリ", "2026-09-09"],
            ["B0EXAMPLE1", "", "商品名です", "収納", ""],
        ]

        updates, _ = build_migration_updates(old, ASIN_VALUES, NAME_VALUES, HEADER)

        assert all(u["range"] != "D10" for u in updates)

    def test_ignores_an_asin_that_has_no_rank_row(self) -> None:
        old = [
            ["ASIN", "画像", "商品名", "カテゴリ", "2026-09-09"],
            ["B0GONE00001", "", "消えた商品", "収納", "12"],
        ]

        updates, _ = build_migration_updates(old, ASIN_VALUES, NAME_VALUES, HEADER)

        assert updates == []

    def test_returns_nothing_for_an_empty_table(self) -> None:
        assert build_migration_updates([], ASIN_VALUES, NAME_VALUES, HEADER) == ([], [])
