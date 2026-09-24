"""Restart-recovery worker — runs in a REAL separate process.

Usage (one phase per process invocation):
    python tools/phase6_1_worker.py phase1 --state PATH [--bars N] [--seed S]
        [--partial] [--dump]
    python tools/phase6_1_worker.py phase2 --state PATH [--bars N] [--seed S]
        [--expect-cycle ID] [--duplicate-tick] [--stale] [--no-state-ok]

phase1: build core, run ticks, persist, exit (simulates termination).
phase2: NEW process — verify contract hash, load state (checksum), restore,
        continue processing, report JSON on stdout.

Exit codes: 0 ok, 3 SAFE_STOP (by policy), 4 corruption, 5 model mismatch.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.our_ea.config import OurEaConfig
from core.our_ea.execution import PaperAdapter
from core.our_ea.events import EventLog
from core.our_ea.rule_registry import RuleRegistry
from core.our_ea.strategy import StrategyCore
from core.our_ea.persistence import (StateStore, StateCorruptionError,
                                     PersistenceError, RecoveryPolicy)
from core.our_ea import simulation as sim
from datetime import datetime


def build(state_path, partial=False):
    reg = RuleRegistry.from_contract()          # verifies frozen hash
    over = {"partial": {"enabled": True}} if partial else {}
    cfg = OurEaConfig(model_version=reg.model_version.model_id,
                      execution_mode="PAPER", **over)
    store = StateStore(state_path)
    log = EventLog(reg.model_version.model_id)
    return cfg, reg, store, log


def run_ticks(core, n, seed, start_px=4400.0):
    bars = sim.generate_bars("RANGE", n=n, seed=seed, start=start_px)
    run = sim.run_scenario(core, bars, "RESTART_PHASE")
    return run


def phase1(args):
    cfg, reg, store, log = build(args.state, partial=args.partial)
    core = StrategyCore(cfg, PaperAdapter(), log, reg, state_store=store)
    run = run_ticks(core, args.bars, args.seed)
    core._persist()
    b = core.basket.summary() if core.basket else {}
    print(json.dumps({
        "phase": "phase1", "ok": True,
        "state": core.sm.state, "cycle_id": b.get("cycle_id"),
        "basket_id": b.get("basket_id"), "open_positions": b.get("open_positions"),
        "cycle_sequence": core.cycle_sequence, "tick_no": core.tick_no,
        "events": len(core.log.all()), "kill_switch": core.risk.state.kill_switch}))


def phase2(args):
    cfg, reg, store, log = build(args.state)
    policy = RecoveryPolicy()
    result = {"phase": "phase2"}

    # stale-state policy (before adoption)
    if args.stale:
        decision = policy.on_stale_state(float(10 ** 9))
        result.update({"ok": False, "action": decision["action"],
                       "reason": decision["reason"], "exit": 3})
        print(json.dumps(result))
        sys.exit(3)

    try:
        persisted = store.load(expected_model=(
            reg.model_version.model_id, reg.model_version.model_hash))
    except StateCorruptionError as ex:
        decision = policy.on_state_corrupt()
        result.update({"ok": False, "action": decision["action"],
                       "reason": f"{ex}", "exit": 4})
        print(json.dumps(result))
        sys.exit(4)
    except PersistenceError as ex:
        if "no persisted state" in str(ex):
            decision = policy.on_missing_state_with_positions()
        else:
            decision = policy.on_state_corrupt()
        result.update({"ok": False, "action": decision["action"],
                       "reason": str(ex), "exit": 5})
        print(json.dumps(result))
        sys.exit(5)

    # restore into a live core (checksum + model version already verified)
    core = StrategyCore.restore(cfg, PaperAdapter(), log, reg, store,
                                persisted)
    result["restored_state"] = persisted.state
    result["restored_cycle_id"] = persisted.cycle_id
    result["idempotency_keys"] = len(persisted.idem_keys)

    if args.expect_cycle and persisted.cycle_id != args.expect_cycle:
        result.update({"ok": False, "action": "MISMATCH",
                       "reason": f"cycle id changed: {persisted.cycle_id}",
                       "exit": 6})
        print(json.dumps(result))
        sys.exit(6)

    if args.duplicate_tick:
        # replay the SAME market tick twice after restore: must not
        # double-execute (level-keyed grid gating + idempotency)
        before = len(core.log.all())
        core.on_tick(4400.0, 4399.5, 0.5)
        core.on_tick(4400.0, 4399.5, 0.5)
        entries = core.log.by_type("ENTRY") + core.log.by_type("GRID_ADD")
        keys = [(e.side, e.level) for e in entries]
        dup = len(keys) != len(set(keys))
        result.update({"ok": not dup, "duplicate_detected": dup,
                       "exit": 0 if not dup else 7})
        print(json.dumps(result))
        sys.exit(0 if not dup else 7)

    run = run_ticks(core, args.bars, args.seed + 1)
    core._persist()
    b = core.basket.summary() if core.basket else {}
    result.update({
        "ok": True, "state": core.sm.state,
        "cycle_id": b.get("cycle_id"), "basket_id": b.get("basket_id"),
        "cycle_sequence": core.cycle_sequence,
        "tick_no": core.tick_no,
        "kill_switch": core.risk.state.kill_switch,
        "events": len(core.log.all()), "exit": 0})
    print(json.dumps(result))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["phase1", "phase2"])
    ap.add_argument("--state", required=True)
    ap.add_argument("--bars", type=int, default=25)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--partial", action="store_true")
    ap.add_argument("--expect-cycle")
    ap.add_argument("--duplicate-tick", action="store_true")
    ap.add_argument("--stale", action="store_true")
    args = ap.parse_args()
    if args.phase == "phase1":
        phase1(args)
    else:
        phase2(args)


if __name__ == "__main__":
    main()
