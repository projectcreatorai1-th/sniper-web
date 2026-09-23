"""Set Builder (Module 8) + Set Store/Comparison (Module 9).

Generates parameter combinations from user-provided value lists, computes
metrics for each via the core calculators, and applies user filters.
Sets are NOT ranked - results keep generation order and carry warnings.

Named sets persist to data/sets.json with save/duplicate/delete/
export/import operations.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from core import calculations as c
from core.config import EAConfig
from core.model_rules import SimulationModelRules
from core.symbol_profile import SymbolProfile, AccountSettings
from core.validation import validate_config
from core.worst_case import simulate_worst_case, BOTH_SIDES

SETS_SCHEMA = "SNIPER_SET_STORE_V1"
MAX_COMBINATIONS = 5000


@dataclass
class SetMetrics:
    capital: float
    grid_step: float
    base_lot: float
    multiplier: float
    basket_target: float
    max_grid: int
    total_lots: float
    max_single_lot: float
    estimated_dd_percent: float
    estimated_worst_floating_loss: float
    estimated_margin: float
    margin_usage_percent: float
    grid_capacity_levels: int
    price_move_to_basket_target: Optional[float]
    warnings: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["estimated_worst_floating_loss"] = round(self.estimated_worst_floating_loss, 2)
        d["estimated_margin"] = round(self.estimated_margin, 2)
        d["total_lots"] = round(self.total_lots, 4)
        d["max_single_lot"] = round(self.max_single_lot, 4)
        return d


@dataclass
class BuilderFilters:
    max_dd_percent: Optional[float] = None
    max_grid: Optional[int] = None
    max_lot: Optional[float] = None          # single-order lot cap
    max_margin_usage_percent: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BuilderFilters":
        f = cls()
        for k, v in (d or {}).items():
            if hasattr(f, k):
                setattr(f, k, v)
        return f


def grid_capacity_levels(config: EAConfig, profile: SymbolProfile,
                         account: AccountSettings, rules: SimulationModelRules,
                         capital: float, margin_level_stop_percent: float = 100.0,
                         hard_cap: int = 200) -> int:
    """How many grid levels the capital can carry before margin level falls
    below `margin_level_stop_percent` (or equity <= 0 / lot beyond lot_max).

    MODEL ASSUMPTION based (MARGIN_ASSUMPTION_001 + grid assumptions).
    """
    side = c.BUY if config.UseGridBuy else c.SELL
    p0 = profile.reference_price
    lots, _ = c.lots_for_levels(config, hard_cap, rules, profile)
    positions: List[tuple] = []
    for i in range(1, hard_cap + 1):
        entry = c.entry_price_for_level(p0, i, side, config.GridStepUSD)
        positions.append((side, entry, lots[i - 1]))
        margin = sum(c.margin_used(l, e, profile, account) for _, e, l in positions)
        price_now = entry
        equity = capital + c.basket_pl(positions, price_now, profile)
        if equity <= 0:
            return i
        mlvl = c.margin_level_percent(equity, margin)
        if mlvl is not None and mlvl < margin_level_stop_percent:
            return i
        if lots[i - 1] > profile.lot_max:
            return i
    return hard_cap


def evaluate_set(base_config: EAConfig, profile: SymbolProfile,
                 account: AccountSettings, rules: SimulationModelRules,
                 capital: float, grid_step: float, base_lot: float,
                 multiplier: float, basket_target: float, max_grid: int) -> SetMetrics:
    cfg = base_config.copy()
    cfg.GridStepUSD = grid_step
    cfg.BaseLot = base_lot
    cfg.LotMultiplier = multiplier
    cfg.BasketCloseAllUSD = basket_target

    adverse = (max_grid - 1) * grid_step if max_grid > 1 else grid_step
    worst = simulate_worst_case(cfg, profile, account, rules, capital,
                                adverse, BOTH_SIDES)
    capacity = grid_capacity_levels(cfg, profile, account, rules, capital)

    lots_list, lot_assumptions = c.lots_for_levels(cfg, max_grid, rules, profile)
    positions, _ = c.build_side_positions(
        cfg, c.BUY if cfg.UseGridBuy else c.SELL, profile.reference_price,
        max_grid, rules, profile)
    move_to_target = None
    if cfg.UseBasketCloseAll and positions:
        total_lots = sum(l for _, _, l in positions)
        pl_now = c.basket_pl(positions, c.entry_price_for_level(
            profile.reference_price, max_grid,
            c.BUY if cfg.UseGridBuy else c.SELL, grid_step), profile)
        move_to_target = c.price_move_for_basket_target(pl_now, total_lots,
                                                        basket_target, profile)

    warnings: List[str] = []
    for issue in validate_config(cfg, profile, account, capital):
        if issue.severity in ("ERROR", "WARNING"):
            warnings.append(f"{issue.severity}: {issue.message}")

    return SetMetrics(
        capital=capital,
        grid_step=grid_step,
        base_lot=base_lot,
        multiplier=multiplier,
        basket_target=basket_target,
        max_grid=max_grid,
        total_lots=worst.total_lots,
        max_single_lot=max(lots_list) if lots_list else 0.0,
        estimated_dd_percent=worst.drawdown_pct,
        estimated_worst_floating_loss=worst.floating_pl,
        estimated_margin=worst.estimated_margin_used,
        margin_usage_percent=round(worst.estimated_margin_used / capital * 100.0, 4),
        grid_capacity_levels=capacity,
        price_move_to_basket_target=move_to_target,
        warnings=warnings,
        assumptions=list(dict.fromkeys(worst.assumptions + lot_assumptions)),
    )


def build_combinations(values: Dict[str, List[float]]) -> List[Dict[str, float]]:
    """Cartesian product over {capital, grid_step, base_lot, multiplier,
    basket_target, max_grid} value lists."""
    keys = ["capital", "grid_step", "base_lot", "multiplier", "basket_target", "max_grid"]
    combos: List[Dict[str, float]] = [{}]
    for key in keys:
        vals = values.get(key) or [None]
        new: List[Dict[str, float]] = []
        for combo in combos:
            for v in vals:
                nc = dict(combo)
                nc[key] = v
                new.append(nc)
        combos = new
        if len(combos) > MAX_COMBINATIONS:
            raise ValueError(
                f"Too many combinations ({len(combos)} > {MAX_COMBINATIONS}) - "
                f"reduce the value lists")
    # drop rows missing mandatory numeric fields
    out = []
    for combo in combos:
        if all(combo.get(k) is not None for k in keys):
            out.append({k: float(combo[k]) for k in keys})
    return out


def apply_filters(metrics: SetMetrics, filters: BuilderFilters) -> tuple:
    """Return (passed: bool, reasons: List[str])."""
    reasons = []
    if filters.max_dd_percent is not None and metrics.estimated_dd_percent > filters.max_dd_percent:
        reasons.append(f"DD {metrics.estimated_dd_percent:.1f}% > {filters.max_dd_percent}%")
    if filters.max_grid is not None and metrics.max_grid > filters.max_grid:
        reasons.append(f"Grid {metrics.max_grid} > {filters.max_grid}")
    if filters.max_lot is not None and metrics.max_single_lot > filters.max_lot:
        reasons.append(f"Max lot {metrics.max_single_lot} > {filters.max_lot}")
    if filters.max_margin_usage_percent is not None and \
            metrics.margin_usage_percent > filters.max_margin_usage_percent:
        reasons.append(f"Margin use {metrics.margin_usage_percent:.1f}% > "
                       f"{filters.max_margin_usage_percent}%")
    return (len(reasons) == 0, reasons)


# ---------------------------------------------------------------------------
# Set store (Module 9)
# ---------------------------------------------------------------------------
class SetStore:
    """Named set persistence at data/sets.json."""

    def __init__(self, path: Optional[str] = None):
        if path is None:
            base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
            path = os.path.join(base, "sets.json")
        self.path = path
        self.sets: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.sets = data.get("sets", {})
            except (json.JSONDecodeError, OSError):
                self.sets = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"schema": SETS_SCHEMA, "sets": self.sets}, f,
                      ensure_ascii=False, indent=2)

    def save_set(self, name: str, config: EAConfig, capital: float,
                 metrics: Optional[SetMetrics] = None) -> None:
        if not name or not name.strip():
            raise ValueError("set name must not be empty")
        self.sets[name.strip()] = {
            "config": config.to_dict(),
            "capital": capital,
            "metrics": metrics.to_dict() if metrics else None,
        }
        self._save()

    def duplicate_set(self, name: str, new_name: str) -> None:
        if name not in self.sets:
            raise KeyError(name)
        if not new_name.strip():
            raise ValueError("set name must not be empty")
        self.sets[new_name.strip()] = json.loads(json.dumps(self.sets[name]))
        self._save()

    def delete_set(self, name: str) -> None:
        if name not in self.sets:
            raise KeyError(name)
        del self.sets[name]
        self._save()

    def get_set(self, name: str) -> Optional[dict]:
        return self.sets.get(name)

    def names(self) -> List[str]:
        return sorted(self.sets.keys())

    def export_set(self, name: str, path: str) -> None:
        if name not in self.sets:
            raise KeyError(name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"schema": SETS_SCHEMA, "set": {name: self.sets[name]}},
                      f, ensure_ascii=False, indent=2)

    def import_set(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        sets = data.get("set") or data.get("sets")
        if not sets or not isinstance(sets, dict):
            raise ValueError("no set found in file")
        name, payload = next(iter(sets.items()))
        self.sets[name] = payload
        self._save()
        return name
