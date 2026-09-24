"""Broker constraints (§19) + idempotency (§17).

BrokerProfile: calculate -> normalize -> validate -> intent.
Invalid volume raises ORDER_VOLUME_INVALID — never a silent semantic
change.

Idempotency keys: (account, symbol, cycle_id, event_type, sequence).
Repeats do not execute twice; DUPLICATE_EVENT is emitted instead.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple

ORDER_VOLUME_INVALID = "ORDER_VOLUME_INVALID"


@dataclass(frozen=True)
class BrokerProfile:
    min_lot: float = 0.01
    max_lot: float = 100.0
    lot_step: float = 0.01
    price_digits: int = 2
    tick_size: float = 0.01
    tick_value: float = 0.01          # USD per tick per lot
    contract_size: float = 1.0        # VERIFIED for GOLDmicro (R-CONTRACT-SIZE)
    margin_rate: float = 0.002        # leverage 1:500

    def validate(self) -> None:
        problems = []
        if self.min_lot <= 0 or self.max_lot < self.min_lot:
            problems.append("min/max lot range invalid")
        if self.lot_step <= 0:
            problems.append("lot_step must be > 0")
        if self.contract_size <= 0:
            problems.append("contract_size must be > 0")
        if problems:
            raise ValueError(f"BrokerProfile invalid: {'; '.join(problems)}")


@dataclass(frozen=True)
class OrderVolume:
    raw: float
    normalized: float
    lot_step: float
    valid: bool
    reason: str = ""


class BrokerConstraintError(ValueError):
    code = ORDER_VOLUME_INVALID


def normalize_volume(raw: float, profile: BrokerProfile) -> OrderVolume:
    if raw <= 0:
        return OrderVolume(raw, 0.0, profile.lot_step, False, "non-positive")
    stepped = math.floor(raw / profile.lot_step + 1e-9) * profile.lot_step
    norm = round(stepped, 10)
    if norm < profile.min_lot or norm > profile.max_lot:
        return OrderVolume(raw, norm, profile.lot_step, False,
                           f"{norm} outside [{profile.min_lot}, {profile.max_lot}]")
    return OrderVolume(raw, norm, profile.lot_step, True)


def margin_for(lot: float, price: float, profile: BrokerProfile) -> float:
    return round(lot * price * profile.contract_size * profile.margin_rate, 8)


# --------------------------------------------------------------------- §17
class IdempotencyKey(tuple):
    @classmethod
    def build(cls, account: str, symbol: str, cycle_id: str,
              event_type: str, sequence: int) -> "IdempotencyKey":
        return cls((account, symbol, cycle_id, event_type, sequence))


class DuplicateEvent(RuntimeError):
    pass


class IdempotencyLedger:
    """Tracks seen keys; duplicates are refused, not executed."""

    def __init__(self):
        self._seen: Set[Tuple] = set()

    def check_and_record(self, key: Tuple) -> bool:
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    def seen(self, key: Tuple) -> bool:
        return key in self._seen

    def size(self) -> int:
        return len(self._seen)
