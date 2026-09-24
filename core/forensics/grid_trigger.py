"""Grid trigger forensics — prove (or refute) the SPACING SEMANTICS.

Spacing (~5 USD median) is established; what is NOT established is which
price the EA references when it fires the next grid add. Hypotheses:

  H_PREV_ENTRY   next add fires when price crosses previous entry - step
  H_EXTREME      ... crosses the lowest (BUY) / highest (SELL) OPEN price - step
  H_AVG_PRICE    ... crosses the side's volume-weighted average price - k
  H_BASKET_ANCHOR... crosses the cycle's FIRST entry price - n*step
  H_SIDE_ANCHOR  ... crosses the side's first entry price - n*step
  H_FIXED_REF    ... fixed absolute price grid (multiples of step)
  H_DYNAMIC      ... anything else / spread- or time-dependent

Method: for each side-ladder of consecutive grid entries, compute the
implied distance d = anchor(prev_state) - new_entry (direction-adjusted).
A "cross-below" trigger implies d >= step with a tight lower bound at
`step` (upper tail = execution timing). The hypothesis whose d
distribution hugs the step most tightly (P5 ~= step, thin left tail)
is best supported; if several remain indistinguishable, semantics stay
PARTIAL/UNKNOWN — no guessing.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import List, Sequence

from core.forensics.cycle_reconstruction import Cycle


@dataclass(frozen=True)
class AddObservation:
    cycle_id: str
    account_id: str
    side: str
    level: int                       # ladder index of the new entry
    entry_price: float
    d_prev_entry: float              # distance from each candidate anchor
    d_extreme: float                 # (direction-adjusted: positive means
    d_avg_price: float               #  the new entry is BEYOND the anchor
    d_side_anchor_mult: float        #  by that many USD)
    d_fixed_ref: float


def _signed(side: str, anchor: float, entry: float) -> float:
    """Positive when the entry lies beyond the anchor in the grid direction."""
    return (anchor - entry) if side == "BUY" else (entry - anchor)


def collect_add_observations(cycles: Sequence[Cycle],
                             high_confidence_only: bool = True) -> List[AddObservation]:
    out: List[AddObservation] = []
    for cyc in cycles:
        if high_confidence_only and cyc.confidence != "HIGH":
            continue
        members = cyc.members
        if len(members) < 2:
            continue
        for side in ("BUY", "SELL"):
            ladder = [m for m in members if m["side"] == side]
            ladder.sort(key=lambda m: (m["open_time"], m["ticket"]))
            if len(ladder) < 2:
                continue
            open_set: List[dict] = []
            first_anchor = ladder[0]["open_price"]
            for lvl, m in enumerate(ladder, 1):
                if open_set:
                    prices = [p["open_price"] for p in open_set]
                    vol = sum(p["volume"] for p in open_set)
                    vwap = sum(p["open_price"] * p["volume"] for p in open_set) / vol
                    extreme = min(prices) if side == "BUY" else max(prices)
                    out.append(AddObservation(
                        cycle_id=cyc.cycle_id, account_id=cyc.account_id,
                        side=side, level=lvl, entry_price=m["open_price"],
                        d_prev_entry=_signed(side, open_set[-1]["open_price"],
                                             m["open_price"]),
                        d_extreme=_signed(side, extreme, m["open_price"]),
                        d_avg_price=_signed(side, vwap, m["open_price"]),
                        d_side_anchor_mult=_signed(side, first_anchor,
                                                   m["open_price"]) / (lvl - 1),
                        d_fixed_ref=abs(((m["open_price"] / 5.0) % 1.0) - 0.5)))
                open_set.append(m)
    return out


def _dist_stats(values: Sequence[float]) -> dict:
    v = sorted(values)
    n = len(v)
    if not n:
        return {"n": 0}
    return {"n": n,
            "min": round(v[0], 3),
            "p5": round(v[int(n * 0.05)], 3),
            "median": round(statistics.median(v), 3),
            "p95": round(v[int(n * 0.95)], 3),
            "below_4_5_pct": round(sum(1 for x in v if x < 4.5) / n * 100, 2),
            "in_4_5_6_pct": round(sum(1 for x in v if 4.5 <= x <= 6.0) / n * 100, 2)}


def replay_anchor_hypotheses(obs: Sequence[AddObservation], step: float = 5.0) -> dict:
    """Score each anchor by how closely its distance distribution hugs `step`.

    A cross-the-level trigger fires when price goes beyond anchor-step, so
    the observed distance must be >= step (left tail = data noise) and
    concentrate just above it (right tail = reaction/slippage). The best
    hypothesis maximizes in-band mass while keeping the left tail thin.
    """
    by_anchor = {
        "H_PREV_ENTRY": [o.d_prev_entry for o in obs],
        "H_EXTREME": [o.d_extreme for o in obs],
        "H_AVG_PRICE": [o.d_avg_price for o in obs],
    }
    scores = {}
    for name, vals in by_anchor.items():
        st = _dist_stats(vals)
        if st.get("n"):
            tight = st["in_4_5_6_pct"] - st["below_4_5_pct"] * 2  # penalize left tail
            scores[name] = {**st, "score": round(tight, 2)}
        else:
            scores[name] = {"n": 0, "score": -999.0}
    # anchor-multiple and fixed-grid diagnostics (not scored the same way)
    scores["H_SIDE_ANCHOR_MULT_per_level"] = _dist_stats(
        [o.d_side_anchor_mult for o in obs])
    scores["H_FIXED_REF_residual"] = _dist_stats([o.d_fixed_ref for o in obs])
    return {"step_usd": step, "anchors": scores}


def anchor_conclusion(replay: dict) -> dict:
    anchors = {k: v for k, v in replay["anchors"].items()
               if v.get("score") is not None and v.get("n")}
    if not anchors:
        return {"status": "UNKNOWN",
                "supported": [], "note": "no high-confidence observations"}
    best = max(anchors, key=lambda k: anchors[k]["score"])
    best_score = anchors[best]["score"]
    runner_ups = [k for k in anchors
                  if k != best and anchors[k]["score"] >= best_score - 5.0]
    if runner_ups:
        return {"status": "PARTIAL",
                "supported": [best] + runner_ups,
                "note": "several anchor hypotheses remain compatible "
                        "(in averaging-down ladders they coincide); "
                        "semantics not proven"}
    return {"status": "PARTIAL",
            "supported": [best],
            "note": "single best anchor, but close-side data cannot observe "
                    "the evaluation instant; remains PARTIAL until a "
                    "controlled test"}
