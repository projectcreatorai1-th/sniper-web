"""Tests: project save/load + report exports (Module 12)."""
import json
import os
import unittest

from core.backtest_io import BacktestSummary
from core.basket import simulate_basket
from core.config import EAConfig
from core.grid import build_grid_table
from core.report import (ProjectData, save_project, load_project,
                         ReportBundle, export_report_json, export_report_csv,
                         export_report_html, APP_VERSION)
from core.symbol_profile import SymbolProfile, AccountSettings
from core.worst_case import simulate_worst_case, BOTH_SIDES
from tests import TempDirTestMixin, std_ctx


class TestProjectIO(TempDirTestMixin, unittest.TestCase):
    def test_roundtrip(self):
        data = ProjectData()
        data.capital = 3000.0
        cfg = EAConfig()
        cfg.BaseLot = 0.18
        data.config = cfg.to_dict()
        prof = SymbolProfile(name="BTCUSD", contract_size=1.0,
                             reference_price=60000.0)
        data.symbol_profile = prof.to_dict()
        data.backtest_summary = BacktestSummary(net_profit=99.0).to_dict()

        path = os.path.join(self.tmpdir, "proj.json")
        save_project(path, data)
        loaded = load_project(path)
        self.assertEqual(loaded.capital, 3000.0)
        self.assertEqual(EAConfig.from_dict(loaded.config).BaseLot, 0.18)
        self.assertEqual(SymbolProfile.from_dict(loaded.symbol_profile).name, "BTCUSD")
        self.assertEqual(BacktestSummary.from_dict(loaded.backtest_summary).net_profit, 99.0)

    def test_wrong_schema_rejected(self):
        path = os.path.join(self.tmpdir, "bad.json")
        with open(path, "w") as f:
            json.dump({"schema": "SOMETHING_ELSE"}, f)
        with self.assertRaises(ValueError):
            load_project(path)

    def test_schema_versioned(self):
        d = ProjectData().to_dict()
        self.assertEqual(d["schema"], "SNIPER_PROJECT_V1")
        self.assertEqual(d["app_version"], APP_VERSION)


class TestReportExports(TempDirTestMixin, unittest.TestCase):
    def _bundle(self):
        cfg, prof, acct, rules = std_ctx()
        prof.reference_price = 2000.0
        grid = build_grid_table(cfg, prof, acct, rules, 5, "BUY")
        worst = [simulate_worst_case(cfg, prof, acct, rules, 500.0, 30.0, BOTH_SIDES)]
        baskets = [simulate_basket(cfg, prof, rules, "BUY", 5)]
        bt = BacktestSummary(net_profit=42.0, trades=3)
        return ReportBundle(config=cfg, profile=prof, account=acct, capital=500.0,
                            grid_tables=[grid], worst_cases=worst,
                            basket_sims=baskets, backtest_summary=bt,
                            extra_warnings=["test warning"])

    def test_json_export(self):
        path = os.path.join(self.tmpdir, "r.json")
        export_report_json(self._bundle(), path)
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        self.assertEqual(d["schema"], "SNIPER_REPORT_V1")
        self.assertEqual(len(d["grid_tables"][0]["rows"]), 5)
        self.assertEqual(d["worst_case"][0]["scenario"], "BOTH_SIDES")
        self.assertEqual(d["backtest_summary"]["net_profit"], 42.0)
        self.assertTrue(d["assumptions"])
        self.assertIn("disclaimer", d)

    def test_csv_export(self):
        path = os.path.join(self.tmpdir, "r.csv")
        export_report_csv(self._bundle(), path)
        with open(path, encoding="utf-8-sig") as f:
            content = f.read()
        self.assertIn("ea_config", content)
        self.assertIn("worst_case", content)
        self.assertIn("grid_BUY", content)

    def test_html_export(self):
        from core.risk import build_risk_summary, RiskThresholds
        cfg, prof, acct, rules = std_ctx()
        bundle = self._bundle()
        bundle.risk_summary = build_risk_summary(cfg, prof, acct, rules, 500.0,
                                                 RiskThresholds())
        path = os.path.join(self.tmpdir, "r.html")
        export_report_html(bundle, path)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("EA Configuration", content)
        self.assertIn("Grid Table", content)
        self.assertIn("SIMULATION MODEL", content)
        self.assertIn("Assumptions Used", content)
        self.assertIn("Risk Flags", content)

    def test_bundle_dict_contains_risk(self):
        from core.risk import build_risk_summary, RiskThresholds
        cfg, prof, acct, rules = std_ctx()
        b = self._bundle()
        b.risk_summary = build_risk_summary(cfg, prof, acct, rules, 500.0,
                                            RiskThresholds())
        d = b.to_dict()
        self.assertIsNotNone(d["risk_summary"])
        self.assertTrue(d["risk_summary"]["flags"])


if __name__ == "__main__":
    unittest.main()
