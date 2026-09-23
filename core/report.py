"""Export / Report (Module 12) and whole-project save-load.

Exports JSON / CSV / HTML. PDF is intentionally NOT produced: the Python
standard library has no PDF writer and adding a dependency is unnecessary -
a self-contained HTML report (printable to PDF from any browser) covers the
need.

Project files bundle: config, symbol profile, account, thresholds, capital,
model rules version, backtest summary and sets - one JSON, versioned schema.
"""
from __future__ import annotations

import csv
import html as html_mod
import io
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional

from core.backtest_io import BacktestSummary
from core.config import EAConfig
from core.grid import GridTable
from core.model_rules import SimulationModelRules
from core.risk import RiskSummary
from core.symbol_profile import SymbolProfile, AccountSettings
from core.worst_case import WorstCaseResult
from core.basket import BasketSimResult

PROJECT_SCHEMA = "SNIPER_PROJECT_V1"
APP_VERSION = "1.0.0"


@dataclass
class ProjectData:
    """Everything the app persists as one project file."""
    capital: float = 500.0
    config: dict = field(default_factory=lambda: EAConfig().to_dict())
    symbol_profile: dict = field(default_factory=lambda: SymbolProfile().to_dict())
    account: dict = field(default_factory=lambda: AccountSettings().to_dict())
    risk_thresholds: dict = field(default_factory=dict)
    model_rules: dict = field(default_factory=lambda: SimulationModelRules().to_dict())
    backtest_summary: Optional[dict] = None
    saved_sets_names: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = PROJECT_SCHEMA
        d["app_version"] = APP_VERSION
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectData":
        p = cls()
        for k, v in d.items():
            if k in ("schema", "app_version"):
                continue
            if hasattr(p, k) and v is not None:
                setattr(p, k, v)
        return p


def save_project(path: str, data: ProjectData) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)


def load_project(path: str) -> ProjectData:
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    schema = d.get("schema")
    if schema != PROJECT_SCHEMA:
        raise ValueError(f"unsupported project schema: {schema}")
    return ProjectData.from_dict(d)


# ---------------------------------------------------------------------------
# Report bundle
# ---------------------------------------------------------------------------
@dataclass
class ReportBundle:
    config: EAConfig
    profile: SymbolProfile
    account: AccountSettings
    capital: float
    grid_tables: List[GridTable] = field(default_factory=list)
    worst_cases: List[WorstCaseResult] = field(default_factory=list)
    risk_summary: Optional[RiskSummary] = None
    basket_sims: List[BasketSimResult] = field(default_factory=list)
    backtest_summary: Optional[BacktestSummary] = None
    extra_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        from core.assumptions import default_registry
        reg = default_registry()
        assumption_ids: List[str] = []
        for wc in self.worst_cases:
            assumption_ids += wc.assumptions
        for gt in self.grid_tables:
            assumption_ids += gt.assumptions
        if self.risk_summary:
            assumption_ids += self.risk_summary.assumptions
        assumption_ids = list(dict.fromkeys(assumption_ids))
        flag_warnings = []
        if self.risk_summary is not None:
            flag_warnings = [f"{f.flag}: {f.detail}" for f in self.risk_summary.flags]
        return {
            "schema": "SNIPER_REPORT_V1",
            "app_version": APP_VERSION,
            "generated": _now(),
            "disclaimer": (
                "SIMULATION MODEL - not verified internal EA formula. "
                "This analyzer is a calculator/simulator only; it does not "
                "trade and does not guarantee profits."),
            "ea_configuration": self.config.to_dict(),
            "simulation_parameters": {
                "capital": self.capital,
                "symbol_profile": self.profile.to_dict(),
                "account": self.account.to_dict(),
            },
            "grid_tables": [{ "side": gt.side, "start_price": gt.start_price,
                              "rows": gt.to_dicts(),
                              "total_lot": round(gt.total_lot, 4),
                              "total_margin": round(gt.total_margin, 2),
                              "assumptions": gt.assumptions}
                            for gt in self.grid_tables],
            "worst_case": [wc.to_dict() for wc in self.worst_cases],
            "risk_summary": self.risk_summary.to_dict() if self.risk_summary else None,
            "basket_simulation": [bs.to_dict() for bs in self.basket_sims],
            "backtest_summary": self.backtest_summary.to_dict() if self.backtest_summary else None,
            "assumptions": reg.describe(assumption_ids),
            "warnings": flag_warnings + self.extra_warnings,
        }


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


def export_report_json(bundle: ReportBundle, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle.to_dict(), f, ensure_ascii=False, indent=2)


def export_report_csv(bundle: ReportBundle, path: str) -> None:
    """Grid table(s) + summary sections in one CSV (sections separated by
    blank lines and a section column)."""
    rows: List[List] = []
    d = bundle.to_dict()
    rows.append(["SECTION", "KEY", "VALUE", "EXTRA"])
    for k, v in d["simulation_parameters"]["symbol_profile"].items():
        rows.append(["symbol_profile", k, v, ""])
    rows.append(["capital", "capital", bundle.capital, ""])
    for k, v in d["ea_configuration"].items():
        if k != "schema":
            rows.append(["ea_config", k, v, ""])
    for gt in d["grid_tables"]:
        for r in gt["rows"]:
            rows.append([f"grid_{gt['side']}", f"level_{r['level']}",
                         r["lot"], json.dumps(r, ensure_ascii=False)])
    for wc in d["worst_case"]:
        rows.append(["worst_case", wc["scenario"],
                     wc["floating_pl"], json.dumps(wc, ensure_ascii=False)])
    if d["risk_summary"]:
        for k, v in d["risk_summary"].items():
            if k not in ("flags", "assumptions"):
                rows.append(["risk", k, v, ""])
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)


_CSS = """
body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#1a1a2e;background:#fafafa}
h1{border-bottom:3px solid #c9a227;padding-bottom:8px}
h2{color:#16213e;margin-top:28px;border-bottom:1px solid #ddd;padding-bottom:4px}
table{border-collapse:collapse;margin:10px 0;font-size:13px}
th,td{border:1px solid #ccc;padding:4px 8px;text-align:right}
th{background:#16213e;color:#fff;text-align:left}
tr:nth-child(even){background:#f0f0f5}
.warn{color:#a33}.ok{color:#1a7a2e}.unk{color:#b8860b}
.banner{background:#fff3cd;border:1px solid #e0c46c;padding:10px;border-radius:6px}
.flags li{margin:2px 0}
.small{color:#666;font-size:12px}
"""


def export_report_html(bundle: ReportBundle, path: str) -> None:
    d = bundle.to_dict()
    parts: List[str] = []
    esc = html_mod.escape

    parts.append("<html><head><meta charset='utf-8'>")
    parts.append(f"<title>SNIPER CashFlow Analyzer Report</title><style>{_CSS}</style></head><body>")
    parts.append("<h1>SNIPER CashFlow Analyzer — Report</h1>")
    parts.append(f"<p class='small'>Generated {esc(d['generated'])} · App v{d['app_version']}</p>")
    parts.append(f"<div class='banner'><b>{esc(d['disclaimer'])}</b></div>")

    # EA configuration
    parts.append("<h2>EA Configuration (SNIPER_V1_68_CONFIG)</h2><table><tr><th>Parameter</th><th>Value</th></tr>")
    for k, v in d["ea_configuration"].items():
        if k != "schema":
            parts.append(f"<tr><td>{esc(str(k))}</td><td>{esc(str(v))}</td></tr>")
    parts.append("</table>")

    # Simulation parameters
    parts.append("<h2>Simulation Parameters</h2><table><tr><th>Item</th><th>Value</th></tr>")
    parts.append(f"<tr><td>Capital</td><td>{bundle.capital}</td></tr>")
    for k, v in d["simulation_parameters"]["symbol_profile"].items():
        parts.append(f"<tr><td>{esc(k)}</td><td>{esc(str(v))}</td></tr>")
    for k, v in d["simulation_parameters"]["account"].items():
        parts.append(f"<tr><td>account.{esc(k)}</td><td>{esc(str(v))}</td></tr>")
    parts.append("</table>")

    # Grid tables
    for gt in d["grid_tables"]:
        parts.append(f"<h2>Grid Table — {esc(gt['side'])} (start {gt['start_price']})</h2>")
        parts.append("<table><tr><th>Level</th><th>Distance</th><th>Entry</th><th>Lot</th>"
                     "<th>Cum. Lot</th><th>Exposure</th><th>Margin</th><th>Floating P/L @ open</th></tr>")
        for r in gt["rows"]:
            parts.append(
                f"<tr><td>{r['level']}</td><td>{r['distance_from_start']}</td>"
                f"<td>{r['entry_price']}</td><td>{r['lot']}</td><td>{r['cumulative_lot']}</td>"
                f"<td>{r['exposure']}</td><td>{r['margin']}</td><td>{r['floating_pl_at_open']}</td></tr>")
        parts.append("</table>")

    # Worst case
    if d["worst_case"]:
        parts.append("<h2>Worst Case Simulation</h2>")
        parts.append("<table><tr><th>Scenario</th><th>Move</th><th>Levels</th><th>Total Lots</th>"
                     "<th>Floating P/L</th><th>Margin</th><th>Equity</th><th>DD %</th>"
                     "<th>Margin Level %</th></tr>")
        for wc in d["worst_case"]:
            mlvl = wc["margin_level_pct"] if wc["margin_level_pct"] is not None else "N/A"
            parts.append(
                f"<tr><td>{esc(wc['scenario'])}</td><td>{wc['adverse_move']}</td>"
                f"<td>{wc['grid_levels']}</td><td>{wc['total_lots']}</td>"
                f"<td class='warn'>{wc['floating_pl']}</td><td>{wc['estimated_margin_used']}</td>"
                f"<td>{wc['equity']}</td><td class='warn'>{wc['drawdown_pct']}</td><td>{mlvl}</td></tr>")
        parts.append("</table>")

    # Risk summary
    if d["risk_summary"]:
        rs = d["risk_summary"]
        parts.append("<h2>Risk Summary</h2><table><tr><th>Metric</th><th>Value</th></tr>")
        for k, v in rs.items():
            if k in ("flags", "assumptions"):
                continue
            parts.append(f"<tr><td>{esc(k)}</td><td>{esc(str(v))}</td></tr>")
        parts.append("</table><h3>Risk Flags</h3><ul class='flags'>")
        for fl in rs["flags"]:
            cls = "warn" if fl["severity"] == "warning" else "unk"
            parts.append(f"<li class='{cls}'><b>{esc(fl['flag'])}</b> — {esc(fl['detail'])}</li>")
        parts.append("</ul>")

    # Basket sims
    if d["basket_simulation"]:
        parts.append("<h2>Basket / Partial Close Simulation</h2><table><tr><th>Side</th>"
                     "<th>Levels</th><th>Total Lots</th><th>Basket P/L</th><th>Partial Trigger</th>"
                     "<th>Basket Target</th><th>Move to Target</th></tr>")
        for b in d["basket_simulation"]:
            parts.append(
                f"<tr><td>{esc(b['side'])}</td><td>{b['levels']}</td><td>{b['total_lots']}</td>"
                f"<td>{b['current_basket_pl']}</td><td>{b['partial_trigger']}</td>"
                f"<td>{b['basket_target']}</td><td>{b['price_move_to_target']}</td></tr>")
        parts.append("</table>")

    # Backtest
    if d["backtest_summary"]:
        bs = d["backtest_summary"]
        parts.append("<h2>Backtest Summary (imported)</h2><table><tr><th>Metric</th><th>Value</th></tr>")
        for k, v in bs.items():
            if k in ("deals", "balance_curve", "schema"):
                continue
            parts.append(f"<tr><td>{esc(k)}</td><td>{esc(str(v) if v is not None else 'N/A')}</td></tr>")
        parts.append("</table>")
    else:
        parts.append("<h2>Backtest Summary</h2><p>No backtest imported.</p>")

    # Assumptions
    parts.append("<h2>Assumptions Used</h2><table><tr><th>ID</th><th>Status</th><th>Title</th></tr>")
    for a in d["assumptions"]:
        cls = {"MODEL_ASSUMPTION": "unk", "UNKNOWN": "unk",
               "VERIFIED_FROM_DOCUMENTATION": "ok"}.get(a["status"], "")
        parts.append(f"<tr><td>{esc(a['assumption_id'])}</td>"
                     f"<td class='{cls}'>{esc(a['status'])}</td><td>{esc(a['title'])}</td></tr>")
    parts.append("</table>")

    # Warnings
    parts.append("<h2>Warnings</h2><ul class='flags'>")
    for w in d["warnings"]:
        parts.append(f"<li class='warn'>{esc(w)}</li>")
    if not d["warnings"]:
        parts.append("<li>No warnings.</li>")
    parts.append("</ul>")

    parts.append("<p class='small'>Analyzer / Calculator / Simulator only — no trading commands, "
                 "no account modifications, no profit guarantee.</p>")
    parts.append("</body></html>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(parts))
