from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

ASIN_PATTERN = re.compile(r"^B0[A-Z0-9]{8}$")


@dataclass(frozen=True)
class CategoryRank:
    asin: str
    category: str
    rank: int | None

    def __post_init__(self) -> None:
        if not ASIN_PATTERN.match(self.asin):
            raise ValueError(f"ASIN の形式が不正です: {self.asin}")
        if self.rank is not None and self.rank <= 0:
            raise ValueError(f"順位は正の整数である必要があります: {self.rank}")

    @classmethod
    def unranked(cls, asin: str) -> CategoryRank:
        return cls(asin=asin, category="", rank=None)

    @property
    def is_ranked(self) -> bool:
        return self.rank is not None


def pick_rank(
    asin: str, groups: list[dict[str, Any]], preferred: str | None
) -> CategoryRank:
    # classificationRanks（例: ジュエリー収納 60位）が「カテゴリランキング」。
    # 無ければ displayGroupRanks（例: ホーム＆キッチン 19888位）で代用する
    entries = [e for g in groups for e in g.get("classificationRanks", [])]
    if not entries:
        entries = [e for g in groups for e in g.get("displayGroupRanks", [])]

    # 一度記録したカテゴリを追い続ける。毎回いちばん良い順位を採ると日によって
    # カテゴリが入れ替わり、時系列が意味を失う
    if preferred:
        for entry in entries:
            if entry.get("title") == preferred:
                kept = _better(None, entry)
                if kept:
                    return CategoryRank(asin=asin, category=kept[0], rank=kept[1])

    best: tuple[str, int] | None = None
    for entry in entries:
        best = _better(best, entry)
    if best is None:
        return CategoryRank.unranked(asin)
    return CategoryRank(asin=asin, category=best[0], rank=best[1])


def _better(
    current: tuple[str, int] | None, entry: dict[str, Any]
) -> tuple[str, int] | None:
    rank = entry.get("rank")
    title = entry.get("title")
    if not isinstance(rank, int) or isinstance(rank, bool) or rank <= 0 or not title:
        return current
    if current is None or rank < current[1]:
        return (str(title), rank)
    return current
