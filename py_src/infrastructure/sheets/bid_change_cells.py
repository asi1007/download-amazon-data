from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BidChangeCells:
    cheaper: list[str] = field(default_factory=list)
    pricier: list[str] = field(default_factory=list)


def classify_bid_changes(
    history: list[dict[str, Any]],
    target_asins: dict[str, list[str]],
    asin_rows: dict[str, int],
    date_columns: dict[str, str],
) -> BidChangeCells:
    """広告単価を動かした日の営業利益セルを、安くした側と高くした側に分ける。

    1 つの商品で下げと上げが混ざる日がある。多い方を採り、
    同数なら色を付けない（どちらとも言えないものを断定しない）。
    """
    ordered = sorted(history, key=lambda entry: entry["date"])
    cheaper: list[str] = []
    pricier: list[str] = []

    for previous, current in zip(ordered, ordered[1:]):
        column = date_columns.get(current["date"])
        if not column:
            continue
        tally: dict[str, Counter] = {}
        for target_id, after in current.get("bids", {}).items():
            before = previous.get("bids", {}).get(target_id)
            if before is None or before == after:
                continue
            way = "down" if after < before else "up"
            for asin in target_asins.get(target_id, []):
                tally.setdefault(asin, Counter())[way] += 1

        for asin, counter in tally.items():
            row = asin_rows.get(asin)
            if not row:
                continue
            if counter["down"] > counter["up"]:
                cheaper.append(f"{column}{row}")
            elif counter["up"] > counter["down"]:
                pricier.append(f"{column}{row}")

    return BidChangeCells(cheaper=sorted(cheaper), pricier=sorted(pricier))
