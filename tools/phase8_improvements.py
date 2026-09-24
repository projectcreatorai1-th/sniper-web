"""Phase 8 (§25) — OUR_EA_POLICY improvement validation.

Change class: MAJOR (risk). Each improvement is validated with
before/after, dataset, result, and recorded with hash/version per the
change-management contract. V1.68 evidence is untouched.
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.our_ea.config import OurEaConfig
from core.our_ea.execution import PaperAdapter
from core.our_ea.events import EventLog
from core.our_ea.rule_registry import RuleRegistry
from core.our_ea.strategy import StrategyCore
from core.our_ea import simulation as sim
from core.our_ea.risk_guard import RiskGuard, RiskLimits


def scenario_run(volatility_guard: bool, scenario="FAST_MOVE"):
    reg = RuleRegistry.from_contract()
    risk = {"max_positions": 12, "max_grid_depth": 12, "max_total_lot": 2.0,
            "max_loss_usd": 50.0, "max_drawdown_pct": 30.0,
            "max_margin_usage_pct": 50.0, "max_spread_usd": 0.6,
            "max_slippage_usd": 0.5, "max_execution_time_s": 5.0,
            "allowed_symbols": ["GOLDmicro"]}
    if volatility_guard:
        risk["max_tick_volatility_usd"] = 8.0
    cfg = OurEaConfig(model_version=reg.model_version.model_id,
                      execution_mode="PAPER", risk=risk)
    core = StrategyCore(cfg, PaperAdapter(),
                        EventLog(reg.model_version.model_id), reg)
    bars = sim.generate_bars(scenario, n=200, seed=17)
    run = sim.run_scenario(core, bars, f"P8_{scenario}")
    return run, core


def main():
    ts = datetime.now().isoformat(timespec="seconds")
    changes = []

    # ---- improvement 1: consecutive-failure limiter --------------------
    g = RiskGuard(RiskLimits())
    g.record_order_failure(); g.record_order_failure()
    pre = g.check_entry(open_positions=0, side_levels=0,
                        total_lot_after=0.1, spread_usd=0.1)
    g.record_order_failure()               # 3rd -> blocked
    post = g.check_entry(open_positions=0, side_levels=0,
                         total_lot_after=0.1, spread_usd=0.1)
    g.record_order_success()               # reset
    reset = g.check_entry(open_positions=0, side_levels=0,
                          total_lot_after=0.1, spread_usd=0.1)
    changes.append({
        "change": "consecutive-failure limiter",
        "classification": "MAJOR (risk)",
        "before": f"2 failures -> allowed={pre.allowed}",
        "after": f"3 failures -> allowed={post.allowed}; success resets -> "
                 f"allowed={reset.allowed}",
        "reason": "broker rejection storms must not cascade (§16)",
        "dataset": "unit scenario", "result": "PASS" if (pre.allowed and
                 not post.allowed and reset.allowed) else "FAIL"})

    # ---- improvement 2: per-tick volatility guard ----------------------
    g2 = RiskGuard(RiskLimits(max_tick_volatility_usd=25.0))
    ok1 = g2.check_tick_volatility(4400.0).allowed
    jump = g2.check_tick_volatility(4450.0)             # +50 move
    calm = g2.check_tick_volatility(4451.0).allowed
    changes.append({
        "change": "per-tick volatility guard",
        "classification": "MAJOR (risk)",
        "before": "no per-tick move guard",
        "after": f"50usd tick move blocked={not jump.allowed}; "
                 f"next calm tick allowed={calm}",
        "reason": "fast-market cascades observed in evidence "
                  "(2026.09.16 21:00, spacing 0.19 fills)",
        "dataset": "observed fast-market analog", "result":
            "PASS" if (ok1 and not jump.allowed and calm) else "FAIL"})

    # ---- improvement 3: portfolio effect on HIGH_VOLATILITY scenario ---
    before_run, _ = scenario_run(volatility_guard=False)
    after_run, _ = scenario_run(volatility_guard=True)
    guard_effect = (before_run.risk_blocks, after_run.risk_blocks)
    changes.append({
        "change": "volatility guard engaged in strategy loop risk block "
                  "(via config)",
        "classification": "MAJOR (risk)",
        "before": f"FAST_MOVE risk_blocks={before_run.risk_blocks}",
        "after": f"FAST_MOVE risk_blocks={after_run.risk_blocks} "
                 f"(volatility guard active)",
        "reason": "extreme tick moves should block entries, not chase them",
        "dataset": "synthetic HIGH_VOLATILITY (labelled SYNTHETIC — never "
                   "evidence)",
        "result": "PASS" if after_run.risk_blocks > before_run.risk_blocks
                  else "FAIL"})

    blob = json.dumps(changes, sort_keys=True)
    doc = {
        "schema": "PHASE8_CHANGE_VALIDATION_V1",
        "generated": ts,
        "principle": "V1.68_EVIDENCE untouched; all changes OUR_EA_POLICY",
        "risk_model_version": "RK-1.1",
        "change_hash": hashlib.sha256(blob.encode()).hexdigest().upper(),
        "material_process": ["Replay", "Regression", "OOS", "Risk Validation",
                             "Demo", "Independent Validation",
                             "Deployment Review"],
        "changes": changes,
    }
    out = os.path.join(ROOT, "PHASE8_STRATEGY_IMPROVEMENT_REPORT.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"""# PHASE 8 — OUR EA Strategy Improvement (§25-§26)

{ts} · all changes classified **MAJOR (risk)** · risk model RK-1.0 -> **RK-1.1**
· change hash `{doc['change_hash'][:24]}…`

V1.68 evidence untouched (frozen model hash verified separately).
Dataset lineage: improvements motivated by OBSERVED evidence
(fast-market cascades E013/E014 exceptions), validated on SYNTHETIC
scenarios clearly labelled as non-evidence + unit counter-examples.

""")
        for c in changes:
            f.write(f"## {c['change']} — {c['result']}\n\n"
                    f"- classification: {c['classification']}\n"
                    f"- before: {c['before']}\n- after: {c['after']}\n"
                    f"- reason: {c['reason']}\n- dataset: {c['dataset']}\n\n")
        f.write("""## Material-change pipeline (required before deployment)

Replay -> Regression -> OOS -> Risk Validation -> Demo -> Independent
Validation -> Deployment Review — OOS portion executed in Phase 7 (no
strategy parameters were tuned on it; the guards are policy limits, not
fitted parameters).
""")
    ok = all(c["result"] == "PASS" for c in changes)
    print("changes:", [(c["change"], c["result"]) for c in changes])
    print("PHASE 8:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
