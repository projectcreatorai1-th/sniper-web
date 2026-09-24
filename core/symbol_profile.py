"""Symbol profile & account settings.

Broker constraints differ per broker, so everything here is configurable and
persisted - nothing is hard-coded beyond editable defaults.

Default symbol profile is XAUUSD because the seller's documentation uses it
as the primary example asset (contract size 100 -> see assumption
XAUUSD_CONTRACT_ASSUMPTION_001).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Optional


@dataclass
class SymbolProfile:
    name: str = "XAUUSD"
    contract_size: float = 100.0        # units of base asset per 1.0 lot
    tick_size: float = 0.01             # minimal price increment
    lot_min: float = 0.01               # = volume_min (spec naming)
    lot_max: float = 100.0              # = volume_max (spec naming)
    lot_step: float = 0.01              # = volume_step (spec naming)
    digits: int = 2
    reference_price: float = 2000.0     # price used for margin/exposure estimates
    # Phase 1 optional symbol specs - UNKNOWN (None) when not captured.
    # The defaults above are EDITABLE STARTING POINTS, never universal rules.
    tick_value: Optional[float] = None
    currency: str = ""                  # account/presentation currency if known
    quote_currency: str = ""
    base_currency: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SymbolProfile":
        p = cls()
        for k, v in d.items():
            if hasattr(p, k) and v is not None:
                setattr(p, k, v)
        return p


@dataclass
class AccountSettings:
    leverage: int = 500                 # e.g. 1:500
    margin_rate: float = 1.0            # broker margin multiplier (hedged/tiered rules)
    currency: str = "USD"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AccountSettings":
        a = cls()
        for k, v in d.items():
            if hasattr(a, k) and v is not None:
                setattr(a, k, v)
        return a


# Common editable starting points (user can freely modify any value afterwards)
def builtin_profiles() -> List[SymbolProfile]:
    return [
        SymbolProfile(
            name="XAUUSD", contract_size=100.0, tick_size=0.01,
            lot_min=0.01, lot_max=100.0, lot_step=0.01, digits=2, reference_price=2000.0,
        ),
        SymbolProfile(
            name="BTCUSD", contract_size=1.0, tick_size=0.01,
            lot_min=0.01, lot_max=100.0, lot_step=0.01, digits=2, reference_price=60000.0,
        ),
        SymbolProfile(
            name="EURUSD", contract_size=100000.0, tick_size=0.00001,
            lot_min=0.01, lot_max=100.0, lot_step=0.01, digits=5, reference_price=1.1000,
        ),
    ]
