"""Versioned configuration schema (§34) + observability (§35).

Every config validates; invalid -> CONFIG_INVALID, no silent fallback.
Diagnostics expose model/hash/state/cycle/basket/level/lot/risk/mode/
pending intent/last event/uncertainty/hypothesis as JSON.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

CONFIG_SCHEMA = "OUR_EA_CONFIG_V1"


class ConfigInvalid(ValueError):
    code = "CONFIG_INVALID"


@dataclass(frozen=True)
class OurEaConfig:
    model_version: str
    execution_mode: str = "SIMULATION"
    account: str = "SIM"
    symbol: str = "GOLDmicro"
    # engine blocks
    lot: Dict[str, Any] = field(default_factory=lambda: {
        "base_lot": 0.10, "multiplier": 1.10, "lot_step": 0.01,
        "min_lot": 0.01, "max_lot": 100.0})
    grid: Dict[str, Any] = field(default_factory=lambda: {
        "step_usd": 5.0, "tolerance_usd": 1.0,
        "trigger_hypothesis": "H_PREV_ENTRY"})
    basket: Dict[str, Any] = field(default_factory=lambda: {
        "hypothesis": "H_GROSS_1_00"})
    partial: Dict[str, Any] = field(default_factory=lambda: {
        "enabled": False,   # UNKNOWN rules -> disabled by default (§13/§22)
        "policy_on_uncertainty": "SKIP_WITH_UNCERTAINTY"})
    risk: Dict[str, Any] = field(default_factory=lambda: {
        "max_positions": 12, "max_grid_depth": 12, "max_total_lot": 2.0,
        "max_loss_usd": 50.0, "max_drawdown_pct": 30.0,
        "max_margin_usage_pct": 50.0, "max_spread_usd": 0.60,
        "max_slippage_usd": 0.50, "max_execution_time_s": 5.0,
        "allowed_symbols": ["GOLDmicro"]})
    broker: Dict[str, Any] = field(default_factory=lambda: {
        "min_lot": 0.01, "max_lot": 100.0, "lot_step": 0.01,
        "price_digits": 2, "tick_size": 0.01, "tick_value": 0.01,
        "contract_size": 1.0, "margin_rate": 0.002})
    logging: Dict[str, Any] = field(default_factory=lambda: {
        "json_lines": True, "csv": False, "dir": "data/our_ea/logs"})
    schema: str = CONFIG_SCHEMA

    def validate(self) -> "OurEaConfig":
        problems: List[str] = []
        if not self.model_version:
            problems.append("model_version required")
        if self.execution_mode not in ("SIMULATION", "PAPER", "DEMO", "LIVE"):
            problems.append(f"execution_mode invalid: {self.execution_mode}")
        elif self.execution_mode == "LIVE":
            problems.append("execution_mode=LIVE is locked (Phase 6)")
        if self.grid.get("trigger_hypothesis") not in ("H_PREV_ENTRY", "H_EXTREME"):
            problems.append("grid.trigger_hypothesis must be a known hypothesis")
        if self.basket.get("hypothesis") not in ("H_GROSS_1_00", "H_PER_LOT_0_50",
                                                 "H_PER_LOT_0_85"):
            problems.append("basket.hypothesis must be a compatible hypothesis "
                            "(1.68 is REJECTED)")
        if self.basket.get("hypothesis") == "H_GROSS_1_68":
            problems.append("H_GROSS_1_68 is REJECTED (E027)")
        if self.lot.get("base_lot", 0) <= 0 or self.lot.get("multiplier", 0) < 1:
            problems.append("lot block invalid")
        if problems:
            raise ConfigInvalid("; ".join(problems))
        return self

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "OurEaConfig":
        base = cls(model_version=d.get("model_version", ""))
        known = set(base.to_dict().keys())
        clean = {k: v for k, v in d.items() if k in known}
        return cls(**clean).validate()


# --------------------------------------------------------------------- §35
class Diagnostics:
    """Machine-readable JSON snapshot of the running strategy."""

    def __init__(self):
        self._data: Dict[str, Any] = {}

    def update(self, **kw) -> None:
        self._data.update(kw)

    def to_json(self) -> str:
        import json
        return json.dumps(self._data, ensure_ascii=False, indent=1)

    def to_dict(self) -> dict:
        return dict(self._data)
