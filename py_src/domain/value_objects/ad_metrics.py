from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class AdMetrics:
    units: int = 0
    cost: float = 0.0
