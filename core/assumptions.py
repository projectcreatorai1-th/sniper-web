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
    # Phase 1 metadata (optional; empty = not set on legacy entries)
    category: str = ""
    confidence: str = ""            # LOW / MEDIUM / HIGH
    affected_modules: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


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

    # --- Phase 1 completion: unknowns made explicit (no evidence -> UNKNOWN) ---
    def add2(aid: str, status: str, title: str, detail: str, category: str,
             confidence: str, modules=None, source: str = ""):
        a[aid] = Assumption(aid, status, title, detail, source,
                            category=category, confidence=confidence,
                            affected_modules=list(modules or []),
                            created_at="2026-09-24", updated_at="2026-09-24")

    add2("TICK_VALUE_ASSUMPTION_001", UNKNOWN,
         "Tick value (money per tick per lot) is not captured",
         "P/L model converts via contract size instead; per-broker tick value is "
         "unknown and not stored anywhere yet.",
         "Symbol specification", "LOW", ["core/symbol_profile.py"])
    add2("TICK_SIZE_ASSUMPTION_001", UNKNOWN,
         "Real broker tick size per symbol is not captured",
         "A default tick size exists in SymbolProfile as an editable value; the "
         "actual broker's tick size for the observed environment is unknown.",
         "Symbol specification", "LOW", ["core/symbol_profile.py"])
    add2("CONTRACT_SIZE_ASSUMPTION_001", MODEL_ASSUMPTION,
         "Contract size is configurable per symbol (XAUUSD=100 modeled)",
         "General form of XAUUSD_CONTRACT_ASSUMPTION_001: contract size comes "
         "from SymbolProfile/EnvironmentProfile, never assumed universal.",
         "Symbol specification", "MEDIUM", ["core/symbol_profile.py"],
         "See XAUUSD_CONTRACT_ASSUMPTION_001.")
    add2("VOLUME_STEP_ASSUMPTION_001", UNKNOWN,
         "Volume step / lot rounding semantics of the EX5 are unknown",
         "The model rounds to broker lot step (LOT_NORMALIZATION_ASSUMPTION_001) "
         "and reports out-of-bound lots (LOT_STEP_BOUNDARY_ASSUMPTION_001); how "
         "the EX5 itself rounds volume is unknown.",
         "Lot sizing", "LOW", ["core/calculations.py"])
    add2("PRICE_GAP_ASSUMPTION_001", UNKNOWN,
         "Behavior when price gaps over multiple grid levels is unknown",
         "When a single tick jumps past several GridStepUSD levels, whether the "
         "EA opens one order, several, or none is not documented or observed.",
         "Grid behavior", "LOW", ["core/grid.py", "core/worst_case.py"])
    add2("SLIPPAGE_ASSUMPTION_001", UNKNOWN,
         "Slippage is not modeled and its magnitude is unknown",
         "All simulation entries assume exact fills; real slippage is broker- "
         "and volatility-dependent.",
         "Cost model", "LOW", ["core/calculations.py"])
    add2("SPREAD_ASSUMPTION_001", UNKNOWN,
         "Spread magnitude is unknown (model excludes spread entirely)",
         "PL_CONVERSION_ASSUMPTION_001 excludes spread from P/L; the actual "
         "spread of the observed environment is not captured.",
         "Cost model", "LOW", ["core/calculations.py"])
    add2("COMMISSION_ASSUMPTION_001", UNKNOWN,
         "Commission model/value is unknown (model excludes commission)",
         "The P/L model excludes commission; the observed broker's commission "
         "structure is not captured anywhere yet.",
         "Cost model", "LOW", ["core/calculations.py"])
    add2("SWAP_ASSUMPTION_001", UNKNOWN,
         "Swap model/value is unknown (model excludes swap)",
         "The P/L model excludes swap; the observed broker's swap rates are not "
         "captured anywhere yet.",
         "Cost model", "LOW", ["core/calculations.py"])
    add2("MAGIC_NUMBER_ASSUMPTION_001", UNKNOWN,
         "The EA's magic number / order identification scheme is unknown",
         "No documentation or observation exists; nothing in the model relies "
         "on a magic number.",
         "Execution", "LOW", [])
    add2("ORDER_EXECUTION_ASSUMPTION_001", UNKNOWN,
         "Order execution model (market/limit, partial fills) is unknown",
         "The simulator assumes immediate full fills at computed prices.",
         "Execution", "LOW", ["core/worst_case.py"])
    add2("BID_ASK_ASSUMPTION_001", UNKNOWN,
         "The EA's use of bid/ask prices is unknown",
         "The model uses a single price series; which side of the spread the "
         "EA uses for triggers/entries is not documented.",
         "Execution", "LOW", ["core/calculations.py"])
    add2("TICK_BAR_TIMER_ASSUMPTION_001", UNKNOWN,
         "The EA's trigger basis (tick / bar open / timer) is unknown",
         "Grid trigger timing affects real behavior; the model is price-level "
         "based only.",
         "Execution", "LOW", ["core/grid.py"])
    add2("BROKER_MARGIN_ASSUMPTION_001", UNKNOWN,
         "Real broker margin rules (hedged/tiered) are unknown",
         "MARGIN_ASSUMPTION_001 gives the modeled formula; actual broker margin "
         "modes for the observed environment are not captured.",
         "Accounting", "LOW", ["core/calculations.py"],
         "See MARGIN_ASSUMPTION_001.")
    add2("CYCLE_START_RULE_ASSUMPTION_001", MODEL_ASSUMPTION,
         "Cycle begins at the first position/open event of a burst",
         "MODEL - NOT VERIFIED INTERNAL EA BEHAVIOR. Segmenting rule used by "
         "core/cycle.py for observed records and model snapshots.",
         "Lifecycle", "MEDIUM", ["core/cycle.py"])
    add2("CYCLE_END_RULE_ASSUMPTION_001", MODEL_ASSUMPTION,
         "Cycle ends at the configured terminal event (basket/emergency/time stop)",
         "MODEL - NOT VERIFIED INTERNAL EA BEHAVIOR. Terminal events close the "
         "simulated cycle in core/cycle.py.",
         "Lifecycle", "MEDIUM", ["core/cycle.py"])
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
