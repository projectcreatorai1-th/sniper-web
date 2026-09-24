"""Phase 5.1 forensic v3 — DEFINITIVE analysis from the full MT5 report.

Each xlsx contains FIVE sections:
  Positions     per-position history (open/close, P/L)
  Orders        every market order (requested/filled, state, EA comment)
  Deals         every deal (direction in/out, volume, price, profit,
                running BALANCE, EA comment on entries)
  Open Positions current basket at export time
  Results        account summary (net profit, PF, trade counts)

Reconstructions:
  cycles       = event-walk over positions (closes before opens at same ts)
  partial      = close that does not empty the open basket
  close bursts = out-deals grouped by <=5s gaps (realization events)
"""
import hashlib
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime

import openpyxl

DESKTOP = r"C:\Users\BANK\Desktop"
ACCOUNTS = ["335504856", "391629843", "411173797", "440192945"]
LOT_STEP = 0.01
FMT = "%Y.%m.%d %H:%M:%S"
SECTION_NAMES = ("Positions", "Orders", "Deals", "Open Positions", "Results")


def sf(v):
    if v is None:
        return 0.0
    s = str(v).strip()
    if "/" in s:
        s = s.split("/")[0].strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def ss(v):
    return str(v).strip() if v is not None else ""


def load_workbook_rows(filepath):
    wb = openpyxl.load_workbook(filepath, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    return rows


def find_sections(rows):
    marks = {}
    for i, r in enumerate(rows):
        v = ss(r[0]) if r else ""
        if v in SECTION_NAMES:
            marks.setdefault(v, i)
    return marks


def parse_positions(rows, start, end):
    out = []
    for i in range(start, end):
        r = rows[i]
        if ss(r[2]) != "GOLDmicro":
            continue
        vol = sf(r[4])
        if vol <= 0:
            continue
        out.append({
            "open_time": ss(r[0]), "ticket": ss(r[1]),
            "side": "BUY" if ss(r[3]).lower() == "buy" else "SELL",
            "volume": vol, "open_price": sf(r[5]),
            "close_time": ss(r[8]), "close_price": sf(r[9]),
            "commission": sf(r[10]), "swap": sf(r[11]), "profit": sf(r[12]),
        })
    return out


def parse_orders(rows, start, end):
    out = []
    for i in range(start, end):
        r = rows[i]
        if ss(r[2]) != "GOLDmicro":
            continue
        vols = ss(r[4])
        req, filled = (sf(x) for x in vols.split("/")) if "/" in vols else (sf(vols), sf(vols))
        out.append({
            "time": ss(r[0]), "order_id": ss(r[1]),
            "side": "BUY" if ss(r[3]).lower() == "buy" else "SELL",
            "vol_req": req, "vol_filled": filled, "price_type": ss(r[5]),
            "fill_time": ss(r[8]), "state": ss(r[9]), "comment": ss(r[11]),
        })
    return out


def parse_deals(rows, start, end):
    out = []
    for i in range(start, end):
        r = rows[i]
        if ss(r[2]) != "GOLDmicro":
            continue  # skips balance/credit rows too
        out.append({
            "time": ss(r[0]), "deal_id": ss(r[1]),
            "side": "BUY" if ss(r[3]).lower() == "buy" else "SELL",
            "direction": ss(r[4]),           # in / out
            "volume": sf(r[5]), "price": sf(r[6]), "order_id": ss(r[7]),
            "commission": sf(r[8]), "fee": sf(r[9]), "swap": sf(r[10]),
            "profit": sf(r[11]), "balance": sf(r[12]), "comment": ss(r[13]),
        })
    return out


def parse_balance_rows(rows, start, end):
    """balance/credit deals before trading starts (symbol empty)."""
    out = []
    for i in range(start, end):
        r = rows[i]
        if ss(r[2]) == "" and ss(r[3]) in ("balance", "credit"):
            out.append({"time": ss(r[0]), "type": ss(r[3]),
                        "profit": sf(r[11]), "balance": sf(r[12]),
                        "comment": ss(r[13])})
    return out


def parse_open_positions(rows, start, end):
    out = []
    for i in range(start, end):
        r = rows[i]
        if ss(r[2]) != "GOLDmicro":
            continue
        vol = sf(r[4])
        if vol <= 0:
            continue
        out.append({
            "open_time": ss(r[0]), "ticket": ss(r[1]),
            "side": "BUY" if ss(r[3]).lower() == "buy" else "SELL",
            "volume": vol, "open_price": sf(r[5]), "market_price": sf(r[8]),
            "swap": sf(r[9]), "profit": sf(r[11]), "comment": ss(r[12]),
        })
    return out


def load_account(acct):
    fp = os.path.join(DESKTOP, f"ReportHistory-{acct}.xlsx")
    with open(fp, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest().upper()
    rows = load_workbook_rows(fp)
    marks = find_sections(rows)
    p_end = marks.get("Orders", len(rows))
    o_end = marks.get("Deals", len(rows))
    d_end = marks.get("Open Positions", len(rows))
    op_end = marks.get("Results", len(rows))
    return {
        "sha256": sha,
        "account_line": ss(rows[2][3]),
        "positions": parse_positions(rows, 7, p_end),
        "orders": parse_orders(rows, marks.get("Orders", 0) + 2, o_end),
        "deals": parse_deals(rows, marks.get("Deals", 0) + 2, d_end),
        "balance_rows": parse_balance_rows(rows, marks.get("Deals", 0) + 2, d_end),
        "open_positions": parse_open_positions(rows, marks.get("Open Positions", 0) + 2, op_end),
    }


def reconstruct_cycles(positions):
    """Closes sort BEFORE opens at identical timestamps (EA closes basket,
    sees flat, then opens the new pair)."""
    events = []
    for idx, p in enumerate(positions):
        events.append((p["open_time"], 1, idx))
        if p["close_time"]:
            events.append((p["close_time"], 0, idx))
    events.sort()

    cycles, current, open_count = [], [], 0
    partials = []
    for ts, kind, idx in events:
        if kind == 1:
            current.append(idx)
            open_count += 1
        else:
            open_count -= 1
            if open_count > 0:
                partials.append({"time": ts, "ticket": positions[idx]["ticket"],
                                 "idx": idx, "remaining": open_count})
            elif open_count == 0 and current:
                members = [positions[i] for i in current]
                closes = sorted(m["close_time"] for m in members if m["close_time"])
                cycles.append({
                    "members": sorted(members, key=lambda x: (x["open_time"], x["ticket"])),
                    "close_end": closes[-1] if closes else "",
                    "open_start": members[0]["open_time"],
                })
                current = []
    if current:
        members = [positions[i] for i in current]
        cycles.append({
            "members": sorted(members, key=lambda x: (x["open_time"], x["ticket"])),
            "close_end": "", "open_start": members[0]["open_time"], "open": True,
        })
    return cycles, partials


def close_bursts(out_deals, gap=5.0):
    """Group out-deals whose times are within `gap` seconds."""
    bursts = []
    cur = []
    for d in sorted(out_deals, key=lambda x: x["time"]):
        if cur and (datetime.strptime(d["time"], FMT) -
                    datetime.strptime(cur[-1]["time"], FMT)).total_seconds() > gap:
            bursts.append(cur)
            cur = []
        cur.append(d)
    if cur:
        bursts.append(cur)
    return bursts


def expected_lot(level):
    raw = 0.1 * (1.1 ** (level - 1))
    return round(round(raw / LOT_STEP) * LOT_STEP, 8)


def pct(x, y):
    return x / y * 100 if y else 0.0


def main():
    print("=" * 80)
    print("PHASE 5.1 FORENSIC v3 — POSITIONS + ORDERS + DEALS")
    print(f"Time: {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 80)

    acc = {a: load_account(a) for a in ACCOUNTS}
    for a in ACCOUNTS:
        d = acc[a]
        print(f"{a}: {len(d['positions'])} pos | {len(d['orders'])} orders | "
              f"{len(d['deals'])} deals | {len(d['open_positions'])} open now | "
              f"sha={d['sha256'][:12]}…")
        print(f"    {d['account_line']}")

    # ---------------- A. provenance + integrity ----------------
    print("\n" + "=" * 80)
    print("A. EA PROVENANCE + DATA INTEGRITY")
    print("=" * 80)
    for a in ACCOUNTS:
        d = acc[a]
        in_d = [x for x in d["deals"] if x["direction"] == "in"]
        out_d = [x for x in d["deals"] if x["direction"] == "out"]
        cf_in = sum(1 for x in in_d if x["comment"].startswith("CashFlow"))
        cf_out = sum(1 for x in out_d if x["comment"].startswith("CashFlow"))
        states = Counter(o["state"] for o in d["orders"])
        nonmarket = [o for o in d["orders"] if o["price_type"] != "market"]
        part_fill = [o for o in d["orders"]
                     if o["vol_req"] > 0 and abs(o["vol_req"] - o["vol_filled"]) > 1e-9]
        # balance chain
        deals_b = d["balance_rows"] + [x for x in d["deals"] if x["balance"] > 0]
        chain_ok = True
        if len(deals_b) >= 2:
            prev = deals_b[0]["balance"]
            for x in deals_b[1:]:
                if abs(prev + x["profit"] - x["balance"]) > 0.02:
                    chain_ok = False
                prev = x["balance"]
        vol_in = sum(x["volume"] for x in in_d)
        vol_out = sum(x["volume"] for x in out_d)
        print(f"  {a}: in-deals {cf_in}/{len(in_d)} CashFlow | out-deals w/comment: {cf_out}/{len(out_d)}")
        print(f"    order states: {dict(states)} | non-market: {len(nonmarket)} | "
              f"partial fills: {len(part_fill)}")
        print(f"    vol in={vol_in:.2f} out={vol_out:.2f} (open now "
              f"{sum(p['volume'] for p in d['open_positions']):.2f}) | "
              f"balance chain ok: {chain_ok}")

    # ---------------- B. cycles overview ----------------
    print("\n" + "=" * 80)
    print("B. CYCLE RECONSTRUCTION")
    print("=" * 80)
    cyc_data = {}
    for a in ACCOUNTS:
        cycles, partials = reconstruct_cycles(acc[a]["positions"])
        cyc_data[a] = (cycles, partials)
        complete = [c for c in cycles if not c.get("open")]
        print(f"  {a}: {len(cycles)} cycles ({len(complete)} complete, "
              f"cycle#0 may be truncated) | partial-close events: {len(partials)}")

    # ---------------- C. lot formula ----------------
    print("\n" + "=" * 80)
    print("C. LOT FORMULA — Lot(n) = 0.1 * 1.1^(n-1) rounded to 0.01")
    print("=" * 80)
    m = mm = 0
    samples = []
    max_depth = 0
    per_acct = {}
    for a in ACCOUNTS:
        cycles, _ = cyc_data[a]
        am = amm = 0
        for ci, cyc in enumerate(cycles):
            if ci == 0 or cyc.get("open"):
                continue
            for side in ("BUY", "SELL"):
                sp = [x for x in cyc["members"] if x["side"] == side]
                max_depth = max(max_depth, len(sp))
                for lvl, p in enumerate(sp, 1):
                    if lvl == 1:
                        continue
                    exp = expected_lot(lvl)
                    if abs(p["volume"] - exp) <= LOT_STEP / 2 + 1e-9:
                        am += 1
                    else:
                        amm += 1
                        if len(samples) < 10:
                            samples.append(f"    {a} cyc#{ci} L{lvl} {side}: obs={p['volume']} "
                                           f"exp={exp} open={p['open_time']}")
        per_acct[a] = (am, amm)
        m += am
        mm += amm
    tot = m + mm
    for a in ACCOUNTS:
        am, amm = per_acct[a]
        print(f"  {a}: match {am}/{am+amm} ({pct(am, am+amm):.2f}%)")
    print(f"  TOTAL: match {m}/{tot} ({pct(m, tot):.2f}%) | mismatches: {mm}")
    print(f"  Max single-side depth: {max_depth}")
    for s in samples:
        print(s)

    # ---------------- D. grid spacing + direction ----------------
    print("\n" + "=" * 80)
    print("D. GRID SPACING + DIRECTION")
    print("=" * 80)
    sp_all, bd, bw, su, sw = [], 0, 0, 0, 0
    for a in ACCOUNTS:
        cycles, _ = cyc_data[a]
        for ci, cyc in enumerate(cycles):
            if ci == 0 or cyc.get("open"):
                continue
            for side in ("BUY", "SELL"):
                sp = [x for x in cyc["members"] if x["side"] == side]
                for x, y in zip(sp, sp[1:]):
                    dd = y["open_price"] - x["open_price"]
                    if 1 < abs(dd) < 20:
                        sp_all.append(abs(dd))
                    if side == "BUY":
                        if dd < 0: bd += 1
                        elif dd > 0: bw += 1
                    else:
                        if dd > 0: su += 1
                        elif dd < 0: sw += 1
    sp_all.sort()
    n = len(sp_all)
    print(f"  n={n} median={statistics.median(sp_all):.3f} mean={statistics.mean(sp_all):.3f} "
          f"stdev={statistics.stdev(sp_all):.3f}")
    print(f"  P5={sp_all[int(n*.05)]:.2f} P25={sp_all[int(n*.25)]:.2f} P50={sp_all[int(n*.5)]:.2f} "
          f"P75={sp_all[int(n*.75)]:.2f} P95={sp_all[int(n*.95)]:.2f}")
    band = sum(1 for s in sp_all if 4.5 <= s <= 5.5)
    print(f"  in [4.5,5.5]: {band} ({pct(band, n):.1f}%)")
    print(f"  BUY down {bd} ({pct(bd, bd+bw):.2f}%) / up {bw} | SELL up {su} ({pct(su, su+sw):.2f}%) / down {sw}")

    # ---------------- E. both sides + base lot ----------------
    print("\n" + "=" * 80)
    print("E. BOTH SIDES + BASE LOT")
    print("=" * 80)
    both = single = same_sec = 0
    first_lots = []
    for a in ACCOUNTS:
        cycles, _ = cyc_data[a]
        for ci, cyc in enumerate(cycles):
            if ci == 0 or cyc.get("open"):
                continue
            mlist = cyc["members"]
            sides = set(x["side"] for x in mlist[:2])
            if sides == {"BUY", "SELL"}:
                both += 1
                if mlist[0]["open_time"] == mlist[1]["open_time"]:
                    same_sec += 1
            else:
                single += 1
            for side in ("BUY", "SELL"):
                sp = [x for x in mlist if x["side"] == side]
                if sp:
                    first_lots.append(sp[0]["volume"])
    c = Counter(first_lots)
    print(f"  cycles {both+single} | both-sides {both} ({pct(both, both+single):.1f}%) "
          f"| single {single} | first-pair same-second {same_sec}/{both}")
    print(f"  first-entry lots: {dict(c.most_common(6))} | 0.1-rate {pct(c.get(0.1,0), len(first_lots)):.1f}%")

    # ---------------- F. partial closes ----------------
    print("\n" + "=" * 80)
    print("F. PARTIAL CLOSES")
    print("=" * 80)
    tp = 0
    pl_list, vol_list = [], []
    cwp = 0
    for a in ACCOUNTS:
        cycles, partials = cyc_data[a]
        by_ticket = {p["ticket"]: p for p in acc[a]["positions"]}
        cyc_of = {}
        for ci, cyc in enumerate(cycles):
            for x in cyc["members"]:
                cyc_of[x["ticket"]] = ci
        cnt = Counter(cyc_of.get(pe["ticket"], -1) for pe in partials if cyc_of.get(pe["ticket"], 0) > 0)
        cwp += sum(1 for v in cnt.values() if v > 0)
        tp += len(partials)
        for pe in partials:
            p = by_ticket[pe["ticket"]]
            pl_list.append(p["profit"] + p["commission"] + p["swap"])
            vol_list.append(p["volume"])
        # deal-level: does one position close in multiple out-deals?
        out_d = [x for x in acc[a]["deals"] if x["direction"] == "out"]
        # match by close_time+volume heuristic is fragile; count bursts instead (below)
    print(f"  position-level partial-close events: {tp}")
    print(f"  complete cycles containing >=1 partial: {cwp}")
    if pl_list:
        print(f"  partial P/L: median={statistics.median(pl_list):+.3f} min={min(pl_list):+.2f} "
              f"max={max(pl_list):+.2f}")
        print(f"  partial volumes: {dict(Counter(vol_list).most_common(8))}")

    # ---------------- G. close bursts (deal-level realization) ----------------
    print("\n" + "=" * 80)
    print("G. CLOSE BURSTS (out-deals grouped <=5s)")
    print("=" * 80)
    burst_stats = []
    for a in ACCOUNTS:
        out_d = [x for x in acc[a]["deals"] if x["direction"] == "out"]
        bursts = close_bursts(out_d)
        cycles, partials = cyc_data[a]
        complete = [cc for cc in cycles if not cc.get("open")]
        big = [b for b in bursts if len(b) >= 2]
        solo = [b for b in bursts if len(b) == 1]
        print(f"  {a}: {len(out_d)} out-deals -> {len(bursts)} bursts "
              f"({len(big)} multi, {len(solo)} solo) vs {len(complete)} complete cycles")
        for b in bursts:
            profit = sum(x["profit"] for x in b)
            burst_stats.append({"acct": a, "n": len(b), "profit": profit,
                                "time": b[0]["time"],
                                "vol": sum(x["volume"] for x in b)})
    bs = sorted(burst_stats, key=lambda x: x["profit"])
    if bs:
        profits = [x["profit"] for x in bs]
        print(f"  All bursts: n={len(bs)} | profit min={profits[0]:+.2f} "
              f"P5={profits[int(len(profits)*.05)]:+.2f} median={statistics.median(profits):+.2f} "
              f"max={profits[-1]:+.2f}")
        neg = [x for x in bs if x["profit"] < 0]
        print(f"  Negative bursts: {len(neg)}")
        for x in neg[:8]:
            print(f"    {x['acct']} {x['time']} n={x['n']} vol={x['vol']:.2f} profit={x['profit']:+.2f}")
        big_p = [x["profit"] for x in bs if x["n"] >= 2]
        if big_p:
            print(f"  Multi-deal bursts: n={len(big_p)} min={min(big_p):+.2f} "
                  f"median={statistics.median(big_p):+.2f} max={max(big_p):+.2f}")

    # ---------------- H. basket P/L ----------------
    print("\n" + "=" * 80)
    print("H. BASKET P/L (complete cycles, all positions)")
    print("=" * 80)
    baskets = []
    for a in ACCOUNTS:
        cycles, _ = cyc_data[a]
        for ci, cyc in enumerate(cycles):
            if ci == 0 or cyc.get("open"):
                continue
            mlist = cyc["members"]
            gross = sum(x["profit"] for x in mlist)
            net = gross + sum(x["commission"] + x["swap"] for x in mlist)
            max_lvl = max(len([x for x in mlist if x["side"] == s]) for s in ("BUY", "SELL"))
            dur = ((datetime.strptime(cyc["close_end"], FMT) -
                    datetime.strptime(cyc["open_start"], FMT)).total_seconds()
                   if cyc["close_end"] else 0)
            baskets.append({"acct": a, "ci": ci, "n": len(mlist), "gross": gross,
                            "net": net, "max_lvl": max_lvl,
                            "lots": sum(x["volume"] for x in mlist), "dur_s": dur})
    gv = sorted(b["gross"] for b in baskets)
    nb = len(gv)
    print(f"  baskets: {nb}")
    print(f"  gross: min={gv[0]:+.2f} P5={gv[int(nb*.05)]:+.2f} P25={gv[int(nb*.25)]:+.2f} "
          f"median={statistics.median(gv):+.3f} P75={gv[int(nb*.75)]:+.2f} max={gv[-1]:+.2f}")
    negb = [b for b in baskets if b["gross"] < -0.005]
    print(f"  losing baskets: {len(negb)}")
    for b in negb[:8]:
        print(f"    {b['acct']} cyc#{b['ci']} n={b['n']} max_lvl={b['max_lvl']} gross={b['gross']:+.2f}")
    # near-zero/zero baskets
    zeros = [b for b in baskets if abs(b["gross"]) <= 0.01]
    print(f"  exactly-zero baskets: {len(zeros)}")
    # trigger floor estimate among clean single-burst winners
    winners = sorted(b["gross"] for b in baskets if b["gross"] > 0.005)
    if winners:
        print(f"  winners: n={len(winners)} min={winners[0]:+.3f} "
              f"P5={winners[int(len(winners)*.05)]:+.2f} P25={winners[int(len(winners)*.25)]:+.2f} "
              f"median={statistics.median(winners):+.3f}")
    by_lvl = defaultdict(list)
    for b in baskets:
        by_lvl[b["max_lvl"]].append(b["gross"])
    print("  by max grid level:")
    for k in sorted(by_lvl)[:12]:
        v = by_lvl[k]
        print(f"    lvl={k}: n={len(v)} min={min(v):+.2f} median={statistics.median(v):+.2f} max={max(v):+.2f}")

    # ---------------- I. deep grids ----------------
    print("\n" + "=" * 80)
    print("I. DEEPEST GRIDS")
    print("=" * 80)
    for b in sorted(baskets, key=lambda x: -x["max_lvl"])[:8]:
        print(f"    {b['acct']} cyc#{b['ci']} n={b['n']} max_lvl={b['max_lvl']} "
              f"lots={b['lots']:.2f} dur={b['dur_s']/3600:.1f}h gross={b['gross']:+.2f}")

    # ---------------- J. resume ----------------
    print("\n" + "=" * 80)
    print("J. RESUME GAP (complete cycle close -> next cycle open)")
    print("=" * 80)
    for a in ACCOUNTS:
        cycles, _ = cyc_data[a]
        gaps = []
        for x, y in zip(cycles, cycles[1:]):
            if not x.get("close_end"):
                continue
            g = (datetime.strptime(y["open_start"], FMT) -
                 datetime.strptime(x["close_end"], FMT)).total_seconds()
            gaps.append(g)
        if gaps:
            gaps.sort()
            imm = sum(1 for g in gaps if g <= 2)
            print(f"  {a}: {len(gaps)} gaps | <=2s {imm} ({pct(imm, len(gaps)):.0f}%) | "
                  f"median={statistics.median(gaps):.0f}s P95={gaps[int(len(gaps)*.95)]:.0f}s "
                  f"max={gaps[-1]:.0f}s")

    # ---------------- K. contract size ----------------
    print("\n" + "=" * 80)
    print("K. CONTRACT SIZE (GOLDmicro) from closed positions")
    print("=" * 80)
    implied = []
    for a in ACCOUNTS:
        for p in acc[a]["positions"]:
            if p["close_time"] and p["open_price"] > 0 and p["close_price"] > 0:
                dd = p["close_price"] - p["open_price"]
                signed = dd if p["side"] == "BUY" else -dd
                if abs(signed) > 0.5 and p["volume"] > 0:
                    cs = p["profit"] / (signed * p["volume"])
                    if 0.5 < cs < 2.0:
                        implied.append(cs)
    if implied:
        print(f"  n={len(implied)} median={statistics.median(implied):.4f} "
              f"mean={statistics.mean(implied):.4f} stdev={statistics.stdev(implied):.4f}")
        print(f"  exactly 1.0 within 0.005: {sum(1 for x in implied if abs(x-1.0)<=0.005)} "
              f"({pct(sum(1 for x in implied if abs(x-1.0)<=0.005), len(implied)):.2f}%)")

    # ---------------- save ----------------
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "phase5_1_forensic.json")
    result = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "sources": {a: {"sha256": acc[a]["sha256"],
                        "positions": len(acc[a]["positions"]),
                        "orders": len(acc[a]["orders"]),
                        "deals": len(acc[a]["deals"]),
                        "account_line": acc[a]["account_line"]} for a in ACCOUNTS},
        "summary": {
            "lot_match_pct": round(pct(m, tot), 2), "lot_checked": tot,
            "max_side_depth": max_depth,
            "spacing_median": round(statistics.median(sp_all), 3),
            "spacing_p5": round(sp_all[int(n * .05)], 2),
            "spacing_p95": round(sp_all[int(n * .95)], 2),
            "spacing_in_45_55_pct": round(pct(band, n), 1),
            "buy_down_pct": round(pct(bd, bd + bw), 2),
            "sell_up_pct": round(pct(su, su + sw), 2),
            "both_sides_pct": round(pct(both, both + single), 1),
            "first_pair_same_second_pct": round(pct(same_sec, both), 1),
            "base_lot_01_pct": round(pct(c.get(0.1, 0), len(first_lots)), 1),
            "partial_events": tp,
            "baskets": nb,
            "basket_gross_median": round(statistics.median(gv), 3),
            "basket_gross_min": round(gv[0], 2),
            "losing_baskets": len(negb),
            "contract_size_median": round(statistics.median(implied), 4),
        },
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
