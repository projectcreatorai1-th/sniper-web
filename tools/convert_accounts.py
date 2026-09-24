"""Convert 4 MT5 xlsx history files → clean behavior CSVs for import.

Reads each xlsx, extracts GOLDmicro positions, groups them into cycles by
close-time, and outputs proper behavior event CSVs (one per account).
"""
import os
import sys
import csv
import openpyxl
from collections import defaultdict

DESKTOP = r"C:\Users\BANK\Desktop"
ACCOUNTS = ["335504856", "391629843", "411173797", "440192945"]
OUT_DIR = os.path.join(os.environ.get("TEMP", ""), "sniper_accounts")
os.makedirs(OUT_DIR, exist_ok=True)


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
    return str(v).strip() if v is not None else ""


def convert_account(filepath):
    wb = openpyxl.load_workbook(filepath, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    positions = []
    for i, row in enumerate(rows):
        if i < 7:
            continue
        sym = safe_str(row[2])
        if sym != "GOLDmicro":
            continue
        vol = safe_float(row[4])
        if vol <= 0:
            continue  # skip balance ops
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
    wb.close()
    return positions


def group_into_cycles(positions):
    """Group positions into cycles: a cycle = all positions that share
    the same close_time (basket close = they all close together)."""
    close_groups = defaultdict(list)
    for p in positions:
        if p["close_time"]:
            close_groups[p["close_time"]].append(p)

    cycles = []
    for close_time, members in sorted(close_groups.items()):
        members.sort(key=lambda x: x["open_time"])
        cycles.append({"close_time": close_time, "members": members})
    return cycles


def cycle_to_events(cycle, cycle_id):
    """Convert one cycle's positions into behavior events."""
    events = []
    members = cycle["members"]
    if not members:
        return events

    # Separate by side
    buys = [m for m in members if m["side"] == "BUY"]
    sells = [m for m in members if m["side"] == "SELL"]
    buys.sort(key=lambda x: x["open_time"])
    sells.sort(key=lambda x: x["open_time"])

    total_pl = sum(m["profit"] for m in members)
    total_comm = sum(m["commission"] for m in members)
    total_swap = sum(m["swap"] for m in members)

    # Emit events sorted by open_time
    all_events = []
    for i, b in enumerate(buys, start=1):
        all_events.append((b["open_time"], "open_position" if i == 1 else "add_grid",
                           "BUY", i, b))
    for i, s in enumerate(sells, start=1):
        all_events.append((s["open_time"], "open_position" if i == 1 else "add_grid",
                           "SELL", i, s))
    all_events.sort(key=lambda x: x[0])

    cum_lots = 0.0
    for ts, event, side, level, p in all_events:
        cum_lots = round(cum_lots + p["volume"], 4)
        events.append({
            "Time": ts, "Event": event, "Side": side, "Level": level,
            "Lot": p["volume"], "Price": p["open_price"],
            "TotalLots": cum_lots, "PositionCount": len(all_events[:all_events.index(
                (ts, event, side, level, p)) + 1]),
            "BasketPL": "", "Commission": p["commission"], "Swap": p["swap"],
            "_cycle_id": cycle_id,
        })

    # Basket close event
    events.append({
        "Time": cycle["close_time"], "Event": "basket_close", "Side": "",
        "Level": "", "Lot": round(sum(m["volume"] for m in members), 4),
        "Price": members[0]["close_price"] if members else "",
        "TotalLots": 0, "PositionCount": 0,
        "BasketPL": round(total_pl, 2),
        "Commission": round(total_comm, 2), "Swap": round(total_swap, 2),
        "_cycle_id": cycle_id,
    })
    return events


def main():
    all_stats = {}
    for acct in ACCOUNTS:
        filepath = os.path.join(DESKTOP, f"ReportHistory-{acct}.xlsx")
        if not os.path.exists(filepath):
            print(f"SKIP {acct}: file not found")
            continue

        print(f"\n{'='*60}")
        print(f"Processing account {acct}...")
        positions = convert_account(filepath)
        print(f"  GOLDmicro positions (vol>0): {len(positions)}")
        buys = [p for p in positions if p["side"] == "BUY"]
        sells = [p for p in positions if p["side"] == "SELL"]
        print(f"  Buys: {len(buys)} | Sells: {len(sells)}")

        cycles = group_into_cycles(positions)
        print(f"  Basket cycles (close groups): {len(cycles)}")

        all_events = []
        for ci, cyc in enumerate(cycles, start=1):
            all_events.extend(cycle_to_events(cyc, ci))
        all_events.sort(key=lambda x: x["Time"])

        # Write CSV
        out_path = os.path.join(OUT_DIR, f"acct_{acct}.csv")
        fields = ["Time", "Event", "Side", "Level", "Lot", "Price",
                  "TotalLots", "PositionCount", "BasketPL", "Commission", "Swap"]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(all_events)

        # Stats
        lot_seqs = []
        for cyc in cycles:
            side_lots = defaultdict(list)
            for m in cyc["members"]:
                side_lots[m["side"]].append(m["volume"])
            for side, lots in side_lots.items():
                if len(lots) >= 2:
                    lot_seqs.append(lots)

        # Analyze lot progression
        if lot_seqs:
            # Check geometric: lot[i+1]/lot[i] ≈ multiplier
            ratios = []
            for seq in lot_seqs[:100]:
                for a, b in zip(seq, seq[1:]):
                    if a > 0:
                        ratios.append(b / a)
            if ratios:
                avg_mult = sum(ratios) / len(ratios)
                # Check grid spacing
                spacings = []
                for cyc in cycles[:50]:
                    for side in ("BUY", "SELL"):
                        side_pos = sorted([m for m in cyc["members"]
                                           if m["side"] == side],
                                          key=lambda x: x["open_time"])
                        for a, b in zip(side_pos, side_pos[1:]):
                            spacings.append(abs(b["open_price"] - a["open_price"]))
                avg_spacing = sum(spacings) / len(spacings) if spacings else 0

                all_stats[acct] = {
                    "positions": len(positions), "buys": len(buys),
                    "sells": len(sells), "cycles": len(cycles),
                    "avg_multiplier": round(avg_mult, 4),
                    "avg_grid_spacing": round(avg_spacing, 2),
                    "csv": out_path,
                }
                print(f"  Avg multiplier: {avg_mult:.4f}")
                print(f"  Avg grid spacing: {avg_spacing:.2f} USD")

        print(f"  CSV: {out_path} ({os.path.getsize(out_path)} bytes)")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY ACROSS ALL ACCOUNTS:")
    print(f"{'='*60}")
    for acct, s in all_stats.items():
        print(f"  {acct}: {s['positions']} pos, {s['cycles']} cycles, "
              f"mult={s['avg_multiplier']}, spacing={s['avg_grid_spacing']}")


if __name__ == "__main__":
    main()
