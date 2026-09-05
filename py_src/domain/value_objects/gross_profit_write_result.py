from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GrossProfitWriteResult:
    cells_written: int = 0
    asins_without_row: tuple[str, ...] = field(default_factory=tuple)


class GrossProfitRowsNotFoundError(RuntimeError):
    pass
