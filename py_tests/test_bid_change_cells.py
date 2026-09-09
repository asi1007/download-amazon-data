"""広告単価を変えた日を、営業利益の行で色分けする。

営業利益だけ見ても、それが入札を下げた結果なのか上げた結果なのかが分からない。
安くしたら青、高くしたら赤にして、後から意図を突き合わせられるようにする。

商品価格の変動（値上げ＝青／値下げ＝赤）とは**逆の対応**なので注意。
広告費は下げるのが good、商品価格は上げるのが good という違いによる。
"""
from py_src.infrastructure.sheets.bid_change_cells import (
    BidChangeCells,
    classify_bid_changes,
)


def _history() -> list[dict]:
    return [
        {"date": "2026-09-05", "bids": {"t1": 30, "t2": 20}},
        {"date": "2026-09-06", "bids": {"t1": 24, "t2": 20}},
        {"date": "2026-09-07", "bids": {"t1": 24, "t2": 25}},
    ]


def _targets() -> dict[str, list[str]]:
    return {"t1": ["B01"], "t2": ["B02"]}


def test_下げた日を安くした側に入れる() -> None:
    cells = classify_bid_changes(_history(), _targets(), {"B01": 10}, {"2026-09-06": "C"})

    assert cells.cheaper == ["C10"]


def test_上げた日を高くした側に入れる() -> None:
    cells = classify_bid_changes(_history(), _targets(), {"B02": 20}, {"2026-09-07": "D"})

    assert cells.pricier == ["D20"]


def test_変わらない日は触らない() -> None:
    cells = classify_bid_changes(_history(), _targets(), {"B02": 20}, {"2026-09-06": "C"})

    assert cells.cheaper == [] and cells.pricier == []


def test_列が無い日は飛ばす() -> None:
    cells = classify_bid_changes(_history(), _targets(), {"B01": 10}, {})

    assert cells.cheaper == []


def test_行が無い商品は飛ばす() -> None:
    cells = classify_bid_changes(_history(), _targets(), {}, {"2026-09-06": "C"})

    assert cells.cheaper == []


def test_記録が1日だけなら比較しない() -> None:
    history = [{"date": "2026-09-06", "bids": {"t1": 24}}]

    cells = classify_bid_changes(history, _targets(), {"B01": 10}, {"2026-09-06": "C"})

    assert cells.cheaper == [] and cells.pricier == []


def test_同じ商品で下げと上げが混ざれば多い方を採る() -> None:
    history = [
        {"date": "2026-09-05", "bids": {"t1": 30, "t2": 30, "t3": 20}},
        {"date": "2026-09-06", "bids": {"t1": 24, "t2": 24, "t3": 25}},
    ]
    targets = {"t1": ["B01"], "t2": ["B01"], "t3": ["B01"]}

    cells = classify_bid_changes(history, targets, {"B01": 10}, {"2026-09-06": "C"})

    assert cells.cheaper == ["C10"]
    assert cells.pricier == []


def test_同数なら色を付けない() -> None:
    history = [
        {"date": "2026-09-05", "bids": {"t1": 30, "t2": 20}},
        {"date": "2026-09-06", "bids": {"t1": 24, "t2": 25}},
    ]
    targets = {"t1": ["B01"], "t2": ["B01"]}

    cells = classify_bid_changes(history, targets, {"B01": 10}, {"2026-09-06": "C"})

    assert cells.cheaper == [] and cells.pricier == []


def test_複数商品を同時に塗る() -> None:
    history = [
        {"date": "2026-09-05", "bids": {"t1": 30, "t2": 20}},
        {"date": "2026-09-06", "bids": {"t1": 24, "t2": 25}},
    ]
    cells = classify_bid_changes(history, _targets(), {"B01": 10, "B02": 20},
                                 {"2026-09-06": "C"})

    assert cells.cheaper == ["C10"]
    assert cells.pricier == ["C20"]


def test_セルは行番号順に並ぶ() -> None:
    history = [
        {"date": "2026-09-05", "bids": {"t1": 30, "t2": 30}},
        {"date": "2026-09-06", "bids": {"t1": 24, "t2": 24}},
    ]
    targets = {"t1": ["B02"], "t2": ["B01"]}

    cells = classify_bid_changes(history, targets, {"B01": 10, "B02": 20},
                                 {"2026-09-06": "C"})

    assert cells.cheaper == ["C10", "C20"]


def test_件数を数えられる() -> None:
    cells = BidChangeCells(cheaper=["C10"], pricier=["C20", "C30"])

    assert len(cells.cheaper) == 1
    assert len(cells.pricier) == 2
