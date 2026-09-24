"""Behavior comparators (Phase 2): OBSERVED vs MODEL vs UNKNOWN.

Every comparator consumes canonical BehaviorRecords and produces structured
BehaviorCheckResult rows (check_id / observed_value / model_value /
difference / status / evidence_ids / assumption_ids / notes).

Rules enforced here:
- model values ALWAYS come from core.calculations / config (SSOT) - this
  module never re-implements a formula
- statuses: MATCH / PARTIAL_MATCH / MISMATCH / UNKNOWN / INSUFFICIENT_DATA
- nothing auto-corrects the model; matches are consistency observations,
  never proof of internal EA rules
- EmergencyComparator always shows OBSERVED DEFAULT 90.0 (E007) and
  RECOMMENDED PRESET 50.0 (E008) side by side with sources
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional

from core import calculations as c
from core.config import EAConfig
from core.model_rules import SimulationModelRules
from core.mt5_adapters import (
    BehaviorRecord,
    EVENT_ADD_GRID,
    EVENT_BASKET_CLOSE,
    EVENT_EMERGENCY,
    EVENT_NEW_CYCLE,
    EVENT_OPEN_POSITION,
    EVENT_PARTIAL_CLOSE,
)
from core.symbol_profile import SymbolProfile

MATCH = "MATCH"
PARTIAL_MATCH = "PARTIAL_MATCH"
MISMATCH = "MISMATCH"
UNKNOWN = "UNKNOWN"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
COMPARISON_STATUSES = (MATCH, PARTIAL_MATCH, MISMATCH, UNKNOWN, INSUFFICIENT_DATA)

CONF_HIGH, CONF_MEDIUM, CONF_LOW, CONF_UNKNOWN = "HIGH", "MEDIUM", "LOW", "UNKNOWN"

SCHEMA = "SNIPER_BEHAVIOR_CHECK_V1"


@dataclass
class BehaviorCheckResult:
    check_id: str
    title: str
    status: str
    observed_value: str = "?"
    model_value: str = "?"
    difference: str = ""
    evidence_ids: List[str] = field(default_factory=list)
    assumption_ids: List[str] = field(default_factory=list)
    confidence: str = CONF_UNKNOWN
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = SCHEMA
        return d


def _fmt(v, nd=2) -> str:
    if v is None:
        return "?"
    if isinstance(v, float):
        return f"{v:.{nd}f}".rstrip("0").rstrip(".") or "0"
    return str(v)


def _entry_events(records: List[BehaviorRecord], side: str) -> List[BehaviorRecord]:
    """Entry/add events for one side (price-independent, unlike the price-
    requiring helper in model_vs_observed)."""
    return [r for r in records
            if r.side == side and r.event in (EVENT_NEW_CYCLE, EVENT_OPEN_POSITION,
                                              EVENT_ADD_GRID)]


def _count_status(results: List[BehaviorCheckResult]) -> dict:
    counts = {s: 0 for s in COMPARISON_STATUSES}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# 1) Grid behavior
# ---------------------------------------------------------------------------
def compare_grid_behavior(records: List[BehaviorRecord], config: EAConfig,
                          profile: SymbolProfile, rules: SimulationModelRules,
                          evidence_ids: Optional[List[str]] = None) -> List[BehaviorCheckResult]:
    out: List[BehaviorCheckResult] = []
    step = config.GridStepUSD
    tol = max(profile.tick_size, step * 0.10)

    for side in ("BUY", "SELL"):
        evs = _entry_events(records, side)
        entries = [r for r in evs if r.price is not None]
        pfx = f"GRID-{side[:4]}"

        if not evs:
            out.append(BehaviorCheckResult(
                f"{pfx}-FIRST", f"{side} first entry", INSUFFICIENT_DATA,
                observed_value="no entries", model_value="level 1 at cycle start",
                evidence_ids=evidence_ids or [],
                assumption_ids=["GRID_TRIGGER_ASSUMPTION_001"]))
            continue

        first = evs[0]
        out.append(BehaviorCheckResult(
            f"{pfx}-FIRST", f"{side} first entry", MATCH,
            observed_value=f"price {_fmt(first.price)} lot {_fmt(first.lot)}",
            model_value="anchor (level 1)",
            evidence_ids=evidence_ids or [], confidence=CONF_MEDIUM,
            assumption_ids=["GRID_TRIGGER_ASSUMPTION_001"],
            notes="First observed entry anchors the model comparison."))

        prices = [r.price for r in entries]
        spacings = [(i, abs(b - a)) for i, (a, b) in enumerate(zip(prices, prices[1:]), start=2)]

        def spacing_check(cid, title, idx_pairs):
            data = [(lvl, obs) for lvl, obs in idx_pairs if obs is not None]
            if not data:
                return BehaviorCheckResult(cid, title, INSUFFICIENT_DATA,
                                           observed_value="no priced pairs",
                                           model_value=f"{_fmt(step)}",
                                           evidence_ids=evidence_ids or [],
                                           assumption_ids=["GRID_TRIGGER_ASSUMPTION_001"])
            bad = [(lvl, obs) for lvl, obs in data if abs(obs - step) > tol]
            if not bad:
                return BehaviorCheckResult(
                    cid, title, MATCH,
                    observed_value=", ".join(f"L{lvl}:{_fmt(obs, 3)}" for lvl, obs in data),
                    model_value=_fmt(step), difference="0 (within tolerance)",
                    evidence_ids=evidence_ids or [], confidence=CONF_MEDIUM,
                    assumption_ids=["GRID_TRIGGER_ASSUMPTION_001",
                                    "GRID_DISTANCE_DOC_001"])
            if len(bad) < len(data):
                return BehaviorCheckResult(
                    cid, title, PARTIAL_MATCH,
                    observed_value=", ".join(f"L{lvl}:{_fmt(obs, 3)}" for lvl, obs in data),
                    model_value=_fmt(step),
                    difference=f"{len(bad)}/{len(data)} outside tolerance",
                    evidence_ids=evidence_ids or [], confidence=CONF_MEDIUM,
                    assumption_ids=["GRID_TRIGGER_ASSUMPTION_001"],
                    notes="Some spacings within tolerance, some not.")
            return BehaviorCheckResult(
                cid, title, MISMATCH,
                observed_value=", ".join(f"L{lvl}:{_fmt(obs, 3)}" for lvl, obs in data),
                model_value=_fmt(step),
                difference=f"all {len(data)} outside tolerance",
                evidence_ids=evidence_ids or [], confidence=CONF_MEDIUM,
                assumption_ids=["GRID_TRIGGER_ASSUMPTION_001"])

        pairs2 = [(lvl, obs) for lvl, obs in spacings if lvl == 2] or \
                 [(2, None) if len(prices) < 2 else (2, abs(prices[1] - prices[0]))]
        out.append(spacing_check(f"{pfx}-SECOND", f"{side} second grid spacing", pairs2))
        pairs3 = [(lvl, obs) for lvl, obs in spacings if lvl == 3]
        if len(prices) >= 3:
            pairs3 = pairs3 or [(3, abs(prices[2] - prices[1]))]
        else:
            pairs3 = [(3, None)]
        out.append(spacing_check(f"{pfx}-THIRD", f"{side} third grid spacing", pairs3))
        rest = [(lvl, obs) for lvl, obs in spacings if lvl > 3]
        out.append(spacing_check(f"{pfx}-SUBSEQUENT", f"{side} subsequent grids", rest))

        if len(prices) >= 2:
            anchor = prices[0]
            max_dist = max(abs(p - anchor) for p in prices)
            model_dist = (len(prices) - 1) * step
            out.append(BehaviorCheckResult(
                f"{pfx}-DISTANCE", f"{side} max price distance from start", MATCH
                if abs(max_dist - model_dist) <= max(tol, step * 0.5 * len(prices)) else MISMATCH,
                observed_value=_fmt(max_dist), model_value=_fmt(model_dist),
                difference=_fmt(abs(max_dist - model_dist)),
                evidence_ids=evidence_ids or [], confidence=CONF_LOW,
                assumption_ids=["GRID_TRIGGER_ASSUMPTION_001"],
                notes="Aggregate bound; per-level spacing checked separately."))
        else:
            out.append(BehaviorCheckResult(
                f"{pfx}-DISTANCE", f"{side} max price distance", INSUFFICIENT_DATA,
                evidence_ids=evidence_ids or [],
                assumption_ids=["GRID_TRIGGER_ASSUMPTION_001"]))

        # direction: BUY adds DOWN, SELL adds UP
        wrong = sum(1 for a, b in zip(prices, prices[1:])
                    if (side == "BUY" and b > a) or (side == "SELL" and b < a))
        out.append(BehaviorCheckResult(
            f"{pfx}-DIRECTION", f"{side} grid direction", MATCH if wrong == 0 else MISMATCH,
            observed_value=f"{len(prices) - wrong - 1}/{len(prices) - 1} add toward adverse",
            model_value="adds only on adverse move",
            difference=str(wrong) if wrong else "0",
            evidence_ids=evidence_ids or [], confidence=CONF_MEDIUM,
            assumption_ids=["GRID_DIRECTION_ASSUMPTION_001"]))

        lvls = [r.grid_level for r in evs if r.grid_level is not None]
        if lvls:
            seq_ok = all(b == a + 1 for a, b in zip(lvls, lvls[1:])) and lvls[0] == 1
            out.append(BehaviorCheckResult(
                f"{pfx}-LEVEL", f"{side} grid level sequence",
                MATCH if seq_ok else MISMATCH,
                observed_value=",".join(map(str, lvls)), model_value="1,2,3,...",
                evidence_ids=evidence_ids or [], confidence=CONF_LOW,
                assumption_ids=["GRID_TRIGGER_ASSUMPTION_001"]))
        else:
            out.append(BehaviorCheckResult(
                f"{pfx}-LEVEL", f"{side} grid level sequence", UNKNOWN,
                observed_value="no explicit grid_level recorded",
                evidence_ids=evidence_ids or [],
                assumption_ids=["GRID_TRIGGER_ASSUMPTION_001"]))

        # multiple-level gap behavior: unknown by definition
        gaps = [(lvl, obs) for lvl, obs in spacings if obs is not None and obs > step * 1.5]
        out.append(BehaviorCheckResult(
            f"{pfx}-GAP", f"{side} multiple-level gap behavior",
            UNKNOWN if gaps else INSUFFICIENT_DATA,
            observed_value=", ".join(f"L{lvl}:{_fmt(obs)}" for lvl, obs in gaps) or "none observed",
            model_value="not modeled",
            evidence_ids=evidence_ids or [], confidence=CONF_UNKNOWN,
            assumption_ids=["PRICE_GAP_ASSUMPTION_001"],
            notes="Gap behavior is UNKNOWN - the model does not guess whether "
                  "the EA opens 1 or several orders across a gap."))
    return out


# ---------------------------------------------------------------------------
# 2) Lot behavior
# ---------------------------------------------------------------------------
def compare_lot_behavior(records: List[BehaviorRecord], config: EAConfig,
                         profile: SymbolProfile, rules: SimulationModelRules,
                         evidence_ids: Optional[List[str]] = None) -> dict:
    rows = []
    half_step = (profile.lot_step or 0.01) / 2 + 1e-9
    for side in ("BUY", "SELL"):
        for i, r in enumerate(_entry_events(records, side), start=1):
            if r.lot is None:
                continue
            model_lot = c.lot_for_level(config, i, rules, profile).value  # SSOT
            diff = abs(r.lot - model_lot)
            if abs(diff) < 1e-9:
                res, rounding = MATCH, "exact"
            elif diff <= half_step:
                res, rounding = MATCH, "within lot step (rounding)"
            else:
                res, rounding = MISMATCH, "off"
            on_step = (profile.lot_step <= 0 or
                       abs(round(r.lot / profile.lot_step) * profile.lot_step - r.lot) < 1e-9)
            rows.append({
                "side": side, "level": i, "observed_lot": r.lot,
                "model_lot": model_lot, "difference": round(r.lot - model_lot, 8),
                "rounding": rounding, "on_volume_step": on_step,
                "volume_step": profile.lot_step, "result": res,
            })
    if not rows:
        summary = INSUFFICIENT_DATA
    else:
        n_match = sum(1 for r in rows if r["result"] == MATCH)
        summary = MATCH if n_match == len(rows) else \
            (PARTIAL_MATCH if n_match else MISMATCH)
    return {
        "schema": "SNIPER_LOT_COMPARISON_V1",
        "rows": rows, "summary": summary,
        "assumption_ids": ["LOT_FORMULA_ASSUMPTION_001",
                           "LOT_NORMALIZATION_ASSUMPTION_001",
                           "VOLUME_STEP_ASSUMPTION_001"],
        "evidence_ids": evidence_ids or [],
        "notes": ("Matches are consistency observations against the MODEL lot "
                  "formula (BaseLot x LotMultiplier^(level-1), rounded) - they "
                  "are NOT proof of the internal EA formula until enough "
                  "independent observations exist."),
    }


# ---------------------------------------------------------------------------
# 3) Buy/Sell relationship
# ---------------------------------------------------------------------------
def compare_buysell_behavior(records: List[BehaviorRecord], config: EAConfig,
                             evidence_ids: Optional[List[str]] = None) -> List[BehaviorCheckResult]:
    ev = []
    for s in ("BUY", "SELL"):
        got = _entry_events(records, s)
        if got:
            ev.append((s, got))
    present = [s for s, _ in ev]
    pattern = ("BOTH_SIDES" if len(present) == 2
               else present[0] + "_ONLY" if present else "NONE")
    expected = ("BOTH_SIDES" if config.UseGridBuy and config.UseGridSell
                else "BUY_ONLY" if config.UseGridBuy else "SELL_ONLY"
                if config.UseGridSell else "NONE")

    out = [BehaviorCheckResult(
        "BS-PATTERN", "Observed side pattern",
        MATCH if pattern == expected else MISMATCH if pattern != "NONE" else INSUFFICIENT_DATA,
        observed_value=pattern, model_value=expected,
        evidence_ids=evidence_ids or [], confidence=CONF_MEDIUM,
        assumption_ids=["BOTH_SIDES_OPEN_AT_START_ASSUMPTION_001"],
        notes="Pattern observation - consistency with config, NOT proof of an EA rule.")]

    if len(ev) == 2:
        first_side, first_evs = ev[0]
        other_side, other_evs = ev[1]
        first_add = next((r for r in first_evs if r.event == EVENT_ADD_GRID), None)
        other_open = other_evs[0]
        if first_add is None:
            status, note = MATCH, "no grid add before observation ended - both " \
                                  "sides opened and stayed at level 1 (consistent " \
                                  "with both-at-start; consistency, not proof)"
        elif not other_open.timestamp or not first_add.timestamp:
            status, note = UNKNOWN, "timestamps missing - ordering unverifiable"
        elif other_open.timestamp <= first_add.timestamp:
            status, note = MATCH, ("opposite side opened before any grid add - "
                                   "consistent with BOTH_SIDES_OPEN_AT_START "
                                   "(observation, NOT an EA rule claim)")
        else:
            status, note = MISMATCH, ("opposite side opened AFTER the first grid "
                                      "add - contradicts both-at-start model default")
        out.append(BehaviorCheckResult(
            "BS-OPPOSITE", "Opposite-side entry timing", status,
            observed_value=f"{other_side} first open @ {other_open.timestamp or '?'}",
            model_value="opposite level-1 at cycle start",
            evidence_ids=evidence_ids or [],
            confidence=CONF_MEDIUM if status != UNKNOWN else CONF_UNKNOWN,
            assumption_ids=["BOTH_SIDES_OPEN_AT_START_ASSUMPTION_001",
                            "BASKET_SCOPE_ASSUMPTION_001"], notes=note))
    out.append(BehaviorCheckResult(
        "BS-SCOPE", "Basket/cycle scope (combined vs per side)", UNKNOWN,
        observed_value="scope not derivable without per-side close detail",
        model_value="COMBINED (default assumption)",
        evidence_ids=evidence_ids or [], confidence=CONF_UNKNOWN,
        assumption_ids=["BASKET_SCOPE_ASSUMPTION_001"],
        notes="Scope stays UNKNOWN until closes attributable to one side are observed."))
    return out


# ---------------------------------------------------------------------------
# 4) Basket behavior
# ---------------------------------------------------------------------------
def compare_basket_behavior(records: List[BehaviorRecord], config: EAConfig,
                            evidence_ids: Optional[List[str]] = None) -> List[BehaviorCheckResult]:
    closes = [r for r in records if r.event == EVENT_BASKET_CLOSE]
    out: List[BehaviorCheckResult] = []
    if not closes:
        out.append(BehaviorCheckResult(
            "BASKET-CLOSE", "Basket close observed", INSUFFICIENT_DATA,
            observed_value="no BASKET_CLOSE events",
            model_value=f"close at BasketCloseAllUSD={_fmt(config.BasketCloseAllUSD)}",
            evidence_ids=evidence_ids or [],
            assumption_ids=["BASKET_CLOSE_DOC_001"]))
        return out
    target = config.BasketCloseAllUSD
    tol = 0.5
    results = []
    comp_rows = []
    for i, r in enumerate(closes, start=1):
        pl = r.basket_pl if r.basket_pl is not None else r.floating_pl
        if pl is None:
            results.append(UNKNOWN)
            comp_rows.append({"close": i, "basket_pl": None, "price_pl": None,
                              "commission": r.commission, "swap": r.swap,
                              "net": None,
                              "composition": "UNKNOWN (no P/L recorded)"})
            continue
        results.append(MATCH if abs(pl - target) <= tol else MISMATCH)
        # cost separation: never assume basket P/L == price P/L
        if r.commission is None and r.swap is None:
            composition = ("UNKNOWN - source has no commission/swap values; "
                           "basket P/L vs price-only P/L cannot be separated")
            price_pl = None
        else:
            price_pl = round(pl - (r.commission or 0.0) - (r.swap or 0.0), 8)
            composition = f"price~{price_pl} + comm~{r.commission} + swap~{r.swap}"
        comp_rows.append({"close": i, "basket_pl": pl, "price_pl": price_pl,
                          "commission": r.commission, "swap": r.swap,
                          "net": pl, "composition": composition})
    n_match = sum(1 for x in results if x == MATCH)
    summary = MATCH if n_match == len(results) else \
        (PARTIAL_MATCH if n_match else MISMATCH)
    out.append(BehaviorCheckResult(
        "BASKET-TARGET", "Basket close vs target", summary,
        observed_value=", ".join(_fmt(r.basket_pl if r.basket_pl is not None
                                      else r.floating_pl) for r in closes),
        model_value=_fmt(target),
        difference=f"{n_match}/{len(results)} within ±{tol}",
        evidence_ids=evidence_ids or [], confidence=CONF_MEDIUM,
        assumption_ids=["BASKET_CLOSE_DOC_001", "PL_CONVERSION_ASSUMPTION_001"]))
    out.append(BehaviorCheckResult(
        "BASKET-COSTS", "P/L composition (price / commission / swap / net)",
        UNKNOWN if any(r["price_pl"] is None for r in comp_rows) else MATCH,
        observed_value="; ".join(r["composition"] for r in comp_rows),
        model_value="price P/L + commission + swap = net",
        evidence_ids=evidence_ids or [], confidence=CONF_UNKNOWN,
        assumption_ids=["COMMISSION_ASSUMPTION_001", "SWAP_ASSUMPTION_001",
                        "PL_CONVERSION_ASSUMPTION_001"],
        notes="When the source lacks cost values the split stays UNKNOWN - "
              "basket P/L is never assumed equal to price P/L.",
        ))
    return out


# ---------------------------------------------------------------------------
# 5) Partial close behavior
# ---------------------------------------------------------------------------
def compare_partial_behavior(records: List[BehaviorRecord], config: EAConfig,
                             evidence_ids: Optional[List[str]] = None) -> List[BehaviorCheckResult]:
    partials = [r for r in records if r.event == EVENT_PARTIAL_CLOSE]
    out: List[BehaviorCheckResult] = []
    if not partials:
        out.append(BehaviorCheckResult(
            "PARTIAL-OBSERVED", "Partial close observed", INSUFFICIENT_DATA,
            observed_value="no PARTIAL_CLOSE events",
            model_value=("closes ProfitPartialPercent% at "
                         f"{_fmt(config.ProfitPartialTriggerUSD)} USD"
                         if config.UseProfitPartialClose else "disabled in config"),
            evidence_ids=evidence_ids or [],
            assumption_ids=["PARTIAL_CLOSE_ASSUMPTION_001"]))
        return out

    for i, r in enumerate(partials, start=1):
        trig = r.basket_pl if r.basket_pl is not None else r.floating_pl
        out.append(BehaviorCheckResult(
            f"PARTIAL-TRIG-{i}", f"Partial #{i} trigger P/L",
            MATCH if trig is not None and abs(trig - config.ProfitPartialTriggerUSD) <= 0.5
            else MISMATCH if trig is not None else UNKNOWN,
            observed_value=_fmt(trig), model_value=_fmt(config.ProfitPartialTriggerUSD),
            difference=_fmt(abs((trig or 0) - config.ProfitPartialTriggerUSD))
            if trig is not None else "",
            evidence_ids=evidence_ids or [], confidence=CONF_LOW,
            assumption_ids=["PARTIAL_CLOSE_ASSUMPTION_001"]))

        idx = records.index(r)
        before = next((x for x in reversed(records[:idx]) if x.total_lots is not None), None)
        after = next((x for x in records[idx + 1:] if x.total_lots is not None), None)
        if before and after and before.total_lots:
            pct = (before.total_lots - after.total_lots) / before.total_lots * 100
            out.append(BehaviorCheckResult(
                f"PARTIAL-PCT-{i}", f"Partial #{i} volume %",
                MATCH if abs(pct - config.ProfitPartialPercent) <= 1.0 else MISMATCH,
                observed_value=f"{pct:.2f}%",
                model_value=f"{_fmt(config.ProfitPartialPercent)}%",
                difference=f"{abs(pct - config.ProfitPartialPercent):.2f}pp",
                evidence_ids=evidence_ids or [], confidence=CONF_LOW,
                assumption_ids=["PARTIAL_CLOSE_ASSUMPTION_001"],
                notes="Consistent with pro-rata total-lot reduction; scope still "
                      "needs position-level detail to prove."))
        else:
            out.append(BehaviorCheckResult(
                f"PARTIAL-PCT-{i}", f"Partial #{i} volume %", UNKNOWN,
                observed_value="total_lots before/after not recorded",
                evidence_ids=evidence_ids or [],
                assumption_ids=["PARTIAL_CLOSE_ASSUMPTION_001"]))

        pb = next((x for x in reversed(records[:idx]) if x.position_count is not None), None)
        pa = next((x for x in records[idx + 1:] if x.position_count is not None), None)
        if pb is not None and pa is not None:
            if pb.position_count == pa.position_count:
                scope = "basket-level OR total-lot (counts unchanged; indistinguishable)"
            elif pa.position_count == pb.position_count - 1:
                scope = "position-level (one position reduced/closed)"
            else:
                scope = "UNKNOWN (counts changed unexpectedly)"
        else:
            scope = "UNKNOWN (position counts not recorded around event)"
        out.append(BehaviorCheckResult(
            f"PARTIAL-SCOPE-{i}", f"Partial #{i} scope", UNKNOWN,
            observed_value=scope,
            model_value="pro-rata total volume (PARTIAL_CLOSE_ASSUMPTION_001)",
            evidence_ids=evidence_ids or [], confidence=CONF_UNKNOWN,
            assumption_ids=["PARTIAL_CLOSE_ASSUMPTION_001"],
            notes="Scope candidates: position-level / basket-level / "
                  "profitable-only / side-level / total-lot / unknown - the "
                  "analyzer does not pick one without evidence."))
    return out


# ---------------------------------------------------------------------------
# 6) Emergency behavior (always shows observed 90.0 vs preset 50.0)
# ---------------------------------------------------------------------------
def compare_emergency_behavior(records: List[BehaviorRecord], config: EAConfig,
                               profile: SymbolProfile,
                               evidence_ids: Optional[List[str]] = None) -> List[BehaviorCheckResult]:
    from core.cycle import build_cycles_from_records

    out: List[BehaviorCheckResult] = []
    out.append(BehaviorCheckResult(
        "EMG-VALUES", "Emergency distance reference values (kept separate)",
        UNKNOWN,
        observed_value="OBSERVED DEFAULT = 90.0 (E007, installation video)",
        model_value=(f"RECOMMENDED PRESET = 50.0 (E008); model config = "
                     f"{_fmt(config.EmergencyDistanceFromCycleUSD)}"),
        evidence_ids=list(dict.fromkeys((evidence_ids or []) + ["E007", "E008"])),
        confidence=CONF_UNKNOWN,
        assumption_ids=["EMERGENCY_FRAME_ASSUMPTION_001", "EMERGENCY_DOC_001"],
        notes="90.0 and 50.0 are distinct records and are never merged."))

    events = [r for r in records if r.event == EVENT_EMERGENCY]
    if not events:
        out.append(BehaviorCheckResult(
            "EMG-OBSERVED", "Emergency events", INSUFFICIENT_DATA,
            observed_value="none observed",
            model_value=("armed at "
                         f"{_fmt(config.EmergencyDistanceFromCycleUSD)} USD"
                         if config.EnableEmergencyStop else "disabled in config"),
            evidence_ids=evidence_ids or [],
            assumption_ids=["EMERGENCY_DOC_001"]))
        return out

    cycles = build_cycles_from_records(records)
    model_val = config.EmergencyDistanceFromCycleUSD
    tol = max(1.0, model_val * 0.05, 90.0 * 0.05)
    for i, r in enumerate(events, start=1):
        cyc = next((cy for cy in cycles
                    if any(e.get("timestamp") == r.timestamp for e in cy.events)), None)
        ref = cyc.start_price if cyc else None
        if ref is None or r.price is None:
            out.append(BehaviorCheckResult(
                f"EMG-DIST-{i}", f"Emergency #{i} distance", UNKNOWN,
                observed_value=f"trigger {_fmt(r.price)} / reference ?",
                model_value=_fmt(model_val),
                evidence_ids=evidence_ids or [], confidence=CONF_UNKNOWN,
                assumption_ids=["EMERGENCY_FRAME_ASSUMPTION_001"],
                notes="Reference (cycle start price) or trigger price missing."))
            continue
        dist = abs(r.price - ref)
        if abs(dist - model_val) <= tol:
            status, note = MATCH, "matches model config distance"
        elif abs(dist - 90.0) <= tol:
            status = MISMATCH
            note = ("distance matches OBSERVED DEFAULT 90.0 (E007) but NOT the "
                    "model/preset 50.0 - recorded as mismatch, no auto-correction")
        else:
            status, note = UNKNOWN, "matches neither reference value"
        out.append(BehaviorCheckResult(
            f"EMG-DIST-{i}", f"Emergency #{i} distance", status,
            observed_value=f"{_fmt(dist)} (trigger {_fmt(r.price)}, ref {_fmt(ref)})",
            model_value=f"{_fmt(model_val)} (preset; observed default = 90.0)",
            difference=_fmt(abs(dist - model_val)),
            evidence_ids=list(dict.fromkeys((evidence_ids or []) + ["E007"])),
            confidence=CONF_LOW,
            assumption_ids=["EMERGENCY_FRAME_ASSUMPTION_001", "EMERGENCY_DOC_001"],
            notes=note))
    return out


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------
def run_all_comparators(records: List[BehaviorRecord], config: EAConfig,
                        profile: SymbolProfile, rules: SimulationModelRules,
                        evidence_ids: Optional[List[str]] = None) -> dict:
    from datetime import datetime
    lot = compare_lot_behavior(records, config, profile, rules, evidence_ids)
    checks = (
        compare_grid_behavior(records, config, profile, rules, evidence_ids)
        + compare_buysell_behavior(records, config, evidence_ids)
        + compare_basket_behavior(records, config, evidence_ids)
        + compare_partial_behavior(records, config, evidence_ids)
        + compare_emergency_behavior(records, config, profile, evidence_ids)
    )
    all_rows = checks + [BehaviorCheckResult(
        "LOT-SUMMARY", "Lot progression summary", lot["summary"],
        observed_value=f"{sum(1 for r in lot['rows'] if r['result'] == MATCH)}/"
                       f"{len(lot['rows'])} levels match",
        model_value="BaseLot x Multiplier^(level-1), rounded",
        evidence_ids=lot["evidence_ids"], confidence=CONF_MEDIUM,
        assumption_ids=lot["assumption_ids"], notes=lot["notes"])]
    return {
        "schema": "SNIPER_BEHAVIOR_COMPARISON_V1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "counts": _count_status(all_rows),
        "checks": [r.to_dict() for r in checks],
        "lot": lot,
        "evidence_ids": evidence_ids or [],
    }
