"""OUR EA lot engine (§18) — VERIFIED rule R-LOT-FLOOR / R-BASE-LOT.

Own implementation (no Analyzer imports). Semantics MUST equal the
Analyzer SSOT `core/calculations.py normalize_lot` — equivalence is
enforced by tests/our_ea (not by runtime imports):

    Lot(n) = floor(BaseLot x Multiplier^(n-1) / lot_step) x lot_step

Observed defaults: BaseLot 0.10, Multiplier 1.10, lot_step 0.01.
Keeps raw_lot / normalized_lot / lot_step for observability.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

EPS = 1e-9
RULE_ID = "R-LOT-FLOOR"
BASE_LOT_RULE_ID = "R-BASE-LOT"


class LotEngineError(ValueError):
    pass


@dataclass(frozen=True)
class LotConfig:
    base_lot: float = 0.10          # VERIFIED R-BASE-LOT (E015)
    multiplier: float = 1.10
    lot_step: float = 0.01
    min_lot: float = 0.01
    max_lot: float = 100.0

    def validate(self) -> None:
        if self.base_lot <= 0:
            raise LotEngineError("base_lot must be > 0")
        if self.multiplier < 1.0:
            raise LotEngineError("multiplier must be >= 1.0")
        if self.lot_step <= 0:
            raise LotEngineError("lot_step must be > 0")
        if not (0 < self.min_lot <= self.max_lot):
            raise LotEngineError("invalid min/max lot")


@dataclass(frozen=True)
class LotDecision:
    level: int
    raw_lot: float
    normalized_lot: float
    lot_step: float
    rule_id: str = RULE_ID


class LotEngine:
    def __init__(self, config: Optional[LotConfig] = None):
        self.config = config or LotConfig()
        self.config.validate()

    def raw(self, level: int) -> float:
        if level < 1:
            raise LotEngineError("level must be >= 1")
        return self.config.base_lot * (self.config.multiplier ** (level - 1))

    def lot(self, level: int) -> float:
        raw = self.raw(level)
        stepped = math.floor(raw / self.config.lot_step + EPS) * self.config.lot_step
        clamped = min(max(round(stepped, 10), self.config.min_lot),
                      self.config.max_lot)
        steps = round(clamped / self.config.lot_step)
        return round(steps * self.config.lot_step, 10)

    def decide(self, level: int) -> LotDecision:
        return LotDecision(level=level, raw_lot=self.raw(level),
                           normalized_lot=self.lot(level),
                           lot_step=self.config.lot_step)

    def ladder(self, levels: int) -> list:
        return [self.lot(n) for n in range(1, levels + 1)]
