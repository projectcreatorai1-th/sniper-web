"""Runtime verification payloads (run: python tools/make_check_payloads.py)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import EAConfig
from core.symbol_profile import AccountSettings, SymbolProfile

BASE = os.path.join(os.environ.get("TEMP", "."), "sniper_web_check")
os.makedirs(BASE, exist_ok=True)

std = {"config": EAConfig().to_dict(),
       "symbol_profile": SymbolProfile().to_dict(),
       "account": AccountSettings().to_dict()}


def w(name, obj):
    with open(os.path.join(BASE, name), "w", encoding="utf-8") as f:
        json.dump(obj, f)


w("validate.json", dict(std, capital=500.0))
bad = json.loads(json.dumps(std))
bad["config"]["BaseLot"] = 0.005
w("validate_warn.json", dict(bad, capital=500.0))
w("grid.json", dict(std, levels=11, side="BUY", capital=500.0))
w("worst.json", dict(std, capital=500.0, moves=[10, 30, 50, 100]))
w("risk.json", dict(std, capital=500.0))
w("basket.json", dict(std, side="BUY", levels=5))
w("setbuilder.json", dict(std, capital=500.0, values={
    "grid_step": [5.0, 8.0], "multiplier": [1.08, 1.10, 1.20], "base_lot": [0.1]},
    filters={"max_dd_percent": 700.0}))
w("report.json", dict(std, format="json", capital=500.0, levels=11, side="BUY",
                      moves=[10, 50], basket_levels=5))
csv_text = (
    "Time\tDeal\tSymbol\tType\tDirection\tVolume\tPrice\tOrder\tCommission\tSwap\tProfit\tBalance\tComment\n"
    "2024.01.02 10:00:00\t1\t\tbalance\t\t0\t0\t0\t0\t0\t500\t500\t\n"
    "2024.01.02 10:05:00\t2\tXAUUSD\tbuy\tin\t0.1\t2050.0\t1\t0\t0\t0\t500\t500\t\n"
    "2024.01.02 11:00:00\t3\tXAUUSD\tsell\tout\t0.1\t2052.0\t2\t-0.2\t0\t19.8\t519.6\tt/p\n")
with open(os.path.join(BASE, "deals.csv"), "w", encoding="utf-8") as f:
    f.write(csv_text)
with open(os.path.join(BASE, "evil.py"), "w", encoding="utf-8") as f:
    f.write("print(1)\n")
print("payloads ready at", BASE)
