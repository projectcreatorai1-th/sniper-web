import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
try:
    import core
    from core.config import EAConfig
    from core.symbol_profile import SymbolProfile, AccountSettings
    from core.model_rules import SimulationModelRules
    from core.grid import build_grid_table
    from core.worst_case import simulate_worst_case, BOTH_SIDES
    from core.basket import simulate_basket
    from core.risk import build_risk_summary, RiskThresholds
    from core.validation import validate_config

    cfg = EAConfig(); prof = SymbolProfile(); acct = AccountSettings(); rules = SimulationModelRules()
    t = build_grid_table(cfg, prof, acct, rules, 5, "BUY")
    print("lots:", [r.lot for r in t.rows])
    print("cum:", [r.cumulative_lot for r in t.rows])
    w = simulate_worst_case(cfg, prof, acct, rules, 500.0, 50.0, BOTH_SIDES)
    print("worst:", w.grid_levels, w.total_lots, w.floating_pl, w.drawdown_pct)
    b = simulate_basket(cfg, prof, rules, "BUY", 5)
    print("basket target move:", b.price_move_to_target, "partial move:", b.price_move_to_partial)
    r = build_risk_summary(cfg, prof, acct, rules, 500.0, RiskThresholds())
    print("risk dd:", r.estimated_dd_percent)
    print("flags:", [f.flag for f in r.flags])
    v = validate_config(cfg, prof, acct, 500.0)
    print("validation:", [(i.severity, i.code) for i in v])
    print("SMOKE OK")
except Exception:
    import traceback
    traceback.print_exc()
    sys.exit(1)
