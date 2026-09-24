"""Phase 6 replay dataset export (§29 + boundary RULE 8).

Uses the Analyzer forensic stack READ-ONLY to convert the original 4
account xlsx files into ONE immutable replay dataset for OUR EA:

    data/our_ea/replay_dataset_v1.json   (+ .sha256.txt)

The export manifest records artifact_hash, source_project, source
commit, model_version, created_at. OUR EA's replay engine consumes ONLY
this file — it never imports Analyzer runtime and never touches the
original datasets.
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Analyzer runtime used HERE (tool side, read-only) — allowed for export
from core.forensics import load_report, reconstruct_cycles

DESKTOP = r"C:\Users\BANK\Desktop"
ACCOUNTS = ["335504856", "391629843", "411173797", "440192945"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "our_ea", "replay_dataset_v1.json")


def main():
    ts = datetime.now().isoformat(timespec="seconds")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    cycles_out = []
    dataset_hashes = {}
    for acct in ACCOUNTS:
        rep = load_report(os.path.join(DESKTOP, f"ReportHistory-{acct}.xlsx"))
        dataset_hashes[acct] = rep.sha256
        all_cycles = reconstruct_cycles(rep)
        FMT = "%Y.%m.%d %H:%M:%S"
        resume_gap = {}
        for a, b in zip(all_cycles, all_cycles[1:]):
            if not a.end_time:
                continue
            resume_gap[b.cycle_id] = round(
                (datetime.strptime(b.start_time, FMT) -
                 datetime.strptime(a.end_time, FMT)).total_seconds(), 1)
        for cyc in all_cycles:
            if cyc.confidence != "HIGH":
                continue                      # ambiguous cycles are not
                                              # hard evidence (§5.2)
            entries = [{"side": m["side"], "lot": m["volume"],
                        "price": m["open_price"], "time": m["open_time"],
                        "level_hint": 0,
                        "close_time": m["close_time"],
                        "close_price": m["close_price"],
                        "profit": m["profit"]}
                       for m in cyc.members]
            # per-side ladder levels for comparison
            for e in entries:
                pass
            side_seq = {"BUY": [], "SELL": []}
            for m in sorted(cyc.members, key=lambda x: (x["open_time"], x["ticket"])):
                side_seq[m["side"]].append(m["volume"])
            for e in entries:
                e["level_hint"] = 0
            cycles_out.append({
                "cycle_id": cyc.cycle_id,
                "account_id": acct,
                "symbol": "GOLDmicro",
                "confidence": cyc.confidence,
                "flags": list(cyc.flags),
                "start_time": cyc.start_time,
                "end_time": cyc.end_time,
                "entries": entries,
                "side_lots": side_seq,
                "basket_close": cyc.basket_close,
                "resume_gap_s": resume_gap.get(cyc.cycle_id),
            })

    doc = {
        "schema": "OUR_EA_REPLAY_DATASET_V1",
        "source_type": "OBSERVED",
        "created_at": ts,
        "model_version": "V1.68-EVIDENCE-MODEL-v1.0",
        "model_hash": open(os.path.join(
            ROOT, "data", "evidence_model",
            "V1.68-EVIDENCE-MODEL-v1.0.sha256.txt")).read().strip(),
        "source_project": "SNIPER-CashFlow-Analyzer (Analyzer, read-only export)",
        "source_commit": commit,
        "dataset_hashes": dataset_hashes,
        "notes": "HIGH-confidence cycles only; LOW-confidence excluded "
                 "from hard-evidence replay; synthetic data never mixed in.",
        "cycles": cycles_out,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    h = hashlib.sha256(open(OUT, "rb").read()).hexdigest().upper()
    with open(OUT + ".sha256.txt", "w") as f:
        f.write(h + "\n")
    print(f"exported {len(cycles_out)} HIGH-confidence cycles -> {OUT}")
    print(f"artifact hash {h}")
    per = {}
    for c in cycles_out:
        per[c["account_id"]] = per.get(c["account_id"], 0) + 1
    print("per account:", per)


if __name__ == "__main__":
    main()
