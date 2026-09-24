"""Lot engine — forensic verification of the observed lot progression.

Observed V1.68 behaviour (E012, 99.77% over 3,427 checks):

    Lot(n) = floor(BaseLot * Multiplier^(n-1) / VolumeStep) * VolumeStep

with defaults BaseLot=0.10, Multiplier=1.10, VolumeStep=0.01 — all
configurable per symbol/broker. The legacy analyzer SSOT
(core/calculations.py) still rounds half-up; that change is gated behind
MC-001 acceptance and MUST NOT be applied here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

EPS = 1e-9


class LotEngineError(ValueError):
    pass


@dataclass(frozen=True)
class LotEngineConfig:
    base_lot: float = 0.10
    multiplier: float = 1.10
    volume_step: float = 0.01
    min_volume: float = 0.01
    max_volume: float = 100.0

    def validate(self) -> None:
        if self.base_lot <= 0:
            raise LotEngineError("base_lot must be > 0")
        if self.multiplier < 1.0:
            raise LotEngineError("multiplier must be >= 1.0")
        if self.volume_step <= 0:
            raise LotEngineError("volume_step must be > 0")
        if self.min_volume < 0:
            raise LotEngineError("min_volume must be >= 0")


class LotEngine:
    """Floor-to-step geometric lot progression with broker constraints."""

    def __init__(self, config: Optional[LotEngineConfig] = None):
        self.config = config or LotEngineConfig()
        self.config.validate()

    def raw_lot(self, level: int) -> float:
        if level < 1:
            raise LotEngineError("level must be >= 1")
        return self.config.base_lot * (self.config.multiplier ** (level - 1))

    def lot(self, level: int) -> float:
        """Broker-valid lot for `level` (floor to step, clamped to [min, max])."""
        raw = self.raw_lot(level)
        stepped = math.floor(raw / self.config.volume_step + EPS) * self.config.volume_step
        stepped = round(stepped, 10)
        if stepped < self.config.min_volume:
            stepped = self.config.min_volume
        if stepped > self.config.max_volume:
            stepped = self.config.max_volume
        # normalize to step precision
        steps = round(stepped / self.config.volume_step)
        return round(steps * self.config.volume_step, 10)

    def ladder(self, levels: int) -> List[float]:
        return [self.lot(n) for n in range(1, levels + 1)]

    def level_of_lot(self, lot: float, max_level: int = 200) -> Optional[int]:
        """Inverse lookup: which ladder level matches this lot (± half step)."""
        half = self.config.volume_step / 2 + EPS
        for n in range(1, max_level + 1):
            if abs(self.lot(n) - lot) <= half:
                return n
        return None

    # -- verification against observations ------------------------------
    def verify_sequence(self, observed: List[float]) -> dict:
        """Compare an observed per-side lot sequence against the ladder."""
        matched = 0
        first_mismatch = None
        for lvl, v in enumerate(observed, 1):
            exp = self.lot(lvl)
            if abs(v - exp) <= self.config.volume_step / 2 + EPS:
                matched += 1
            elif first_mismatch is None:
                first_mismatch = {"level": lvl, "observed": v, "expected": exp}
        total = len(observed)
        return {"checked": total, "matched": matched,
                "match_pct": round(matched / total * 100, 2) if total else 0.0,
                "first_mismatch": first_mismatch}


DEFAULT_ENGINE = LotEngine()

# Regression pins from REAL observations (E012): levels 1-32 were actually
# observed (max side depth 32, 4451/4451 checks = 100.00% on HIGH-confidence
# cycles); levels 33-50 are formula EXTRAPOLATION, not observation.
OBSERVED_FLOOR_LADDER = [
    0.10, 0.11, 0.12, 0.13, 0.14, 0.16, 0.17, 0.19, 0.21, 0.23,
    0.25, 0.28, 0.31, 0.34, 0.37, 0.41, 0.45, 0.50, 0.55, 0.61,
    0.67, 0.74, 0.81, 0.89, 0.98, 1.08, 1.19, 1.31, 1.44, 1.58,
    1.74, 1.91,
]
EXTRAPOLATED_LADDER_33_50 = [
    2.11, 2.32, 2.55, 2.81, 3.09, 3.40, 3.74, 4.11, 4.52, 4.97,
    5.47, 6.02, 6.62, 7.28, 8.01, 8.81, 9.70, 10.67,
]   # L33-L50 formula extrapolation (not observed; max observed depth = 32)
