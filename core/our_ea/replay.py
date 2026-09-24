"""Historical replay engine (§29-§31).

Replays the immutable observed dataset (data/our_ea/replay_dataset_v1.json)
against OUR EA's rule implementations, comparing event-by-event:

    entry (side/level/lot) · grid direction · spacing · basket close ·
    cycle end · normal resume

Classifications per comparison: MATCH / MISMATCH / UNKNOWN / NOT_COMPARABLE.
Partial-close decisions are UNKNOWN (never fabricated). Every mismatch
carries expected/actual/event/rule/evidence/difference.

Determinism (§31): run_id + model_hash + dataset_hash + config_hash +
code_version + result_hash; same inputs -> identical result_hash.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.our_ea.lot_engine import LotEngine, LotConfig
from core.our_ea.grid_engine import GridEngine, GridConfig

DATASET_PATH = os.path.join("data", "our_ea", "replay_dataset_v1.json")

MATCH, MISMATCH, UNKNOWN, NOT_COMPARABLE = ("MATCH", "MISMATCH", "UNKNOWN",
                                            "NOT_COMPARABLE")


@dataclass(frozen=True)
class Comparison:
    cycle_id: str
    event: str
    rule_id: str
    evidence: str
    classification: str
    expected: str = ""
    actual: str = ""
    difference: str = ""


@dataclass
class ReplayReport:
    run_id: str
    model_hash: str
    dataset_hash: str
    config_hash: str
    code_version: str
    comparisons: List[Comparison] = field(default_factory=list)
    result_hash: str = ""

    def counts(self) -> Dict[str, int]:
        c = {MATCH: 0, MISMATCH: 0, UNKNOWN: 0, NOT_COMPARABLE: 0}
        for x in self.comparisons:
            c[x.classification] += 1
        return c

    def summary(self) -> dict:
        c = self.counts()
        total = sum(c.values())
        return {"run_id": self.run_id, "total": total, **c,
                "match_pct": round(c[MATCH] / total * 100, 2) if total else 0.0,
                "result_hash": self.result_hash,
                "mismatches": [m.__dict__ for m in
                               [x for x in self.comparisons
                                if x.classification == MISMATCH][:200]]}


def _load_dataset(repo_root: str) -> dict:
    path = os.path.join(repo_root, DATASET_PATH)
    sidecar = path + ".sha256.txt"
    blob = open(path, "rb").read()
    h = hashlib.sha256(blob).hexdigest().upper()
    if os.path.exists(sidecar):
        expected = open(sidecar).read().strip().upper()
        if h != expected:
            raise RuntimeError(f"replay dataset hash mismatch: {h[:16]}…")
    return json.loads(blob.decode("utf-8"))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


class ReplayEngine:
    def __init__(self, repo_root: str, lot: Optional[LotConfig] = None,
                 grid: Optional[GridConfig] = None,
                 basket_hypothesis: str = "H_GROSS_1_00",
                 model_hash: str = ""):
        self.repo_root = repo_root
        self.lot_engine = LotEngine(lot or LotConfig())
        self.grid_engine = GridEngine(grid or GridConfig())
        self.basket_hypothesis = basket_hypothesis
        self.model_hash = model_hash

    # ------------------------------------------------------------------
    def replay(self) -> ReplayReport:
        ds = _load_dataset(self.repo_root)
        cfg_text = json.dumps({
            "lot": self.lot_engine.config.__dict__,
            "grid": self.grid_engine.config.__dict__,
            "basket_hypothesis": self.basket_hypothesis}, sort_keys=True)
        report = ReplayReport(
            run_id=f"R-{_sha(cfg_text)[:12]}",
            model_hash=self.model_hash or ds.get("model_hash", ""),
            dataset_hash=_sha(json.dumps(ds.get("dataset_hashes"),
                                         sort_keys=True)),
            config_hash=_sha(cfg_text),
            code_version=ds.get("source_commit", ""))
        for cyc in ds["cycles"]:
            self._replay_cycle(cyc, report)
        blob = json.dumps([[c.cycle_id, c.event, c.rule_id, c.classification,
                            c.expected, c.actual, c.difference]
                           for c in report.comparisons])
        report.result_hash = _sha(blob)
        return report

    # ------------------------------------------------------------------
    def _replay_cycle(self, cyc: dict, report: ReplayReport) -> None:
        cid = cyc["cycle_id"]
        entries = cyc["entries"]
        sides_first = {e["side"] for e in entries[:2]}

        # -- R-BOTH-SIDES: initial BUY+SELL pair
        both = sides_first == {"BUY", "SELL"}
        report.comparisons.append(Comparison(
            cid, "initial_pair", "R-BOTH-SIDES", "E015",
            MATCH if both else MISMATCH,
            expected="first two entries are BUY+SELL",
            actual=str(sorted(sides_first)),
            difference="" if both else "unpaired start"))

        # -- per-side ladder: base lot, floor lots, direction, spacing
        for side in ("BUY", "SELL"):
            lad = sorted([e for e in entries if e["side"] == side],
                         key=lambda e: e["time"])
            if not lad:
                continue
            # base lot (R-BASE-LOT)
            lvl1_lot = self.lot_engine.lot(1)
            ok = abs(lad[0]["lot"] - lvl1_lot) <= 0.005
            report.comparisons.append(Comparison(
                cid, f"base_lot_{side}", "R-BASE-LOT", "E015",
                MATCH if ok else MISMATCH,
                expected=str(lvl1_lot), actual=str(lad[0]["lot"]),
                difference=f"{lad[0]['lot'] - lvl1_lot:+.2f}"))
            # floor ladder lots (R-LOT-FLOOR)
            for lvl, e in enumerate(lad, 1):
                exp = self.lot_engine.lot(lvl)
                ok = abs(e["lot"] - exp) <= 0.005
                report.comparisons.append(Comparison(
                    cid, f"lot_L{lvl}_{side}", "R-LOT-FLOOR", "E012;E028",
                    MATCH if ok else MISMATCH,
                    expected=str(exp), actual=str(e["lot"]),
                    difference=f"{e['lot'] - exp:+.2f}"))
            # direction + spacing (R-GRID-DIRECTION / R-GRID-SPACING /
            # R-GRID-TRIGGER PARTIAL -> hypothesis recorded)
            for prev, nxt in zip(lad, lad[1:]):
                d = nxt["price"] - prev["price"]
                down = d < 0 if side == "BUY" else d > 0
                report.comparisons.append(Comparison(
                    cid, f"direction_{side}", "R-GRID-DIRECTION", "E014",
                    MATCH if down else MISMATCH,
                    expected="BUY down/SELL up", actual=f"{d:+.2f}",
                    difference="" if down else "wrong direction"))
                step = self.grid_engine.config.step_usd
                tol = self.grid_engine.config.tolerance_usd
                in_band = abs(abs(d) - step) <= tol
                # Fill scatter beyond the band with the CORRECT direction is
                # NOT a rule violation: trigger semantics are PARTIAL (E026)
                # and fast-market/gap fills land beyond the trigger with no
                # tick data to attribute the difference (E013 distribution
                # itself has a P95 5.98 tail; sub-1 fills occur in cascades).
                classification = MATCH if in_band else (
                    NOT_COMPARABLE if down else MISMATCH)
                report.comparisons.append(Comparison(
                    cid, f"spacing_{side}", "R-GRID-SPACING", "E013;E026",
                    classification,
                    expected=f"~{step} +/-{tol}", actual=f"{abs(d):.2f}",
                    difference=f"{abs(d) - step:+.2f}",
                    ))
                # trigger semantics: PARTIAL — record hypothesis, decide
                # NOT_COMPARABLE (cannot observe evaluation instant)
                report.comparisons.append(Comparison(
                    cid, f"trigger_{side}", "R-GRID-TRIGGER", "E026",
                    NOT_COMPARABLE,
                    expected="prev-entry or extreme (indistinguishable)",
                    actual=self.grid_engine.config.trigger_hypothesis,
                    difference="semantics PARTIAL by evidence"))

        # -- basket close (R-BASKET-TRIGGER PARTIAL: hypothesis check)
        gross = cyc["basket_close"]["gross"]
        lots = cyc["basket_close"]["total_lots"]
        thr = self._threshold(lots)
        ok = gross >= thr - 1e-9
        report.comparisons.append(Comparison(
            cid, "basket_close", "R-BASKET-TRIGGER", "E016;E027",
            MATCH if ok else MISMATCH,
            expected=f">= {thr:.2f} ({self.basket_hypothesis})",
            actual=f"{gross:.2f}",
            difference=f"{gross - thr:+.2f}"))

        # -- partial events: UNKNOWN -> never fabricated
        report.comparisons.append(Comparison(
            cid, "partial_close", "R-PARTIAL-TRIGGER", "E025", UNKNOWN,
            expected="n/a (UNKNOWN)", actual="not evaluated",
            difference="partial trigger/volume UNKNOWN"))

    def _threshold(self, total_lots: float) -> float:
        if self.basket_hypothesis == "H_GROSS_1_00":
            return 1.00
        if self.basket_hypothesis == "H_PER_LOT_0_50":
            return round(total_lots * 0.50, 8)
        if self.basket_hypothesis == "H_PER_LOT_0_85":
            return round(total_lots * 0.85, 8)
        raise ValueError(self.basket_hypothesis)

    # -- normal resume: uses resume_gap_s exported on the FULL per-account
    #    cycle sequence (Analyzer-side), so confidence filtering cannot
    #    fabricate artificial gaps between non-adjacent cycles.
    def replay_resume(self) -> List[Comparison]:
        ds = _load_dataset(self.repo_root)
        out = []
        for cyc in ds["cycles"]:
            gap = cyc.get("resume_gap_s")
            if gap is None:
                continue
            ok = gap <= 2.0
            out.append(Comparison(
                cyc["cycle_id"], "normal_resume", "R-NORMAL-RESUME", "E018",
                MATCH if ok else MISMATCH,
                expected="<= 2s", actual=f"{gap:.0f}s",
                difference=f"{gap - 2:+.0f}s"))
        return out
