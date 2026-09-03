from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AdWriteResult:
    cells_written: int = 0
    skipped_dates: tuple[str, ...] = field(default_factory=tuple)
