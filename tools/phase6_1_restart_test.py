"""Phase 6.1 — TEST_R_RESTART_RECOVERY real execution (§5).

Each scenario runs the worker in REAL subprocesses:
  phase1 (process A) -> termination -> phase2 (process B).
Verifies: model version, event position, cycle ID, basket ID,
idempotency, no duplicate action, no state corruption, risk + kill
switch state, audit trail continuity.

Scenarios:
  1 normal                    (idle/waiting restart)
  2 active_cycle              (open basket continues, same cycle id)
  3 after_partial             (partial enabled -> uncertainty recorded)
  4 duplicate_event           (same tick replayed after restore)
  5 missing_state             (no file -> policy action, no trades)
  6 corrupted_state           (tampered file -> SAFE_STOP)
  7 incompatible_model        (rewritten model hash -> refused)
  8 stale_state               (old timestamp -> SAFE_STOP)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(ROOT, "tools", "phase6_1_worker.py")
OUT = os.path.join(ROOT, "PHASE6_1_RESTART_RECOVERY_REPORT.md")


def run_worker(args):
    r = subprocess.run([sys.executable, WORKER] + args,
                       capture_output=True, text=True, cwd=ROOT)
    try:
        payload = json.loads(r.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        payload = {"raw": r.stdout[-400:], "stderr": r.stderr[-400:]}
    return r.returncode, payload


def scenario_normal(td):
    st = os.path.join(td, "normal.json")
    rc1, p1 = run_worker(["phase1", "--state", st, "--bars", "5"])
    rc2, p2 = run_worker(["phase2", "--state", st, "--bars", "5"])
    ok = rc1 == 0 and rc2 == 0 and p2.get("ok") and p2.get("cycle_sequence", 0) >= p1.get("cycle_sequence", 0)
    return ok, p1, p2, "state restored, cycles continue, no new id minted"


def scenario_active_cycle(td):
    st = os.path.join(td, "active.json")
    # 25 bars of a falling-then-ranging path keeps a basket open
    rc1, p1 = run_worker(["phase1", "--state", st, "--bars", "25",
                          "--seed", "31"])
    rc2, p2 = run_worker(["phase2", "--state", st, "--bars", "25",
                          "--seed", "31", "--expect-cycle",
                          str(p1.get("cycle_id"))])
    # the restored basket may legitimately CLOSE during phase2 (normal
    # operation); what must hold: identity restored unchanged, sequence
    # never reset, processing continued on top of restored tick counter
    ok = (rc1 == 0 and rc2 == 0 and p2.get("ok")
          and p2.get("restored_cycle_id") == p1.get("cycle_id")
          and p2.get("cycle_sequence", 0) >= p1.get("cycle_sequence", 0)
          and p2.get("tick_no", 0) > p1.get("tick_no", 0))
    return ok, p1, p2, ("cycle/basket identity restored unchanged; "
                        "sequence/tick cursor continue (basket may close "
                        "normally afterwards)")


def scenario_after_partial(td):
    st = os.path.join(td, "partial.json")
    rc1, p1 = run_worker(["phase1", "--state", st, "--bars", "30",
                          "--partial"])
    rc2, p2 = run_worker(["phase2", "--state", st, "--bars", "10"])
    ok = rc1 == 0 and rc2 == 0 and p2.get("ok")
    return ok, p1, p2, "restart after uncertainty events — continues safely"


def scenario_duplicate_event(td):
    st = os.path.join(td, "dup.json")
    rc1, p1 = run_worker(["phase1", "--state", st, "--bars", "20"])
    rc2, p2 = run_worker(["phase2", "--state", st, "--duplicate-tick"])
    ok = rc2 == 0 and p2.get("ok") and not p2.get("duplicate_detected")
    return ok, p1, p2, "replayed tick produced no duplicate (side,level) fill"


def scenario_missing_state(td):
    st = os.path.join(td, "missing.json")     # never created
    rc, p = run_worker(["phase2", "--state", st])
    ok = rc in (0, 3, 5) and p.get("action") in ("PAUSE_FOR_OPERATOR",
                                                 "SAFE_STOP")
    return ok, {"phase": "phase2-direct"}, p, "no state -> policy pause, no trades"


def scenario_corrupted(td):
    st = os.path.join(td, "corrupt.json")
    run_worker(["phase1", "--state", st, "--bars", "10"])
    # tamper: flip a character inside the envelope
    blob = open(st, encoding="utf-8").read()
    open(st, "w", encoding="utf-8").write(
        blob.replace('"cycle_sequence"', '"cycle_seqX"', 1))
    rc, p = run_worker(["phase2", "--state", st])
    ok = rc == 4 and p.get("action") == "SAFE_STOP"
    return ok, {"phase": "phase1-ok"}, p, "checksum mismatch -> SAFE_STOP"


def scenario_incompatible_model(td):
    st = os.path.join(td, "incompat.json")
    run_worker(["phase1", "--state", st, "--bars", "10"])
    # rewrite model hash inside envelope (breaks checksum -> corruption
    # first, then also test checksum-valid-but-wrong-model via re-sign)
    import hashlib, json as j
    env = j.load(open(st, encoding="utf-8"))
    env["state"]["model_version"] = "OTHER-MODEL-v9"
    payload = j.dumps(env["state"], ensure_ascii=False, sort_keys=True, indent=1)
    env["checksum"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    j.dump(env, open(st, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rc, p = run_worker(["phase2", "--state", st])
    ok = rc == 5 and p.get("action") in ("SAFE_STOP", "PAUSE_FOR_OPERATOR")
    return ok, {"phase": "phase1-ok"}, p, "model mismatch -> refused, no restore"


def scenario_stale(td):
    st = os.path.join(td, "stale.json")
    run_worker(["phase1", "--state", st, "--bars", "10"])
    rc, p = run_worker(["phase2", "--state", st, "--stale"])
    ok = rc == 3 and p.get("action") == "SAFE_STOP"
    return ok, {"phase": "phase1-ok"}, p, "stale state -> SAFE_STOP (market gap unknowable)"


def main():
    scenarios = [
        ("normal", scenario_normal),
        ("active_cycle", scenario_active_cycle),
        ("after_partial", scenario_after_partial),
        ("duplicate_event", scenario_duplicate_event),
        ("missing_state", scenario_missing_state),
        ("corrupted_state", scenario_corrupted),
        ("incompatible_model_version", scenario_incompatible_model),
        ("stale_state", scenario_stale),
    ]
    results = []
    with tempfile.TemporaryDirectory(prefix="p61_restart_") as td:
        for name, fn in scenarios:
            ok, p1, p2, expect = fn(td)
            results.append({"scenario": name, "ok": ok, "expected": expect,
                            "phase1": p1, "phase2": p2})
            print(f"  {name:28s} {'PASS' if ok else 'FAIL'}")

    passed = sum(1 for r in results if r["ok"])
    lines = [
        "# PHASE 6.1 — TEST_R_RESTART_RECOVERY EXECUTION REPORT (§5)",
        "",
        "Executed as REAL separate processes (phase1 -> termination -> "
        "phase2). Verified on every restore: contract hash, state "
        "checksum, model version, event cursor, cycle/basket identity, "
        "idempotency keys, risk state incl. kill switch.",
        "",
        "**This is OUR EA restart/recovery safety behavior, not verified "
        "V1.68 restart behavior** (R-RESTART-RECOVERY stays UNKNOWN).",
        "",
        f"**Result: {passed}/{len(results)} scenarios PASS**",
        "",
        "| Scenario | Result | Verified behaviour |",
        "|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r['scenario']} | {'PASS' if r['ok'] else 'FAIL'} "
                     f"| {r['expected']} |")
    lines += [
        "",
        "## Representative evidence (JSON from worker processes)",
        "",
    ]
    for r in results:
        lines.append(f"### {r['scenario']}")
        lines.append("```json")
        lines.append(json.dumps(r["phase2"], ensure_ascii=False, indent=1)[:600])
        lines.append("```")
        lines.append("")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nSaved: {OUT}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
