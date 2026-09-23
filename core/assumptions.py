"""Assumption Registry (Module 11).

Central registry of every assumption the simulation model relies on.
Every core calculation attaches assumption IDs to its structured result,
and the UI surfaces the status of each assumption:

  VERIFIED_FROM_DOCUMENTATION -> stated in the seller's PDF manual / report
  OBSERVED_FROM_TESTING       -> confirmed by user-recorded MT5 behavior
  MODEL_ASSUMPTION            -> our simulation model's assumption (not confirmed)
  UNKNOWN                     -> not documented, not modeled

User overrides (status changes + evidence notes) are persisted to
data/assumptions_overrides.json so evidence collected in Behavior
Verification can promote/adjust statuses without code changes.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

VERIFIED_FROM_DOCUMENTATION = "VERIFIED_FROM_DOCUMENTATION"
OBSERVED_FROM_TESTING = "OBSERVED_FROM_TESTING"
MODEL_ASSUMPTION = "MODEL_ASSUMPTION"
UNKNOWN = "UNKNOWN"

ALL_STATUSES = (VERIFIED_FROM_DOCUMENTATION, OBSERVED_FROM_TESTING, MODEL_ASSUMPTION, UNKNOWN)


@dataclass
class Assumption:
    assumption_id: str
    status: str
    title: str
    detail: str
    source: str = ""
    evidence: str = ""


# ---------------------------------------------------------------------------
# Baseline registry entries (code-defined defaults, overridable by user)
# ---------------------------------------------------------------------------
def _baseline() -> Dict[str, Assumption]:
    a: Dict[str, Assumption] = {}

    def add(aid: str, status: str, title: str, detail: str, source: str = ""):
        a[aid] = Assumption(aid, status, title, detail, source)

    # --- Lot sizing -------------------------------------------------------
    add(
        "LOT_FORMULA_ASSUMPTION_001", MODEL_ASSUMPTION,
        "Lot progression = BaseLot x LotMultiplier^(level-1)",
        "The manual states each next order uses the previous lot times LotMultiplier, "
        "but the exact formula (rounding, level indexing) is not documented. "
        "Model uses BaseLot x LotMultiplier^(level-1).",
        "Manual sections 5-7 describe the behavior, not the formula.",
    )
    add(
        "LOT_NORMALIZATION_ASSUMPTION_001", MODEL_ASSUMPTION,
        "Lots normalized (round) to broker lot step",
        "Raw formula output is rounded to the nearest broker lot step; how the EX5 "
        "rounds lots is not documented.",
    )
    add(
        "LOT_STEP_BOUNDARY_ASSUMPTION_001", MODEL_ASSUMPTION,
        "No automatic clamping to broker lot min/max inside the model",
        "The model reports out-of-bound lots through validation warnings instead of "
        "silently clamping; EX5 behaviour below lot minimum is UNKNOWN.",
    )
    # --- Grid -------------------------------------------------------------
    add(
        "GRID_DISTANCE_DOC_001", VERIFIED_FROM_DOCUMENTATION,
        "GridStepUSD is a price-distance between grid orders",
        "Manual section 4: GridStepUSD=5.0 means a new order is considered when price "
        "is about 5 dollars away from the previous order (XAUUSD example).",
        "Manual p.2 section 4; Full Report section 4 param #4.",
    )
    add(
        "GRID_TRIGGER_ASSUMPTION_001", MODEL_ASSUMPTION,
        "Next grid order triggers GridStepUSD away from the LAST order's price",
        "The distance is documented, but the exact reference point (last order vs "
        "average price vs cycle high/low) is not.",
    )
    add(
        "GRID_DIRECTION_ASSUMPTION_001", MODEL_ASSUMPTION,
        "Grid adds only on ADVERSE move (averaging)",
        "The manual says orders are placed as price moves away from the last order; "
        "whether a side also adds on favorable movement is not documented. "
        "Model: adds only against the side direction.",
    )
    add(
        "BOTH_SIDES_OPEN_AT_START_ASSUMPTION_001", MODEL_ASSUMPTION,
        "With UseGridBuy & UseGridSell both true, level-1 orders open on both sides at cycle start",
        "Not documented whether buy and sell baskets start simultaneously. "
        "Model: both sides open one level-1 order at cycle start.",
    )
    # --- Basket / partial -------------------------------------------------
    add(
        "BASKET_CLOSE_DOC_001", VERIFIED_FROM_DOCUMENTATION,
        "All orders close when total net basket profit reaches BasketCloseAllUSD",
        "Manual sections 8-9: the system watches the combined profit of the whole set "
        "and closes ALL orders when it reaches the target.",
        "Manual p.4 sections 8-9.",
    )
    add(
        "BASKET_SCOPE_ASSUMPTION_001", MODEL_ASSUMPTION,
        "Basket P/L scope = combined (both sides) by default",
        "It is not documented whether the basket groups both sides together or per "
        "side. Model default: combined; switchable in Simulation Model Rules.",
    )
    add(
        "PARTIAL_CLOSE_ASSUMPTION_001", MODEL_ASSUMPTION,
        "Partial close reduces total volume by ProfitPartialPercent%, applied pro-rata",
        "Manual says 'close about 50% of the part that meets the condition' - WHICH "
        "orders are selected and how volume is reduced is not documented. "
        "Model: pro-rata volume reduction across open orders.",
    )
    add(
        "PARTIAL_ONCE_DOC_001", VERIFIED_FROM_DOCUMENTATION,
        "At most one partial close per cycle when ProfitPartialOnlyOnce=true",
        "Manual section 16.",
    )
    add(
        "TRAILING_LOGIC_ASSUMPTION_001", MODEL_ASSUMPTION,
        "Trailing model: start at MainTrailStartProfitUSD, lock MainTrailLockUSD",
        "High-level behavior documented; step/refresh logic not documented. "
        "Disabled by default in baseline.",
    )
    # --- Cost / account model ----------------------------------------------
    add(
        "PL_CONVERSION_ASSUMPTION_001", MODEL_ASSUMPTION,
        "P/L(USD) = price difference x lots x contract_size; no spread/commission/swap",
        "Costs are broker specific and not included in the simulation.",
    )
    add(
        "XAUUSD_CONTRACT_ASSUMPTION_001", MODEL_ASSUMPTION,
        "XAUUSD contract size = 100 oz (0.1 lot moves ~$10 per $1 price move)",
        "Derived from the Full Report calculation reference; configure per broker in "
        "Symbol Profile settings.",
        "Full Report section 6 calculation note.",
    )
    add(
        "MARGIN_ASSUMPTION_001", MODEL_ASSUMPTION,
        "Margin = lots x contract_size x price / leverage x margin_rate",
        "Real broker margin (hedged margin rates, tiered leverage) differs; "
        "leverage and margin_rate are configurable account settings.",
    )
    add(
        "EXPOSURE_ASSUMPTION_001", MODEL_ASSUMPTION,
        "Exposure = notional value (lots x contract_size x price)",
        "Notional at reference/entry price; not a risk measure by itself.",
    )
    # --- Unknowns ----------------------------------------------------------
    add(
        "MAX_GRID_DEPTH_UNKNOWN_001", UNKNOWN,
        "Maximum number of grid levels inside the EX5 is not documented",
        "No Max orders parameter exists in the 27 documented parameters. "
        "The simulator lets the user choose the depth to analyze.",
    )
    add(
        "EA_BEHAVIOR_NOT_VERIFIED_001", UNKNOWN,
        "Internal EX5 logic cannot be verified without decompiling (prohibited)",
        "The .ex5 is compiled+compressed; decompiling is not allowed. Behavior must "
        "be verified through Behavior Verification sessions on demo/tester.",
    )
    add(
        "SYMBOL_INPUT_NAME_UNKNOWN_001", UNKNOWN,
        "Actual MT5 input name of parameter #1 (trade symbol) is unknown",
        "Full Report section 8; the field is modeled as 'TradeSymbol' (blank = chart symbol).",
    )
    add(
        "USEMARTINGALE_NAMING_NOTE_001", VERIFIED_FROM_DOCUMENTATION,
        "UseMartingale (infographic) == UsePositionSizeOptimization (PDF manual)",
        "Full Report section 3 note.",
    )
    add(
        "THAI_TIME_DOC_001", VERIFIED_FROM_DOCUMENTATION,
        "All time parameters use Thai time (ICT, UTC+7)",
        "Full Report section 3; manual sections 20, 23-27.",
    )
    add(
        "EMERGENCY_DOC_001", VERIFIED_FROM_DOCUMENTATION,
        "Emergency engages when price runs EmergencyDistanceFromCycleUSD beyond the trading frame",
        "Manual sections 17-19: with EmergencyCloseAllWhenTriggered=false it stops "
        "opening new orders; =true closes everything immediately.",
    )
    add(
        "EMERGENCY_FRAME_ASSUMPTION_001", MODEL_ASSUMPTION,
        "Trading frame modeled as the price range from cycle start price to the last grid order",
        "The manual does not define the exact frame boundaries used by the EX5.",
    )
    return a


class AssumptionRegistry:
    """Registry with optional persisted user overrides (evidence-based updates)."""

    def __init__(self, override_path: Optional[str] = None):
        self._items: Dict[str, Assumption] = _baseline()
        self.override_path = override_path
        if override_path and os.path.exists(override_path):
            try:
                with open(override_path, "r", encoding="utf-8") as f:
                    overrides = json.load(f)
                for aid, data in overrides.get("overrides", {}).items():
                    if aid in self._items:
                        item = self._items[aid]
                        if data.get("status") in ALL_STATUSES:
                            item.status = data["status"]
                        if data.get("evidence"):
                            item.evidence = data["evidence"]
            except (json.JSONDecodeError, OSError):
                # corrupted override file -> fall back to baseline silently
                pass

    # -- queries -----------------------------------------------------------
    def get(self, assumption_id: str) -> Assumption:
        if assumption_id not in self._items:
            raise KeyError(f"Unknown assumption id: {assumption_id}")
        return self._items[assumption_id]

    def try_get(self, assumption_id: str) -> Optional[Assumption]:
        return self._items.get(assumption_id)

    def all(self) -> List[Assumption]:
        return sorted(self._items.values(), key=lambda x: x.assumption_id)

    def by_status(self, status: str) -> List[Assumption]:
        return [a for a in self.all() if a.status == status]

    def status_of(self, assumption_id: str) -> str:
        return self.get(assumption_id).status

    def describe(self, assumption_ids: List[str]) -> List[dict]:
        out = []
        for aid in assumption_ids:
            a = self.try_get(aid)
            if a:
                out.append(asdict(a))
            else:
                out.append({"assumption_id": aid, "status": UNKNOWN,
                            "title": "Unregistered assumption", "detail": "", "source": "", "evidence": ""})
        return out

    # -- evidence-based updates ---------------------------------------------
    def set_status(self, assumption_id: str, status: str, evidence: str = "") -> None:
        if status not in ALL_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        a = self.get(assumption_id)
        a.status = status
        if evidence:
            a.evidence = evidence
        self._save_override(assumption_id, status, a.evidence)

    def _save_override(self, assumption_id: str, status: str, evidence: str) -> None:
        if not self.override_path:
            return
        overrides: Dict[str, dict] = {}
        if os.path.exists(self.override_path):
            try:
                with open(self.override_path, "r", encoding="utf-8") as f:
                    overrides = json.load(f).get("overrides", {})
            except (json.JSONDecodeError, OSError):
                overrides = {}
        overrides[assumption_id] = {"status": status, "evidence": evidence}
        os.makedirs(os.path.dirname(self.override_path), exist_ok=True)
        with open(self.override_path, "w", encoding="utf-8") as f:
            json.dump({"schema": "SNIPER_ASSUMPTION_OVERRIDES", "overrides": overrides}, f,
                      ensure_ascii=False, indent=2)


_DEFAULT_REGISTRY: Optional[AssumptionRegistry] = None


def default_registry() -> AssumptionRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        _DEFAULT_REGISTRY = AssumptionRegistry(os.path.join(base, "assumptions_overrides.json"))
    return _DEFAULT_REGISTRY


def reset_default_registry() -> None:
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None
