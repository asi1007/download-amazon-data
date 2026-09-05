from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ActualProfitCell:
    asin: str
    profit: float
    estimate: float
    fully_settled: bool


@dataclass(frozen=True)
class ActualProfitWriteResult:
    cells_written: int = 0
    cells_cleared: int = 0
    skipped_dates: tuple[str, ...] = field(default_factory=tuple)
    asins_without_row: tuple[str, ...] = field(default_factory=tuple)
