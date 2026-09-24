"""Environment / Broker profiles (Phase 1).

EnvironmentProfile records WHERE the EA was observed running
(OBSERVED TEST ENVIRONMENT) - it is NOT a universal rule: M15 is not a
required timeframe, XM is not a required broker, GOLDmicro is not a
universal symbol.

DELIBERATELY EXCLUDED: account numbers are sensitive and unneeded - this
module provides NO field for them and simulation must never use one.

BrokerProfile models broker-side facts; anything not captured stays None
(= UNKNOWN). No values are invented.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

ENV_SCHEMA = "SNIPER_ENVIRONMENT_PROFILE_V1"
BROKER_SCHEMA = "SNIPER_BROKER_PROFILE_V1"

# record-level statuses (reuse evidence semantics)
OBSERVED = "OBSERVED"
UNKNOWN = "UNKNOWN"

UNKNOWN_TEXT = "UNKNOWN"          # how missing values are reported


@dataclass
class EnvironmentProfile:
    environment_id: str = "ENV-001"
    ea_version: str = ""
    platform: str = ""
    broker: str = ""
    account_type: str = ""
    symbol: str = ""
    timeframe: str = ""
    leverage: Optional[float] = None      # user/test-data supplied, never assumed
    currency: str = ""
    contract_size: Optional[float] = None
    tick_size: Optional[float] = None
    tick_value: Optional[float] = None
    volume_min: Optional[float] = None
    volume_max: Optional[float] = None
    volume_step: Optional[float] = None
    margin_mode: str = ""
    source: str = ""
    status: str = UNKNOWN
    notes: str = ""

    # NO account number field - intentionally excluded (sensitive/unneeded).

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = ENV_SCHEMA
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "EnvironmentProfile":
        p = cls()
        for k, v in d.items():
            if k == "schema" or not hasattr(p, k) or v is None:
                continue
            cur = getattr(p, k)
            if isinstance(cur, float) and not isinstance(cur, bool):
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    continue
            setattr(p, k, v)
        return p

    def observed_fields(self) -> dict:
        """Fields that carry an observed value (others report UNKNOWN)."""
        out = {}
        for k, v in asdict(self).items():
            if k == "schema":
                continue
            out[k] = v if v not in (None, "") else UNKNOWN_TEXT
        return out


@dataclass
class BrokerProfile:
    broker_name: str = ""
    server: str = ""
    account_type: str = ""
    leverage: Optional[float] = None
    margin_mode: str = ""
    commission_model: str = ""
    swap_model: str = ""
    spread_model: str = ""
    execution_model: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = BROKER_SCHEMA
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "BrokerProfile":
        b = cls()
        for k, v in d.items():
            if k == "schema" or not hasattr(b, k) or v is None:
                continue
            setattr(b, k, v)
        return b


def observed_test_environment() -> EnvironmentProfile:
    """The environment seen in the installation video.

    OBSERVED TEST ENVIRONMENT only - none of these values is a requirement
    or universal rule. Numeric symbol/account specs were NOT captured on
    video and therefore stay None (= UNKNOWN).
    """
    return EnvironmentProfile(
        environment_id="ENV-OBS-001",
        ea_version="1.68",
        platform="MT5",
        broker="XM Global",
        account_type="Hedge",
        symbol="GOLDmicro",
        timeframe="M15",
        leverage=None,               # user/test-data supplied; not observed
        source="Installation Video — วิธีติดตั้ง EA SNIPER.mp4 (E002-E006)",
        status=OBSERVED,
        notes=("OBSERVED TEST ENVIRONMENT. M15 is NOT a required timeframe, "
               "XM Global is NOT a required broker, GOLDmicro is NOT a universal "
               "symbol. Account numbers are deliberately not stored."),
    )
