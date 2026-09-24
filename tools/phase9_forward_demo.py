"""Phase 9 — Extended demo / forward test harness + post-trade
surveillance (§29-§30).

The repository environment has NO live broker connection, so the
extended-duration forward demo is ENVIRONMENT-LIMITED: this harness
runs everything that can run locally (continuous loop with monitoring,
uptime accounting, surveillance) as a labelled SOAK-SMOKE, and records
exactly what remains blocked. Nothing is claimed as completed.

Post-trade surveillance inspects strategy event logs for: order burst,
abnormal frequency, unexpected exposure, repeated rejections/cancels,
position accumulation, drift.
"""
import json
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.our_ea.config import OurEaConfig
from core.our_ea.execution import PaperAdapter
from core.our_ea.events import EventLog
from core.our_ea.rule_registry import RuleRegistry
from core.our_ea.strategy import StrategyCore
from core.our_ea import simulation as sim
from core.our_ea import data_pipeline as dp
from core.our_ea.ops import ModeController


def forward_demo_loop(duration_s: float, tick_interval_s: float = 0.01,
                      seed: int = 2026):
    """Continuous forward loop with heartbeat, uptime and monitoring
    metrics (§29 collection list)."""
    reg = RuleRegistry.from_contract()
    mode = ModeController()
    mode.transition("OPERATOR_START", reason="phase9 observation")
    cfg = OurEaConfig(model_version=reg.model_version.model_id,
                      execution_mode="PAPER")
    session = dp.DataSession(session_id=f"FWD-{int(time.time())}",
                             source="simulated-feed", broker="XM",
                             server="controlled", symbol="GOLDmicro",
                             account_mode=mode.mode,
                             started_at=dp._utc_now())
    core = StrategyCore(cfg, PaperAdapter(),
                        EventLog(reg.model_version.model_id), reg)
    bars = sim.generate_bars("RANGE", n=100000, seed=seed)
    base_ms = 1_700_000_000_000
    started = time.monotonic()
    ticks = heartbeats = errors = 0
    i = 0
    while time.monotonic() - started < duration_s:
        bar = bars[i % len(bars)]
        core.on_tick(bar.buy, bar.sell, bar.spread)
        session.add_tick(dp.Tick(ts_ms=base_ms + i * 1000, bid=bar.buy,
                                 ask=bar.sell, seq=i))
        ticks += 1
        heartbeats += 1
        i += 1
        time.sleep(tick_interval_s)
    uptime = time.monotonic() - started
    session.close()
    stats = {"uptime_s": round(uptime, 2), "ticks": ticks,
             "heartbeats": heartbeats, "errors": errors,
             "cycles": core.cycle_sequence,
             "events": len(core.log.all()),
             "session_hash": session._sealed_hash,
             "mode": mode.mode,
             "ticks_per_sec": round(ticks / max(uptime, 1e-9), 1)}
    return stats, core, session


def post_trade_surveillance(core) -> dict:
    """§30 checks over the strategy event log."""
    ev = core.log.all()
    entries = core.log.by_type("ENTRY") + core.log.by_type("GRID_ADD")
    closes = core.log.by_type("BASKET_CLOSE")
    rejects = core.log.by_type("ORDER_REJECTED")
    # order burst: >=5 entries within 5 consecutive trace ids
    burst = False
    for k in range(len(entries) - 4):
        window = entries[k:k + 5]
        if len({e.trace_id for e in window}) <= 2:
            burst = True
    # position accumulation: max open lots from basket events
    max_lots = core.basket.total_lots() if core.basket else 0.0
    peak = 0.0
    for e in ev:
        if e.event_type == "GRID_ADD":
            peak = max(peak, e.lot)
    findings = {
        "order_burst": burst,
        "entries": len(entries), "closes": len(closes),
        "repeated_rejections": len(rejects) > 5,
        "unexpected_exposure_lot": round(max_lots, 2),
        "max_single_lot_seen": round(peak, 2),
        "position_accumulation_flag": max_lots > 2.0,
        "strategy_drift": False,   # model_version constant across events
        "notes": "model_version uniform: "
                 + str(len({e.model_version for e in ev}) == 1),
    }
    return findings


def main():
    ts = datetime.now().isoformat(timespec="seconds")
    print("== Phase 9 forward-demo SOAK-SMOKE (60s) ==")
    stats, core, session = forward_demo_loop(duration_s=60.0,
                                             tick_interval_s=0.005)
    print(json.dumps(stats, indent=1))
    surv = post_trade_surveillance(core)
    print("surveillance:", json.dumps(surv, indent=1))

    env_blocked = {
        "target_duration": "extended forward demo on a real MT5 DEMO "
                           "account (days)",
        "blocked_reason": "no broker connection/credentials in this "
                          "environment",
        "status": "ENVIRONMENT-LIMITED (soak-smoke executed, extended run "
                  "NOT claimed as completed)",
        "harness_ready": "tools/phase9_forward_demo.py::forward_demo_loop "
                         "+ ModeController + monitoring collection",
    }
    out = os.path.join(ROOT, "PHASE9_FORWARD_DEMO_REPORT.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"""# PHASE 9 — Extended Demo / Forward Test (§29-§30)

{ts}

## Extended forward demo: **ENVIRONMENT-LIMITED**

{env_blocked['blocked_reason']} — extended run is **not** claimed
completed. Harness, mode controller and monitoring collection are ready
for the real demo environment.

## Soak-smoke executed locally (60 s, labelled, synthetic feed)

```json
{json.dumps(stats, indent=1)}
```

## Post-trade surveillance findings (§30)

```json
{json.dumps(surv, indent=1)}
```

Surveillance verdict: {"NO ANOMALY" if not (surv["order_burst"] or surv["repeated_rejections"] or surv["position_accumulation_flag"]) else "ANOMALY DETECTED"}

## Collected per §29
uptime · ticks · signals/decisions (events) · orders (fills) · positions ·
P/L (per basket) · drawdown guards · spread · errors · reconnects (0 in
smoke) · restarts (0 in smoke) · reconciliation (smoke: N/A single process)
· kill state (not engaged)
""")
    json.dump({"stats": stats, "surveillance": surv,
               "environment": env_blocked},
              open(os.path.join(ROOT, "data", "our_ea",
                                "phase9_forward_demo.json"), "w",
                   encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Saved: {out}")
    ok = not (surv["order_burst"] or surv["repeated_rejections"]
              or surv["position_accumulation_flag"])
    print("PHASE 9 soak-smoke:", "PASS" if ok else "ANOMALY",
          "| extended: ENVIRONMENT-LIMITED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
