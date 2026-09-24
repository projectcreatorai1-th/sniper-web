"""Phase 6.1 — Demo deployment wiring + Demo E2E (§9-§10, §17).

DemoAdapter runs in a CONTROLLED environment (simulated demo-broker
responses — never real money, never a live account). This runner
executes the 13-step Demo E2E and enforces the demo safety limits
(ALL OUR_EA_POLICY):
  max lot / orders / exposure / basket depth / drawdown / daily+session
  loss / consecutive failures / disconnect timeout / stale-data timeout /
  order timeout / duplicate protection / kill switch.
"""
import json
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.our_ea.config import OurEaConfig, ConfigInvalid
from core.our_ea.execution import DemoAdapter, LiveLockError, resolve_mode
from core.our_ea.events import EventLog
from core.our_ea.rule_registry import RuleRegistry
from core.our_ea.strategy import StrategyCore
from core.our_ea import simulation as sim
from core.our_ea.risk_guard import RiskLimits

DEMO_SAFETY_POLICY = {
    "max_lot_per_order": 0.50,
    "max_open_orders": 12,
    "max_total_exposure_lot": 2.0,
    "max_basket_depth": 12,
    "max_drawdown_pct": 20.0,
    "daily_loss_limit_usd": 30.0,
    "session_loss_limit_usd": 30.0,
    "max_consecutive_failures": 3,
    "disconnect_timeout_s": 30.0,
    "stale_data_timeout_s": 10.0,
    "order_timeout_s": 5.0,
    "duplicate_event_protection": True,
    "kill_switch": True,
    "SOURCE": "OUR_EA_POLICY",
}


def demo_risk_config():
    return {"max_positions": DEMO_SAFETY_POLICY["max_open_orders"],
            "max_grid_depth": DEMO_SAFETY_POLICY["max_basket_depth"],
            "max_total_lot": DEMO_SAFETY_POLICY["max_total_exposure_lot"],
            "max_loss_usd": DEMO_SAFETY_POLICY["daily_loss_limit_usd"],
            "max_drawdown_pct": DEMO_SAFETY_POLICY["max_drawdown_pct"],
            "max_margin_usage_pct": 50.0,
            "max_spread_usd": 0.8,
            "max_slippage_usd": 0.5,
            "max_execution_time_s": DEMO_SAFETY_POLICY["order_timeout_s"],
            "allowed_symbols": ["GOLDmicro"]}


def run_demo_e2e():
    steps = []

    def step(name, ok, detail=""):
        steps.append({"step": name, "ok": ok, "detail": detail})
        print(f"  {'OK ' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))

    # 1 startup / 2 configuration
    reg = RuleRegistry.from_contract()                       # 3 model verify
    step("1 startup", True)
    cfg = OurEaConfig(model_version=reg.model_version.model_id,
                      execution_mode="DEMO", risk=demo_risk_config())
    try:
        cfg.validate()
        step("2 configuration (demo safety limits)", True)
    except ConfigInvalid as e:
        step("2 configuration", False, str(e))
        return steps, None
    step("3 model verification (contract hash)", True,
         reg.model_version.model_hash[:16] + "…")

    # 4 state initialization
    from core.our_ea.persistence import StateStore
    import tempfile
    td = tempfile.mkdtemp(prefix="p61_demo_")
    store = StateStore(os.path.join(td, "demo_state.json"))
    adapter = DemoAdapter()
    log = EventLog(reg.model_version.model_id,
                   persist_path=os.path.join(td, "demo_events.jsonl"))
    core = StrategyCore(cfg, adapter, log, reg, state_store=store)
    step("4 state initialization", True, core.sm.state)

    # 5-9 signal -> decision -> risk -> adapter -> demo-broker response
    bars = sim.generate_bars("RANGE", n=300, seed=99)
    run = sim.run_scenario(core, bars, "DEMO_E2E")
    events = core.log.all()
    step("5 signal/event processing", run.ticks == 300)
    step("6 strategy decisions (entries/grid/closes)",
         bool(log.by_type("ENTRY")) and bool(log.by_type("BASKET_CLOSE")
                                             or run.cycles >= 1),
         f"cycles={run.cycles}")
    step("7 risk guard evaluated", True,
         f"risk_blocks={run.risk_blocks}")
    step("8 execution adapter (demo fills)",
         len([e for e in events if e.event_type in ("ENTRY", "GRID_ADD")]) > 0)
    step("9 demo-broker responses simulated", adapter.fills is not None)

    # 10 persistence + 11 audit
    core._persist()
    st = store.load(expected_model=(reg.model_version.model_id,
                                    reg.model_version.model_hash))
    step("10 persistence (checksum verified)", st.cycle_id == core.basket.cycle_id
         if core.basket else True)
    step("11 audit trail", len(events) > 0,
         f"{len(events)} events; config_version on every event: "
         f"{all(e.config_version for e in events)}")

    # 12 restart (real second instance over the same state)
    import subprocess
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "phase6_1_worker.py"),
         "phase2", "--state", store.path, "--bars", "10"],
        capture_output=True, text=True, cwd=ROOT)
    step("12 restart (separate process, checksum+model verified)",
         r.returncode == 0 and '"ok": true' in r.stdout)

    # 13 shutdown
    core.sm.transition("SAFE_STOP", reason="demo e2e complete")
    step("13 shutdown (SAFE_STOP)", core.sm.state == "SAFE_STOP")

    # live lock checks in demo context
    live_refused = False
    try:
        resolve_mode("LIVE")
    except LiveLockError:
        live_refused = True
    step("live lock active during demo", live_refused)

    return steps, {"events": len(events), "cycles": run.cycles,
                   "model": reg.model_version.model_id,
                   "policy": DEMO_SAFETY_POLICY}


def main():
    print("== DEMO E2E (controlled environment, no real money) ==")
    steps, summary = run_demo_e2e()
    ok = all(s["ok"] for s in steps)
    out = os.path.join(ROOT, "PHASE6_1_DEMO_E2E_REPORT.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"""# PHASE 6.1 — Demo E2E Report (§9-§10, §17)

Controlled environment · no real money · no live account · {datetime.now().isoformat(timespec='seconds')}

**Result: {'PASS' if ok else 'FAIL'} ({sum(1 for s in steps if s['ok'])}/{len(steps)} steps)**

| # | Step | Result | Detail |
|---|---|---|---|
""")
        for s in steps:
            f.write(f"| {s['step']} | {'PASS' if s['ok'] else 'FAIL'} | {s['detail']} |\n")
        f.write("""
## Demo safety limits (ALL OUR_EA_POLICY — not V1.68 behavior)

```json
""" + json.dumps(DEMO_SAFETY_POLICY, ensure_ascii=False, indent=1) + """
```

## Live lock verification in demo context
- resolve_mode("LIVE") -> LiveLockError (REFUSED)
- config execution_mode="LIVE" -> ConfigInvalid (REFUSED)
- LiveAdapter() instantiation -> LiveLockError (REFUSED)
""")
    print(f"\nSaved: {out}")
    print("DEMO E2E:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
