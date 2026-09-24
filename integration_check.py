"""End-to-end integration check (headless): exercises the real user workflow.

1. project new/open/save + config export/import
2. calculation consistency across pages (grid vs worst case vs risk)
3. backtest import + analysis
4. behavior verification session: import -> compare -> apply observed rule
5. report exports (JSON/CSV/HTML)
6. set builder -> save -> compare -> export/import
7. assumption registry evidence update
"""
import json
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.config import EAConfig, builtin_presets
from core.symbol_profile import SymbolProfile, AccountSettings
from core.risk import build_risk_summary, RiskThresholds
from core.grid import build_grid_table
from core.worst_case import simulate_worst_case, BOTH_SIDES
from core.backtest_io import parse_backtest_file
from core.backtest_analysis import analyze_backtest
from core.report import save_project, load_project, ProjectData, \
    ReportBundle, export_report_json, export_report_csv, export_report_html
from core.setbuilder import SetStore, evaluate_set, build_combinations, \
    apply_filters, BuilderFilters
from core.sessions import TestSession, SessionStore
from core.mt5_adapters import BehaviorRecord, load_adapter
from core.model_vs_observed import compare_behavior
from core.model_rules import ModelVersionStore
from core.assumptions import AssumptionRegistry, OBSERVED_FROM_TESTING

tmp = tempfile.mkdtemp(prefix="sniper_e2e_")
passed = []


def check(name, cond, detail=""):
    if cond:
        passed.append(name)
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        sys.exit(1)


print("1) project + config IO")
cfg = builtin_presets()["Seller preset - Capital $3000"].copy()
prof = SymbolProfile()
acct = AccountSettings()
proj = ProjectData(capital=3000.0, config=cfg.to_dict(),
                   symbol_profile=prof.to_dict(), account=acct.to_dict())
p_path = os.path.join(tmp, "proj.json")
save_project(p_path, proj)
loaded = load_project(p_path)
check("project roundtrip keeps BaseLot 0.18",
      EAConfig.from_dict(loaded.config).BaseLot == 0.18)
c_path = os.path.join(tmp, "cfg.json")
with open(c_path, "w", encoding="utf-8") as f:
    json.dump(cfg.to_dict(), f)
with open(c_path, encoding="utf-8") as f:
    cfg2 = EAConfig.from_dict(json.load(f))
check("config JSON roundtrip", cfg2.to_dict() == cfg.to_dict())

print("2) calculation consistency (grid vs worst case vs risk)")
rules = ModelVersionStore(os.path.join(tmp, "mv.json")).active_rules()
grid = build_grid_table(cfg, prof, acct, rules, 10, "BUY")
worst = simulate_worst_case(cfg, prof, acct, rules, 3000.0, 45.0, BOTH_SIDES)
risk = build_risk_summary(cfg, prof, acct, rules, 3000.0, RiskThresholds())
# grid at 10 levels == worst case at move 45 (9 steps + level 1)
check("grid levels == worst-case levels at matching move",
      len(grid.rows) == worst.grid_levels == 10)
check("grid cumulative lots == worst-case total buy lots",
      abs(grid.total_lot - (worst.total_lots - 0.18)) < 0.01)  # minus sell hedge
# risk summary uses the same core at its reference move (default 50)
check("risk DD > 0 for a $50 adverse move", risk.estimated_dd_percent > 0)
check("honesty flags always present",
      {"MODEL ASSUMPTION", "EA BEHAVIOR NOT VERIFIED"} <=
      {f.flag for f in risk.flags})

print("3) backtest import + analysis")
csv_path = os.path.join(tmp, "bt.csv")
with open(csv_path, "w", encoding="utf-8") as f:
    f.write("\t".join(["Time", "Deal", "Symbol", "Type", "Direction", "Volume",
                       "Price", "Order", "Commission", "Swap", "Profit",
                       "Balance", "Comment"]) + "\n")
    rows = [
        ["2024.01.02 09:00:00", "1", "XAUUSD", "balance", "", "", "", "", "0", "0", "5000", "5000", ""],
        ["2024.01.02 09:00:01", "2", "XAUUSD", "buy", "in", "0.10", "2050", "1", "0", "0", "0", "5000", ""],
        ["2024.01.02 09:30:00", "3", "XAUUSD", "buy", "in", "0.11", "2045", "2", "0", "0", "0", "5000", "grid"],
        ["2024.01.02 12:00:00", "4", "XAUUSD", "buy", "out", "0.21", "2046", "3", "0", "0", "8.88", "5008.88", "close all"],
    ]
    for r in rows:
        f.write("\t".join(r) + "\n")
summary = parse_backtest_file(csv_path)
analysis = analyze_backtest(summary)
check("backtest net profit parsed", abs(summary.net_profit - 8.88) < 0.01)
check("analyzer found grid depth 2", analysis.max_grid_depth_total == 2)
check("balance curve extracted", len(summary.balance_curve) == 4)

print("4) behavior verification session")
store = SessionStore(os.path.join(tmp, "sessions"))
sess = TestSession.new(symbol="XAUUSD", broker="Demo", account_type="demo",
                       initial_balance=5000.0, config=cfg.to_dict())
behavior_csv = os.path.join(tmp, "behavior.csv")
with open(behavior_csv, "w", encoding="utf-8") as f:
    f.write("timestamp,symbol,event,side,grid_level,lot,price,basket_pl\n")
    f.write("2024.01.02 09:00:01,XAUUSD,NEW_CYCLE,BUY,1,0.18,2050.00,\n")
    f.write("2024.01.02 09:30:00,XAUUSD,ADD_GRID,BUY,2,0.19,2045.20,\n")
    f.write("2024.01.02 09:55:00,XAUUSD,ADD_GRID,BUY,3,0.21,2040.40,\n")
    f.write("2024.01.02 12:00:00,XAUUSD,BASKET_CLOSE,BUY,,,2046.00,8.88\n")
adapter, records = load_adapter(behavior_csv, "csv")
sess.observed_events.extend(r.to_dict() for r in records)
sess.report_files.append("behavior.csv")
store.save(sess)
loaded_sess = store.load(sess.session_id)
records = [BehaviorRecord.from_dict(d) for d in loaded_sess.observed_events]
report = compare_behavior(records, cfg, prof, rules)
# Phase 1: comparator extended 6 -> 10 checks (+ cycle start/end, emergency, resume)
check("comparison produced 10 checks", len(report.checks) == 10)
spacing = next(c for c in report.checks if c.check == "Grid spacing")
check("grid spacing measured near 4.8 (MATCH)",
      spacing.result == "MATCH", spacing.detail)

print("5) report exports")
bundle = ReportBundle(config=cfg, profile=prof, account=acct, capital=3000.0,
                      grid_tables=[grid], worst_cases=[worst],
                      risk_summary=risk, backtest_summary=summary)
export_report_json(bundle, os.path.join(tmp, "r.json"))
export_report_csv(bundle, os.path.join(tmp, "r.csv"))
export_report_html(bundle, os.path.join(tmp, "r.html"))
for fn in ("r.json", "r.csv", "r.html"):
    check(f"{fn} written", os.path.getsize(os.path.join(tmp, fn)) > 500)
with open(os.path.join(tmp, "r.json"), encoding="utf-8") as f:
    d = json.load(f)
check("report json includes assumptions + disclaimer",
      d["assumptions"] and "SIMULATION MODEL" in d["disclaimer"])

print("6) set builder -> store -> export/import")
combos = build_combinations({
    "capital": [3000.0], "grid_step": [4.8, 6.0], "base_lot": [0.18],
    "multiplier": [1.08], "basket_target": [8.88], "max_grid": [10, 20],
})
check("4 combinations generated", len(combos) == 4)
metrics = [evaluate_set(cfg, prof, acct, rules, **{
    "capital": cb["capital"], "grid_step": cb["grid_step"],
    "base_lot": cb["base_lot"], "multiplier": cb["multiplier"],
    "basket_target": cb["basket_target"], "max_grid": int(cb["max_grid"])})
    for cb in combos]
passed_sets = [m for m in metrics if apply_filters(m, BuilderFilters(max_dd_percent=100))[0]]
set_store = SetStore(os.path.join(tmp, "sets.json"))
set_store.save_set("set1", cfg, 3000.0, metrics[0])
set_store.duplicate_set("set1", "set2")
set_store.export_set("set1", os.path.join(tmp, "set1.json"))
set_store.delete_set("set1")
name = set_store.import_set(os.path.join(tmp, "set1.json"))
check("set store CRUD + export/import", set_store.names() == ["set1", "set2"] and name == "set1")

print("7) assumption evidence update")
reg = AssumptionRegistry(os.path.join(tmp, "assump.json"))
reg.set_status("GRID_DIRECTION_ASSUMPTION_001", OBSERVED_FROM_TESTING,
               "demo: grid added only on adverse moves (2026-09-23)")
reg2 = AssumptionRegistry(os.path.join(tmp, "assump.json"))
check("assumption override persists with evidence",
      reg2.status_of("GRID_DIRECTION_ASSUMPTION_001") == OBSERVED_FROM_TESTING
      and "demo" in reg2.get("GRID_DIRECTION_ASSUMPTION_001").evidence)

print()
print(f"INTEGRATION OK — {len(passed)} checks passed")
shutil.rmtree(tmp, ignore_errors=True)
