"""Phase 5 Finalization: comprehensive 4-account evidence validation.

Reads all 4 MT5 xlsx files, performs rigorous per-rule validation,
and outputs formal evidence with full traceability.
"""
import hashlib
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DESKTOP = r"C:\Users\BANK\Desktop"
ACCOUNTS = ["335504856", "391629843", "411173797", "440192945"]
LOT_STEP = 0.01  # XM GOLDmicro volume step


def safe_float(v):
    if v is None:
        return 0.0
    s = str(v).strip()
    if "/" in s:
        s = s.split("/")[0].strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def safe_str(v):
    return str(v).strip() if v else ""


def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest().upper()


def load_account(filepath):
    wb = openpyxl.load_workbook(filepath, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    positions = []
    for i, row in enumerate(rows):
        if i < 7:
            continue
        if safe_str(row[2]) != "GOLDmicro":
            continue
        vol = safe_float(row[4])
        if vol <= 0:
            continue
        positions.append({
            "open_time": safe_str(row[0]),
            "ticket": safe_str(row[1]),
            "side": "BUY" if safe_str(row[3]).lower() == "buy" else "SELL",
            "volume": vol,
            "open_price": safe_float(row[5]),
            "close_time": safe_str(row[8]) if row[8] else "",
            "close_price": safe_float(row[9]),
            "commission": safe_float(row[10]),
            "swap": safe_float(row[11]),
            "profit": safe_float(row[12]),
        })
    return positions


def group_cycles(positions):
    close_groups = defaultdict(list)
    for p in positions:
        if p["close_time"]:
            close_groups[p["close_time"]].append(p)
    cycles = []
    for ct in sorted(close_groups.keys()):
        members = sorted(close_groups[ct], key=lambda x: x["open_time"])
        cycles.append({"close_time": ct, "members": members})
    return cycles


def normalize_lot(raw, step=LOT_STEP):
    return round(round(raw / step) * step, 8)


# ===========================================================================
# VALIDATION FUNCTIONS
# ===========================================================================
def validate_lot_formula(all_cycles, accounts):
    """Check Lot(n) = 0.1 × 1.1^(n-1) with broker step normalization."""
    results = {"total": 0, "match": 0, "mismatch": 0, "errors": [],
               "per_account": {}, "max_level_seen": 0}
    for acct in accounts:
        results["per_account"][acct] = {"match": 0, "mismatch": 0}

    for cyc_info in all_cycles:
        acct = cyc_info["account"]
        cyc = cyc_info["cycle"]
        for side in ("BUY", "SELL"):
            side_pos = [m for m in cyc["members"] if m["side"] == side]
            side_pos.sort(key=lambda x: x["open_time"])
            for level, p in enumerate(side_pos, start=1):
                if level == 1:
                    continue  # base lot checked separately
                expected_raw = 0.1 * (1.1 ** (level - 1))
                expected = normalize_lot(expected_raw)
                observed = p["volume"]
                error = abs(observed - expected)
                results["total"] += 1
                results["max_level_seen"] = max(results["max_level_seen"], len(side_pos))
                # tolerance = half a lot step (broker rounding)
                if error <= LOT_STEP / 2 + 1e-9:
                    results["match"] += 1
                    results["per_account"][acct]["match"] += 1
                else:
                    results["mismatch"] += 1
                    results["per_account"][acct]["mismatch"] += 1
                    if len(results["errors"]) < 10:
                        results["errors"].append({
                            "account": acct, "cycle": cyc["close_time"],
                            "side": side, "level": level,
                            "observed": observed, "expected": expected,
                            "error": round(error, 6),
                        })
    if results["total"] > 0:
        results["match_rate"] = round(results["match"] / results["total"] * 100, 2)
    return results


def validate_grid_spacing(all_cycles, accounts):
    """Analyze grid spacing distribution with full statistics."""
    spacings = []
    for cyc_info in all_cycles:
        cyc = cyc_info["cycle"]
        acct = cyc_info["account"]
        for side in ("BUY", "SELL"):
            side_pos = sorted([m for m in cyc["members"] if m["side"] == side],
                              key=lambda x: x["open_time"])
            for a, b in zip(side_pos, side_pos[1:]):
                if a["open_price"] > 0 and b["open_price"] > 0:
                    s = abs(b["open_price"] - a["open_price"])
                    if s < 100:  # filter cross-cycle artifacts
                        spacings.append({"value": s, "account": acct,
                                         "side": side})
    if not spacings:
        return {"error": "no valid spacings"}

    values = [s["value"] for s in spacings]
    sorted_vals = sorted(values)
    n = len(values)

    # percentiles
    def pct(p):
        idx = int(n * p / 100)
        return sorted_vals[min(idx, n - 1)]

    # per-account
    per_acct = {}
    for acct in accounts:
        acct_vals = [s["value"] for s in spacings if s["account"] == acct]
        if acct_vals:
            per_acct[acct] = {
                "count": len(acct_vals),
                "median": round(statistics.median(acct_vals), 3),
                "mean": round(statistics.mean(acct_vals), 3),
            }

    # per-direction
    per_dir = {}
    for d in ("BUY", "SELL"):
        dir_vals = [s["value"] for s in spacings if s["side"] == d]
        if dir_vals:
            per_dir[d] = {"count": len(dir_vals),
                          "median": round(statistics.median(dir_vals), 3)}

    # cluster around 5.0
    near_5 = sum(1 for v in values if 4.0 <= v <= 6.0)
    tight_5 = sum(1 for v in values if 4.5 <= v <= 5.5)

    return {
        "count": n,
        "min": round(min(values), 3), "max": round(max(values), 3),
        "mean": round(statistics.mean(values), 3),
        "median": round(statistics.median(values), 3),
        "stdev": round(statistics.stdev(values), 3),
        "p5": round(pct(5), 3), "p25": round(pct(25), 3),
        "p50": round(pct(50), 3), "p75": round(pct(75), 3),
        "p95": round(pct(95), 3),
        "per_account": per_acct, "per_direction": per_dir,
        "in_4to6": near_5, "in_4to6_pct": round(near_5 / n * 100, 1),
        "in_4.5to5.5": tight_5, "in_4.5to5.5_pct": round(tight_5 / n * 100, 1),
    }


def validate_direction(all_cycles):
    buy_correct = buy_wrong = sell_correct = sell_wrong = 0
    for cyc_info in all_cycles:
        cyc = cyc_info["cycle"]
        for side in ("BUY", "SELL"):
            side_pos = sorted([m for m in cyc["members"] if m["side"] == side],
                              key=lambda x: x["open_time"])
            for a, b in zip(side_pos, side_pos[1:]):
                if a["open_price"] > 0 and b["open_price"] > 0:
                    if side == "BUY":
                        if b["open_price"] < a["open_price"]:
                            buy_correct += 1
                        else:
                            buy_wrong += 1
                    else:
                        if b["open_price"] > a["open_price"]:
                            sell_correct += 1
                        else:
                            sell_wrong += 1
    return {"buy_down": buy_correct, "buy_up": buy_wrong,
            "sell_up": sell_correct, "sell_down": sell_wrong,
            "buy_rate": round(buy_correct / max(buy_correct + buy_wrong, 1) * 100, 1),
            "sell_rate": round(sell_correct / max(sell_correct + sell_wrong, 1) * 100, 1)}


def validate_both_sides(all_cycles):
    both = single_buy = single_sell = neither = 0
    for cyc_info in all_cycles:
        cyc = cyc_info["cycle"]
        has_buy = any(m["side"] == "BUY" for m in cyc["members"])
        has_sell = any(m["side"] == "SELL" for m in cyc["members"])
        if has_buy and has_sell:
            both += 1
        elif has_buy:
            single_buy += 1
        elif has_sell:
            single_sell += 1
        else:
            neither += 1
    total = both + single_buy + single_sell + neither
    return {"total": total, "both_sides": both,
            "single_buy": single_buy, "single_sell": single_sell,
            "neither": neither,
            "both_rate": round(both / max(total, 1) * 100, 1)}


def validate_base_lot(all_cycles, accounts):
    lots = defaultdict(list)
    for cyc_info in all_cycles:
        cyc = cyc_info["cycle"]
        acct = cyc_info["account"]
        for side in ("BUY", "SELL"):
            side_pos = sorted([m for m in cyc["members"] if m["side"] == side],
                              key=lambda x: x["open_time"])
            if side_pos:
                lots[acct].append(side_pos[0]["volume"])
    all_lots = [l for vals in lots.values() for l in vals]
    from collections import Counter
    dist = Counter(all_lots)
    return {
        "total_first_entries": len(all_lots),
        "distribution": dict(dist.most_common(10)),
        "is_01_dominant": dist.most_common(1)[0][0] == 0.1 if all_lots else False,
        "pct_01": round(dist.get(0.1, 0) / max(len(all_lots), 1) * 100, 1),
        "per_account": {a: Counter(v).most_common(3) for a, v in lots.items()},
    }


def validate_basket_pl(all_cycles):
    baskets = []
    for cyc_info in all_cycles:
        cyc = cyc_info["cycle"]
        if len(cyc["members"]) < 2:
            continue
        gross = sum(m["profit"] for m in cyc["members"])
        comm = sum(m["commission"] for m in cyc["members"])
        swap = sum(m["swap"] for m in cyc["members"])
        net = gross + comm + swap
        baskets.append({
            "gross": round(gross, 4), "commission": round(comm, 4),
            "swap": round(swap, 4), "net": round(net, 4),
            "positions": len(cyc["members"]),
        })
    if not baskets:
        return {"error": "no baskets"}

    gross_vals = [b["gross"] for b in baskets]
    net_vals = [b["net"] for b in baskets]
    # How many near 1.68?
    near_168_gross = sum(1 for v in gross_vals if 1.4 <= v <= 2.0)
    near_168_net = sum(1 for v in net_vals if 1.4 <= v <= 2.0)

    return {
        "count": len(baskets),
        "gross": {"mean": round(statistics.mean(gross_vals), 4),
                  "median": round(statistics.median(gross_vals), 4),
                  "stdev": round(statistics.stdev(gross_vals), 4)},
        "net": {"mean": round(statistics.mean(net_vals), 4),
                "median": round(statistics.median(net_vals), 4)},
        "near_1.68_gross": near_168_gross,
        "near_1.68_gross_pct": round(near_168_gross / len(baskets) * 100, 1),
        "near_1.68_net": near_168_net,
        "near_1.68_net_pct": round(near_168_net / len(baskets) * 100, 1),
        "has_commission": any(b["commission"] != 0 for b in baskets),
        "has_swap": any(b["swap"] != 0 for b in baskets),
    }


def validate_partial(all_cycles):
    """Detect partial closes: volume reduction within same cycle."""
    partial_candidates = []
    for cyc_info in all_cycles:
        cyc = cyc_info["cycle"]
        side_pos = sorted(cyc["members"], key=lambda x: x["open_time"])
        # Look for non-monotonic volume within a cycle
        vols = [p["volume"] for p in side_pos]
        for i in range(1, len(vols)):
            if vols[i] < vols[i - 1] and vols[i] > 0:
                # Volume decreased — could be partial close
                # But need to distinguish from cycle boundary
                partial_candidates.append({
                    "cycle": cyc["close_time"],
                    "index": i, "prev_vol": vols[i - 1], "this_vol": vols[i],
                })
    # Most volume decreases are likely cycle boundaries (0.1 after 0.5)
    # True partials would show same ticket reopened with less volume
    # Without ticket-level close data, this is INCONCLUSIVE
    return {
        "volume_decreases": len(partial_candidates),
        "sample": partial_candidates[:5],
        "conclusion": "INCONCLUSIVE — position history format does not "
                      "distinguish partial close from cycle boundary. "
                      "Need deal-level data with individual close records.",
    }


def validate_emergency(all_cycles):
    """Look for cycles with abnormal close patterns (large loss + many positions)."""
    emergency_candidates = []
    for cyc_info in all_cycles:
        cyc = cyc_info["cycle"]
        total_pl = sum(m["profit"] for m in cyc["members"])
        n_pos = len(cyc["members"])
        # Emergency candidate: many positions + significant loss
        if n_pos >= 5 and total_pl < -10:
            emergency_candidates.append({
                "close_time": cyc["close_time"], "positions": n_pos,
                "total_pl": round(total_pl, 2),
            })
    return {
        "candidates": len(emergency_candidates),
        "sample": emergency_candidates[:5],
        "conclusion": "INCONCLUSIVE — large loss alone does not prove emergency. "
                      "Cannot distinguish emergency close from normal basket "
                      "close at adverse price without deal-level sequence data.",
    }


def validate_resume(all_cycles):
    """Analyze gap between basket close and next cycle start."""
    gaps = []
    sorted_cycles = sorted(all_cycles, key=lambda x: x["cycle"]["close_time"])
    for i in range(len(sorted_cycles) - 1):
        curr_close = sorted_cycles[i]["cycle"]["close_time"]
        next_members = sorted_cycles[i + 1]["cycle"]["members"]
        if next_members:
            next_open = min(m["open_time"] for m in next_members)
            # Parse times
            try:
                from datetime import datetime as dt
                fmt = "%Y.%m.%d %H:%M:%S"
                ct = dt.strptime(curr_close, fmt)
                no = dt.strptime(next_open, fmt)
                gap_sec = (no - ct).total_seconds()
                gaps.append(gap_sec)
            except (ValueError, TypeError):
                pass
    if not gaps:
        return {"conclusion": "no parseable gaps"}
    return {
        "count": len(gaps),
        "median_gap_sec": round(statistics.median(gaps), 1),
        "min_gap_sec": round(min(gaps), 1),
        "max_gap_sec": round(max(gaps), 1),
        "immediate": sum(1 for g in gaps if g <= 1),
        "conclusion": "NORMAL_RESUME observed (next cycle follows basket close). "
                      "RESTART_RESUME = UNKNOWN (no controlled restart in data).",
    }


def infer_contract_size(all_cycles):
    """Infer GOLDmicro contract size from P/L, volume, and price difference."""
    implied = []
    for cyc_info in all_cycles[:200]:  # sample
        for m in cyc_info["cycle"]["members"]:
            if m["open_price"] > 0 and m["close_price"] > 0 and m["volume"] > 0:
                price_diff = m["close_price"] - m["open_price"]
                if m["side"] == "BUY":
                    directional = price_diff
                else:
                    directional = -price_diff
                # P/L ≈ directional × volume × contract_size
                if abs(directional) > 0.1 and abs(m["profit"]) > 0.01:
                    cs = m["profit"] / (directional * m["volume"])
                    if 0 < cs < 1000:
                        implied.append(cs)
    if not implied:
        return {"conclusion": "could not infer"}
    return {
        "count": len(implied),
        "median": round(statistics.median(implied), 2),
        "mean": round(statistics.mean(implied), 2),
        "stdev": round(statistics.stdev(implied), 2),
        "conclusion": f"GOLDmicro contract size ≈ {statistics.median(implied):.0f} "
                      f"(implied from {len(implied)} trades)",
    }


# ===========================================================================
# MAIN
# ===========================================================================
def main():
    print("=" * 80)
    print("PHASE 5 FINALIZATION — COMPREHENSIVE 4-ACCOUNT EVIDENCE VALIDATION")
    print(f"Started: {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 80)

    all_cycles = []
    sources = []

    for acct in ACCOUNTS:
        filepath = os.path.join(DESKTOP, f"ReportHistory-{acct}.xlsx")
        if not os.path.exists(filepath):
            print(f"SKIP {acct}: not found")
            continue
        sha = file_hash(filepath)
        positions = load_account(filepath)
        cycles = group_cycles(positions)
        buys = sum(1 for p in positions if p["side"] == "BUY")
        sells = sum(1 for p in positions if p["side"] == "SELL")
        sources.append({
            "account": acct, "file": os.path.basename(filepath),
            "sha256": sha, "positions": len(positions),
            "buys": buys, "sells": sells, "cycles": len(cycles),
        })
        for cyc in cycles:
            all_cycles.append({"account": acct, "cycle": cyc})
        print(f"  {acct}: {len(positions)} pos ({buys}B/{sells}S), "
              f"{len(cycles)} cycles, hash={sha[:12]}...")

    print(f"\nTotal: {len(all_cycles)} cycles from {len(sources)} accounts")

    # Run all validations
    print("\n" + "=" * 80)
    print("1. LOT FORMULA VALIDATION")
    print("=" * 80)
    lot = validate_lot_formula(all_cycles, ACCOUNTS)
    print(f"  Total checked: {lot['total']}")
    print(f"  Match: {lot['match']} ({lot.get('match_rate', 0)}%)")
    print(f"  Mismatch: {lot['mismatch']}")
    print(f"  Max level seen: {lot['max_level_seen']}")
    if lot["errors"]:
        print(f"  Sample errors: {lot['errors'][:3]}")
    for a, s in lot["per_account"].items():
        print(f"  {a}: {s['match']} match / {s['mismatch']} mismatch")

    print("\n" + "=" * 80)
    print("2. GRID SPACING VALIDATION")
    print("=" * 80)
    grid = validate_grid_spacing(all_cycles, ACCOUNTS)
    print(f"  Count: {grid['count']}")
    print(f"  Median: {grid['median']} | Mean: {grid['mean']} | Stdev: {grid['stdev']}")
    print(f"  P5: {grid['p5']} | P25: {grid['p25']} | P75: {grid['p75']} | P95: {grid['p95']}")
    print(f"  In 4-6 range: {grid['in_4to6']} ({grid['in_4to6_pct']}%)")
    print(f"  In 4.5-5.5 range: {grid['in_4.5to5.5']} ({grid['in_4.5to5.5_pct']}%)")
    print(f"  Per account: {grid['per_account']}")
    print(f"  Per direction: {grid['per_direction']}")

    print("\n" + "=" * 80)
    print("3. GRID DIRECTION VALIDATION")
    print("=" * 80)
    direction = validate_direction(all_cycles)
    print(f"  BUY adds DOWN: {direction['buy_down']} ({direction['buy_rate']}%)")
    print(f"  SELL adds UP: {direction['sell_up']} ({direction['sell_rate']}%)")

    print("\n" + "=" * 80)
    print("4. BOTH-SIDES INITIAL ENTRY")
    print("=" * 80)
    both = validate_both_sides(all_cycles)
    print(f"  Total cycles: {both['total']}")
    print(f"  Both sides: {both['both_sides']} ({both['both_rate']}%)")
    print(f"  Single BUY: {both['single_buy']} | Single SELL: {both['single_sell']}")

    print("\n" + "=" * 80)
    print("5. BASE LOT VALIDATION")
    print("=" * 80)
    base = validate_base_lot(all_cycles, ACCOUNTS)
    print(f"  First entries: {base['total_first_entries']}")
    print(f"  Distribution: {base['distribution']}")
    print(f"  0.1 dominant: {base['is_01_dominant']} ({base['pct_01']}%)")

    print("\n" + "=" * 80)
    print("6. BASKET P/L ANALYSIS")
    print("=" * 80)
    basket = validate_basket_pl(all_cycles)
    print(f"  Baskets: {basket['count']}")
    print(f"  Gross P/L: mean={basket['gross']['mean']}, median={basket['gross']['median']}")
    print(f"  Net P/L: mean={basket['net']['mean']}, median={basket['net']['median']}")
    print(f"  Near 1.68 (gross): {basket['near_1.68_gross']} ({basket['near_1.68_gross_pct']}%)")
    print(f"  Near 1.68 (net): {basket['near_1.68_net']} ({basket['near_1.68_net_pct']}%)")
    print(f"  Has commission data: {basket['has_commission']}")
    print(f"  Has swap data: {basket['has_swap']}")

    print("\n" + "=" * 80)
    print("7. PARTIAL CLOSE DETECTION")
    print("=" * 80)
    partial = validate_partial(all_cycles)
    print(f"  Volume decreases: {partial['volume_decreases']}")
    print(f"  Conclusion: {partial['conclusion']}")

    print("\n" + "=" * 80)
    print("8. EMERGENCY DETECTION")
    print("=" * 80)
    emergency = validate_emergency(all_cycles)
    print(f"  Candidates: {emergency['candidates']}")
    print(f"  Conclusion: {emergency['conclusion']}")

    print("\n" + "=" * 80)
    print("9. RESUME BEHAVIOR")
    print("=" * 80)
    resume = validate_resume(all_cycles)
    print(f"  Gaps analyzed: {resume.get('count', 0)}")
    print(f"  Median gap: {resume.get('median_gap_sec', '?')} sec")
    print(f"  Conclusion: {resume.get('conclusion', '?')}")

    print("\n" + "=" * 80)
    print("10. CONTRACT SIZE INFERENCE")
    print("=" * 80)
    contract = infer_contract_size(all_cycles)
    print(f"  Median: {contract.get('median', '?')}")
    print(f"  Conclusion: {contract.get('conclusion', '?')}")

    # Save results
    results = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "sources": sources,
        "lot_formula": lot, "grid_spacing": grid,
        "grid_direction": direction, "both_sides": both,
        "base_lot": base, "basket_pl": basket,
        "partial": partial, "emergency": emergency,
        "resume": resume, "contract_size": contract,
    }
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "phase5_validation_results.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nResults saved: {out}")

    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
