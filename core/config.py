"""EA configuration model (Module 1) - SNIPER CashFlow V1.68 baseline.

Versioned data model: every persisted dict carries schema="SNIPER_V1_68_CONFIG".

All 27 parameters from the seller's PDF manual are represented.
Parameter #1 (trade symbol) has an undocumented input name - see
SYMBOL_INPUT_NAME_UNKNOWN_001.

Presets are named exactly by their source (seller documentation) and are NOT
labeled "safest"/"best".
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, asdict, fields
from typing import Dict, List, Optional

SCHEMA = "SNIPER_V1_68_CONFIG"

# input name in MT5 unknown (SYMBOL_INPUT_NAME_UNKNOWN_001); blank = chart symbol
TIME_FIELDS = (
    "DailyResumeThaiTimeAfterEmergency",
    "ResumeNextDayThaiTimeAfterTarget",
    "FridayCloseAllThaiTime",
    "MondayRestartThaiTime",
)


@dataclass
class EAConfig:
    # 1. symbol selection (input name unknown; blank = current chart symbol)
    TradeSymbol: str = ""
    # grid
    UseGridBuy: bool = True
    UseGridSell: bool = True
    GridStepUSD: float = 5.0
    # lot / money management
    BaseLot: float = 0.1
    UsePositionSizeOptimization: bool = True      # aka UseMartingale (infographic name)
    LotMultiplier: float = 1.1
    # basket close
    UseBasketCloseAll: bool = True
    BasketCloseAllUSD: float = 1.68
    # trailing (main side)
    UseMainSideTrailing: bool = False
    MainTrailStartProfitUSD: float = 3.0
    MainTrailLockUSD: float = 1.5
    # partial close
    UseProfitPartialClose: bool = True
    ProfitPartialTriggerUSD: float = 2.0
    ProfitPartialPercent: float = 50.0
    ProfitPartialOnlyOnce: bool = True
    # emergency
    EnableEmergencyStop: bool = False
    EmergencyDistanceFromCycleUSD: float = 50.0
    EmergencyCloseAllWhenTriggered: bool = False
    DailyResumeThaiTimeAfterEmergency: str = "08:00"
    # daily target / schedule
    AccumTargetUSD: float = 0.0
    EnablePauseAfterAccumTargetHit: bool = False
    ResumeNextDayThaiTimeAfterTarget: str = "08:00"
    EnableFridayHardStop: bool = False
    FridayCloseAllAtTime: bool = False
    FridayCloseAllThaiTime: str = "17:00"
    MondayRestartThaiTime: str = "08:00"

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = SCHEMA
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "EAConfig":
        cfg = cls()
        known = {f.name for f in fields(cls)}
        schema = d.get("schema")
        for k, v in d.items():
            if k in known and v is not None:
                cur = getattr(cfg, k)
                if isinstance(cur, bool):
                    if isinstance(v, str):
                        v = v.strip().lower() in ("1", "true", "yes", "on")
                    v = bool(v)
                elif isinstance(cur, float):
                    v = float(v)
                elif isinstance(cur, str):
                    v = str(v)
                setattr(cfg, k, v)
        return cfg

    def copy(self) -> "EAConfig":
        return copy.deepcopy(self)

    # ------------------------------------------------------------------
    # Parameter metadata used by the settings UI (order = manual order)
    # (key, label, group, kind)
    # ------------------------------------------------------------------
    @staticmethod
    def parameter_meta() -> List[Dict[str, str]]:
        return [
            {"key": "TradeSymbol", "label": "Trade Symbol (blank = chart symbol)", "group": "Symbol / Grid", "kind": "str"},
            {"key": "UseGridBuy", "label": "UseGridBuy", "group": "Symbol / Grid", "kind": "bool"},
            {"key": "UseGridSell", "label": "UseGridSell", "group": "Symbol / Grid", "kind": "bool"},
            {"key": "GridStepUSD", "label": "GridStepUSD", "group": "Symbol / Grid", "kind": "float"},
            {"key": "BaseLot", "label": "BaseLot", "group": "Lot / Money Management", "kind": "float"},
            {"key": "UsePositionSizeOptimization", "label": "UsePositionSizeOptimization (UseMartingale)", "group": "Lot / Money Management", "kind": "bool"},
            {"key": "LotMultiplier", "label": "LotMultiplier", "group": "Lot / Money Management", "kind": "float"},
            {"key": "UseBasketCloseAll", "label": "UseBasketCloseAll", "group": "Basket Close", "kind": "bool"},
            {"key": "BasketCloseAllUSD", "label": "BasketCloseAllUSD", "group": "Basket Close", "kind": "float"},
            {"key": "UseMainSideTrailing", "label": "UseMainSideTrailing", "group": "Trailing", "kind": "bool"},
            {"key": "MainTrailStartProfitUSD", "label": "MainTrailStartProfitUSD", "group": "Trailing", "kind": "float"},
            {"key": "MainTrailLockUSD", "label": "MainTrailLockUSD", "group": "Trailing", "kind": "float"},
            {"key": "UseProfitPartialClose", "label": "UseProfitPartialClose", "group": "Partial Close", "kind": "bool"},
            {"key": "ProfitPartialTriggerUSD", "label": "ProfitPartialTriggerUSD", "group": "Partial Close", "kind": "float"},
            {"key": "ProfitPartialPercent", "label": "ProfitPartialPercent", "group": "Partial Close", "kind": "float"},
            {"key": "ProfitPartialOnlyOnce", "label": "ProfitPartialOnlyOnce", "group": "Partial Close", "kind": "bool"},
            {"key": "EnableEmergencyStop", "label": "EnableEmergencyStop", "group": "Emergency", "kind": "bool"},
            {"key": "EmergencyDistanceFromCycleUSD", "label": "EmergencyDistanceFromCycleUSD", "group": "Emergency", "kind": "float"},
            {"key": "EmergencyCloseAllWhenTriggered", "label": "EmergencyCloseAllWhenTriggered", "group": "Emergency", "kind": "bool"},
            {"key": "DailyResumeThaiTimeAfterEmergency", "label": "DailyResumeThaiTimeAfterEmergency", "group": "Emergency", "kind": "time"},
            {"key": "AccumTargetUSD", "label": "AccumTargetUSD", "group": "Daily Target / Schedule", "kind": "float"},
            {"key": "EnablePauseAfterAccumTargetHit", "label": "EnablePauseAfterAccumTargetHit", "group": "Daily Target / Schedule", "kind": "bool"},
            {"key": "ResumeNextDayThaiTimeAfterTarget", "label": "ResumeNextDayThaiTimeAfterTarget", "group": "Daily Target / Schedule", "kind": "time"},
            {"key": "EnableFridayHardStop", "label": "EnableFridayHardStop", "group": "Daily Target / Schedule", "kind": "bool"},
            {"key": "FridayCloseAllAtTime", "label": "FridayCloseAllAtTime", "group": "Daily Target / Schedule", "kind": "bool"},
            {"key": "FridayCloseAllThaiTime", "label": "FridayCloseAllThaiTime", "group": "Daily Target / Schedule", "kind": "time"},
            {"key": "MondayRestartThaiTime", "label": "MondayRestartThaiTime", "group": "Daily Target / Schedule", "kind": "time"},
        ]

    def parameter_count(self) -> int:
        return len(EAConfig.parameter_meta())


# ---------------------------------------------------------------------------
# Presets - values VERIFIED from seller's PDF manual + infographics
# (Full Report section 5, cross-checked against the two infographics).
# Names intentionally carry no "safest/best" wording.
# ---------------------------------------------------------------------------
PRESET_DEFAULT = EAConfig()


def _preset_500() -> EAConfig:
    cfg = EAConfig()
    # $500 infographic values: GridStep 5.0, BaseLot 0.1, Mult 1.1,
    # Basket 1.68, PartialTrigger 2.0, FridayCloseAll 17:00 (= defaults)
    return cfg


def _preset_3000() -> EAConfig:
    cfg = EAConfig()
    cfg.GridStepUSD = 4.8
    cfg.BaseLot = 0.18
    cfg.LotMultiplier = 1.08
    cfg.BasketCloseAllUSD = 8.88
    cfg.ProfitPartialTriggerUSD = 1.0
    cfg.FridayCloseAllThaiTime = "08:00"
    return cfg


def builtin_presets() -> Dict[str, EAConfig]:
    return {
        "Default (PDF manual V1.68)": _preset_500(),
        "Seller preset - Capital $500": _preset_500(),
        "Seller preset - Capital $3000": _preset_3000(),
    }
