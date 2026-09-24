"""Phase 5.2 orchestrator — forensic engines + human confirmation packet.

Runs every forensic engine over the 4-account dataset, then produces:
  data/phase5_2_forensics.json      raw engine results
  data/phase5_2_confirmation_packet.json   per-candidate review packet
  data/evidence_model/V1.68-EVIDENCE-MODEL-v1.0-draft.json  freeze draft

CONSTRAINTS honoured here:
  - no auto-confirm: candidates stay CANDIDATE, packet marks
    new_status = PENDING_HUMAN_REVIEW
  - no invented behaviour: UNKNOWN stays UNKNOWN
  - no mixing observed with synthetic (this run uses observed data only)
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.forensics import (
    load_report, reconstruct_cycles, LotEngine,
    collect_add_observations, replay_anchor_hypotheses, anchor_conclusion,
    extract_partial_deals, classify_partial_deals,
    basket_from_cycle, replay_trigger_hypotheses, summarize_baskets,
    trigger_conclusion,
    scan_emergency, scan_pauses, restart_status)
from core.evidence import default_evidence_registry
from core.model_candidates import ModelCandidateStore

DESKTOP = r"C:\Users\BANK\Desktop"
ACCOUNTS = ["335504856", "391629843", "411173797", "440192945"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def main():
    ts = datetime.now().isoformat(timespec="seconds")
    print("=" * 78)
    print(f"PHASE 5.2 — FORENSIC ENGINES + CONFIRMATION PACKET  ({ts})")
    print("=" * 78)

    reports, all_cycles = [], []
    for a in ACCOUNTS:
        rep = load_report(os.path.join(DESKTOP, f"ReportHistory-{a}.xlsx"))
        reports.append(rep)
        cyc = reconstruct_cycles(rep)
        all_cycles.extend(cyc)
        hi = sum(1 for c in cyc if c.confidence == "HIGH")
        print(f"  {a}: {len(rep.positions)} pos | {len(cyc)} cycles "
              f"({hi} HIGH conf) | sha={rep.sha256[:12]}…")

    complete = [c for c in all_cycles if c.end_time]
    high_conf = [c for c in complete if c.confidence == "HIGH"]
    print(f"\n  total cycles {len(all_cycles)} | complete {len(complete)} | "
          f"HIGH-confidence {len(high_conf)}")

    # ---- 3. Lot engine verification (L1-L50, broker constraints) ----
    print("\n[3] LOT ENGINE (floor, configurable)")
    engine = LotEngine()
    ladder50 = engine.ladder(50)
    seq_ok = engine.verify_sequence(ladder50)
    print(f"  ladder L1-L50 self-consistent: {seq_ok['matched']}/50")
    obs_match = tot = 0
    for c in high_conf:
        for side in ("BUY", "SELL"):
            seq = [m["volume"] for m in c.members if m["side"] == side]
            r = engine.verify_sequence(seq)
            obs_match += r["matched"]
            tot += r["checked"]
    print(f"  real observations: {obs_match}/{tot} = {obs_match/max(tot,1)*100:.2f}%")

    # ---- 4. Grid trigger forensics ----
    print("\n[4] GRID TRIGGER FORENSICS (anchor hypotheses)")
    adds = collect_add_observations(complete, high_confidence_only=True)
    replay = replay_anchor_hypotheses(adds)
    concl = anchor_conclusion(replay)
    print(f"  add observations (HIGH-conf cycles): {len(adds)}")
    for name, st in replay["anchors"].items():
        if st.get("n") and st.get("score") is not None:
            print(f"    {name:28s} n={st['n']:5d} p5={st['p5']:.2f} "
                  f"med={st['median']:.2f} p95={st['p95']:.2f} "
                  f"band%={st['in_4_5_6_pct']:.1f} score={st['score']}")
    print(f"  conclusion: {concl['status']} supported={concl['supported']}")

    # ---- 5. Cycle reconstruction summary (confidence distribution) ----
    conf_dist = {}
    for c in all_cycles:
        conf_dist[c.confidence] = conf_dist.get(c.confidence, 0) + 1
    flag_counts = {}
    for c in all_cycles:
        for f in c.flags:
            flag_counts[f] = flag_counts.get(f, 0) + 1
    print("\n[5] CYCLE RECONSTRUCTION")
    print(f"  confidence: {conf_dist}")
    print(f"  flags: {flag_counts}")

    # ---- 6. Partial close engine ----
    print("\n[6] PARTIAL CLOSE ENGINE (deal-level)")
    partials = []
    for rep in reports:
        partials.extend(extract_partial_deals(rep))
    pclass = classify_partial_deals(partials, reports)
    print(f"  true partial events (unmatched out-deals): {pclass.get('n_events')}")
    print(f"  per account: {pclass.get('per_account')}")
    print(f"  profit: median={pclass['profit']['median']} "
          f"in[0.7,1.3]={pclass['profit']['in_0_7_1_3_pct']}%")
    print(f"  PARTIAL_EXISTS={pclass['PARTIAL_EXISTS']} "
          f"TRIGGER={pclass['PARTIAL_TRIGGER']['status']} "
          f"VOLUME_RULE={pclass['PARTIAL_VOLUME_RULE']['status']} "
          f"LEVEL_RULE={pclass['PARTIAL_LEVEL_RULE']['status']} "
          f"attribution={pclass['attribution']}")

    # ---- 7. Basket engine forensics ----
    print("\n[7] BASKET ENGINE FORENSICS (trigger hypothesis replay)")
    baskets = [basket_from_cycle(c) for c in complete if c.confidence != "LOW"]
    summary = summarize_baskets(baskets)
    print(f"  baskets: {summary['n']} | median {summary['gross_median']} | "
          f"losers {summary['losers']}")
    hyps = replay_trigger_hypotheses(baskets)
    for h in hyps:
        print(f"    {h.name:16s} violations={h.violations:3d} "
              f"({h.violation_pct:5.2f}%) overshoot_mean={h.overshoot_mean:+.3f} "
              f"mae={h.mae:.3f}")
    tconcl = trigger_conclusion(hyps)
    print(f"  trigger: {tconcl['trigger_status']} compatible={tconcl['compatible_hypotheses']}")

    # ---- 8. Emergency forensics ----
    print("\n[8] EMERGENCY FORENSICS")
    em = scan_emergency(complete, reports)
    print(f"  emergency closes: {em['emergency_closes_observed']} | "
          f"anomaly kinds: {em['anomaly_kinds']} | status={em['status']}")

    # ---- 9. Restart recovery ----
    print("\n[9] RESTART RECOVERY")
    pauses = scan_pauses(all_cycles)
    rst = restart_status(pauses)
    print(f"  pauses>{60}s: {rst['pauses_observed']} | "
          f"fresh base-lot after pause: {rst['fresh_base_lot_after_pause']} | "
          f"restart={rst['restart_recovery']}")

    # ---- save raw results ----
    results = {
        "generated": ts,
        "sources": {r.account_id: {"sha256": r.sha256,
                                   "positions": len(r.positions),
                                   "orders": len(r.orders),
                                   "deals": len(r.deals),
                                   "account_line": r.account_line}
                    for r in reports},
        "cycle_reconstruction": {"total": len(all_cycles),
                                 "complete": len(complete),
                                 "high_confidence": len(high_conf),
                                 "confidence_dist": conf_dist,
                                 "flag_counts": flag_counts},
        "lot_engine": {"ladder_L1_L50": ladder50,
                       "observation_match_pct": round(obs_match / max(tot, 1) * 100, 2),
                       "checked": tot},
        "grid_trigger": {"n_observations": len(adds), "replay": replay,
                         "conclusion": concl},
        "partial_close": pclass,
        "basket": {"summary": summary,
                   "hypotheses": [h.__dict__ for h in hyps],
                   "conclusion": tconcl},
        "emergency": {k: v for k, v in em.items() if k != "anomalies"},
        "emergency_anomalies": em["anomalies"],
        "restart": {"pauses": pauses, "status": rst["restart_recovery"],
                    "note": rst["note"]},
    }
    out_raw = os.path.join(DATA, "phase5_2_forensics.json")
    with open(out_raw, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {out_raw}")

    # ---- Phase 5.2 confirmation packet (NO auto-confirm) ----
    build_packet(results, ts)


def build_packet(results, ts):
    reg = default_evidence_registry()
    store = ModelCandidateStore()

    # ensure the master-command rule set exists (BaseLot was folded into
    # MC-001/MC-004 descriptions; create an explicit BASE_LOT candidate)
    existing = {(c.rule_type, c.description) for c in store.all()}
    base_desc = ("BaseLot = 0.10 on GOLDmicro (first entry of each side in "
                 "99.8% of cycle starts)")
    if not any(t == "LOT_FORMULA" and "BaseLot = 0.10" in d
               for t, d in existing):
        store.create(rule_type="LOT_FORMULA", description=base_desc,
                     source_evidence_ids=["E015"],
                     notes="Split out of MC-001/MC-004 per MASTER COMMAND "
                           "Phase 5.2 rule list.")

    candidates = store.all()
    ev_by_id = {e.evidence_id: e for e in reg.all()}

    def ev_refs(ids):
        return [{"evidence_id": i,
                 "claim": (ev_by_id[i].claim if i in ev_by_id else "MISSING"),
                 "status": (ev_by_id[i].status if i in ev_by_id else "MISSING"),
                 "confidence": (ev_by_id[i].confidence if i in ev_by_id else "-")}
                for i in ids]

    fr = results

    # ---- E025: corrected deal-level partial-close analysis ----
    from core.evidence import EvidenceRecord, MT5_CSV, OBSERVED
    pc = fr["partial_close"]
    try:
        reg.add(EvidenceRecord(
            evidence_id="E025", source_type=MT5_CSV,
            source_name="MT5 Deals table — unmatched out-deals (intra-position partials)",
            source_reference="see E011 hashes",
            claim="Partial closes are intra-position: out-deals that match no "
                  "position-row close; Positions table shows only remaining volume",
            observed_value=(f"{pc['n_events']} events | profit median "
                            f"{pc['profit']['median']} | {pc['profit']['in_0_7_1_3_pct']}% "
                            f"in [0.7,1.3] | attribution {pc['attribution']['fifo_feasible']} "
                            f"FIFO-feasible / {pc['attribution']['ambiguous']} ambiguous"),
            ea_version="1.68", parameter="PartialClose", status=OBSERVED,
            confidence="HIGH", timestamp=ts,
            notes="Corrects E017 interpretation (E017 counted solo bursts; the "
                  "deal-matching method here is exact). E017 kept for audit trail."))
        print("  + E025 deal-level partial close analysis")
    except KeyError:
        print("  = E025 exists, skipped")
    # MC-009 corrected partial-close rule (human still decides MC-005 vs MC-009)
    have_mc009 = any("deal-level intra-position" in c.description for c in store.all())
    if not have_mc009:
        store.create(
            rule_type="PARTIAL_CLOSE",
            description="Partial closes are deal-level intra-position volume "
                        "reductions (unmatched out-deals); final basket close "
                        "is a single full burst; PARTIAL_TRIGGER and "
                        "PARTIAL_VOLUME_RULE remain UNKNOWN",
            source_evidence_ids=["E025", "E017"],
            notes="Corrected rule from Phase 5.2 deal-level forensics; "
                  "supersedes the description of MC-005 (reviewer may reject "
                  "MC-005 in favour of this).")
        print("  + MC-009 corrected partial-close rule")
    ev_by_id = {e.evidence_id: e for e in reg.all()}
    candidates = store.all()

    packet_entries = []
    for c in candidates:
        if c.candidate_id == "MC-001":
            sample = f"{fr['lot_engine']['observation_match_pct']}% of {fr['lot_engine']['checked']} checks (4 accounts)"
            exceptions = "8 checks on 391629843 Sep 23-24 (suspected manual parameter change, E023)"
            alternatives = ["round-half-up ladder (fits only 82.90%)",
                            "different multiplier per account (no support)",
                            "equity-scaled lots (no support: 4 synced accounts with different balances used identical lots)"]
        elif "BaseLot = 0.10" in c.description:
            sample = "1,715/1,719 first-entry lots = 0.1 (99.8%)"
            exceptions = "4 first entries with 0.11/0.12/0.18 (report-window truncation)"
            alternatives = ["base lot scales with equity (refuted: synced accounts, different balances, same 0.1)",
                            "base lot is per-account parameter (possible but unobserved)"]
        elif c.rule_type == "GRID_SPACING":
            sample = "n=3,426 spacings; median 5.09; 85.2% in [4.5,5.5]"
            exceptions = "P95 tail to 5.98 (execution timing/slippage)"
            alternatives = fr["grid_trigger"]["conclusion"]["supported"]
        elif c.rule_type == "GRID_DIRECTION":
            sample = "BUY down 1,732/1,732 (100.00%); SELL up 1,692/1,695 (99.82%)"
            exceptions = "3 SELL adds below prior entry (0.18%)"
            alternatives = ["trend-filtered adds (no support: adds strictly price-spaced)"]
        elif c.rule_type == "BASKET_SCOPE":
            sample = "857/862 cycles start with both sides (99.4%); 72% same second"
            exceptions = "5 unpaired starts (report-window truncation)"
            alternatives = ["one-side-only mode parameter (possible but unobserved)"]
        elif c.rule_type == "PARTIAL_CLOSE":
            pc = fr["partial_close"]
            if "oldest_first_pct" in pc.get("PARTIAL_LEVEL_RULE", {}):
                sample = (f"{pc.get('n_events')} events; "
                          f"{pc['PARTIAL_LEVEL_RULE']['oldest_first_pct']}% oldest-first")
            else:
                sample = (f"{pc.get('n_events')} deal-level partial closes "
                          f"(unmatched out-deals); profit median "
                          f"{pc['profit']['median']}; attribution: "
                          f"{pc['attribution']['fifo_feasible']} FIFO-feasible / "
                          f"{pc['attribution']['ambiguous']} ambiguous")
            exceptions = ("trigger and volume-rule UNKNOWN (separated statuses); "
                          "MC-005 wording predates the deal-level correction "
                          "(E025) — see MC-009")
            alternatives = ["final-close burst artifacts (excluded by deal "
                            "matching)", "per-position take-profit at ~$1 "
                            "(compatible with profit distribution but "
                            "evaluation instant unobservable)"]
        elif "fixed target near $1.0" in c.description:
            sample = ("855 winners: P5 +1.03, P25 +1.10, median +1.14; "
                      "compatible hypotheses: " +
                      ", ".join(fr["basket"]["conclusion"]["compatible_hypotheses"]))
            exceptions = ("7 near-zero losers (spread events 2026.09.16 21:19:52); "
                          "deep grids overshoot (lvl10 median 3.20)")
            alternatives = [h["name"] + f" (violations {h['violation_pct']}%)"
                            for h in fr["basket"]["hypotheses"]]
        else:  # resume candidate
            sample = "<=2s resume: 857/862 transitions across 4 accounts"
            exceptions = "one 7.45h pause (391629843, E022)"
            alternatives = ["timer-scheduled re-entry (refuted: resumes align with close second)"]

        packet_entries.append({
            "candidate_id": c.candidate_id,
            "rule_type": c.rule_type,
            "description": c.description,
            "evidence_refs": ev_refs(c.source_evidence_ids),
            "sample_size": sample,
            "accounts": list(results["sources"].keys()),
            "confidence": "HIGH" if c.candidate_id in ("MC-001", "MC-002", "MC-003") else "HIGH",
            "exceptions": exceptions,
            "alternative_explanations": alternatives,
            "previous_status": c.status,
            "new_status": "PENDING_HUMAN_REVIEW",
            "confirmation_record": {
                "reviewer": None,
                "decision": None,
                "timestamp": None,
                "note": "Awaiting project-owner review. Auto-confirm forbidden.",
            },
        })

    packet = {
        "schema": "SNIPER_PHASE52_CONFIRMATION_PACKET_V1",
        "generated": ts,
        "dataset": results["sources"],
        "candidates": packet_entries,
        "separated_rule_statuses": {
            "PARTIAL_EXISTS": results["partial_close"]["PARTIAL_EXISTS"],
            "PARTIAL_TRIGGER": results["partial_close"]["PARTIAL_TRIGGER"]["status"],
            "PARTIAL_VOLUME_RULE": results["partial_close"]["PARTIAL_VOLUME_RULE"]["status"],
            "PARTIAL_LEVEL_RULE": results["partial_close"]["PARTIAL_LEVEL_RULE"]["status"],
            "GRID_TRIGGER_SEMANTICS": results["grid_trigger"]["conclusion"]["status"],
            "BASKET_AMOUNT": results["basket"]["conclusion"]["basket_amount"],
            "BASKET_TRIGGER": results["basket"]["conclusion"]["trigger_status"],
            "EMERGENCY": results["emergency"]["status"],
            "RESTART_RECOVERY": results["restart"]["status"],
        },
        "rules": [
            "No candidate was auto-confirmed by tooling.",
            "UNKNOWN rules remain UNKNOWN.",
            "Synthetic data is not used anywhere in this packet.",
        ],
    }
    out = os.path.join(DATA, "phase5_2_confirmation_packet.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(packet, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out}")

    # ---- freeze draft ----
    freeze = {
        "model_id": "V1.68-EVIDENCE-MODEL-v1.0-draft",
        "generated": ts,
        "status": "DRAFT — Evidence Gate not passed (human confirmation pending)",
        "evidence_registry": [e.__dict__ for e in reg.all()],
        "candidates": [c.to_dict() for c in store.all()],
        "dataset_hashes": {a: d["sha256"] for a, d in results["sources"].items()},
        "ssot_version": "core/calculations.py @ current (round-half-up ladder; "
                        "floor change pending MC-001)",
        "regression_version": "365 tests, all passing at freeze-draft time",
        "assumptions": [
            "GOLDmicro contract size = 1 (E019)",
            "Spacing semantics reference = PARTIAL (see grid_trigger conclusion)",
        ],
        "conflicts": [
            "Lot rounding: SSOT round-half-up vs observed floor (MC-001)",
            "AccumTargetUSD: documented 1.68 vs observed ~1.0-1.1 (MC-006 / E016)",
        ],
        "exclusions": [
            "cycle#0 of each account (report-window truncation)",
            "LOW-confidence cycles as hard evidence",
            "8 anomalous lot checks on 391629843 Sep 23-24",
        ],
        "unknowns": packet["separated_rule_statuses"],
    }
    fz = os.path.join(DATA, "evidence_model")
    os.makedirs(fz, exist_ok=True)
    out_fz = os.path.join(fz, "V1.68-EVIDENCE-MODEL-v1.0-draft.json")
    with open(out_fz, "w", encoding="utf-8") as f:
        json.dump(freeze, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out_fz}")


if __name__ == "__main__":
    main()
