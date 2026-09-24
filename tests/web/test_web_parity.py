"""PARITY TESTS — Desktop/Core result must equal Web/API result.

Every case calls the core function directly (exactly what the desktop GUI
calls) and then the web API with identical inputs, then asserts exact
equality of the serialized results. No tolerance is used: the web backend
calls the very same core functions, so the values are deterministic.
"""
import unittest

from core.basket import simulate_basket
from core.config import EAConfig, builtin_presets
from core.grid import build_grid_table
from core.report import ReportBundle
from core.risk import RiskThresholds, build_risk_summary
from core.setbuilder import BuilderFilters, apply_filters, build_combinations, evaluate_set
from core.symbol_profile import AccountSettings, SymbolProfile
from core.model_rules import SimulationModelRules
from core.validation import INFO, WARNING, validate_config
from core.worst_case import (
    BUY_ADVERSE,
    SELL_ADVERSE,
    BOTH_SIDES,
    SCENARIOS,
    simulate_moves,
    simulate_worst_case,
)

from webhelpers import call_app, std_body
from tests import std_ctx


def grid_dict_from_table(table):
    """The exact serialization contract the API uses for a GridTable."""
    return {
        "side": table.side,
        "start_price": round(table.start_price, 6),
        "grid_step": table.grid_step,
        "rows": table.to_dicts(),
        "total_lot": round(table.total_lot, 4),
        "total_exposure": round(table.total_exposure, 2),
        "total_margin": round(table.total_margin, 2),
        "final_floating_pl": round(table.final_floating_pl, 2),
        "avg_entry": round(table.avg_entry, 6) if table.avg_entry is not None else None,
        "assumptions": table.assumptions,
    }


class GridParity(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()
        self.prof.reference_price = 2000.0

    def _parity(self, levels, side):
        table = build_grid_table(self.cfg, self.prof, self.acct, self.rules, levels, side)
        status, _, payload = call_app("POST", "/api/grid/calculate",
                                      std_body(levels=levels, side=side, capital=500.0))
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["data"]["grid"], grid_dict_from_table(table))

    def test_grid_5_levels_buy(self):
        self._parity(5, "BUY")

    def test_grid_11_levels_buy(self):
        self._parity(11, "BUY")

    def test_grid_11_levels_sell(self):
        self._parity(11, "SELL")

    def test_grid_5_levels_sell(self):
        self._parity(5, "SELL")

    def test_grid_golden_lot_sequence(self):
        """Regression pin through the API: BaseLot .1 / mult 1.1 / step 5."""
        status, _, payload = call_app("POST", "/api/grid/calculate",
                                      std_body(levels=10, side="BUY", capital=500.0))
        lots = [r["lot"] for r in payload["data"]["grid"]["rows"]]
        self.assertEqual(lots, [0.1, 0.11, 0.12, 0.13, 0.14,
                                0.16, 0.17, 0.19, 0.21, 0.23])
        cums = [r["cumulative_lot"] for r in payload["data"]["grid"]["rows"][:5]]
        self.assertEqual(cums, [0.1, 0.21, 0.33, 0.46, 0.60])

    def test_grid_level3_floating_matches_regression(self):
        status, _, payload = call_app("POST", "/api/grid/calculate",
                                      std_body(levels=3, side="BUY", capital=500.0))
        row = payload["data"]["grid"]["rows"][2]
        self.assertAlmostEqual(row["floating_pl_at_open"], -155.0)
        self.assertAlmostEqual(row["margin"], 0.33 * 100 * 1990.0 / 500.0)


class WorstCaseParity(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()
        self.prof.reference_price = 2000.0

    def test_parity_all_scenarios_move_50(self):
        move = 50.0
        expected = [simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                        500.0, move, sc).to_dict() for sc in SCENARIOS]
        status, _, payload = call_app(
            "POST", "/api/worst-case/simulate",
            std_body(capital=500.0, moves=[move], scenarios=list(SCENARIOS)))
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["data"]["results"], expected)

    def test_parity_multiple_moves(self):
        moves = [10.0, 30.0, 50.0, 100.0]
        expected = [simulate_worst_case(self.cfg, self.prof, self.acct, self.rules,
                                        500.0, mv, sc).to_dict()
                    for mv in moves for sc in (BUY_ADVERSE, SELL_ADVERSE, BOTH_SIDES)]
        status, _, payload = call_app("POST", "/api/worst-case/simulate",
                                      std_body(capital=500.0, moves=moves))
        self.assertEqual(payload["data"]["results"], expected)

    def test_golden_both_sides_50(self):
        """Regression pin through the API: 11 levels / 1.91 lots / -3200 / 640% (floor, MC-001)."""
        status, _, payload = call_app("POST", "/api/worst-case/simulate",
                                      std_body(capital=500.0, moves=[50.0],
                                               scenarios=[BOTH_SIDES]))
        r = payload["data"]["results"][0]
        self.assertEqual(r["grid_levels"], 11)
        self.assertAlmostEqual(r["total_lots"], 1.91)
        self.assertAlmostEqual(r["floating_pl"], -3200.0)
        self.assertAlmostEqual(r["drawdown_pct"], 640.0)

    def test_golden_buy_adverse_10(self):
        status, _, payload = call_app("POST", "/api/worst-case/simulate",
                                      std_body(capital=500.0, moves=[10.0],
                                               scenarios=[BUY_ADVERSE]))
        r = payload["data"]["results"][0]
        self.assertEqual(r["grid_levels"], 3)
        self.assertAlmostEqual(r["total_lots"], 0.33)
        self.assertAlmostEqual(r["floating_pl"], -155.0)
        self.assertAlmostEqual(r["equity"], 345.0)
        self.assertAlmostEqual(r["drawdown_pct"], 31.0)


class BasketParity(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_parity_default_basket_buy_5(self):
        expected = simulate_basket(self.cfg, self.prof, self.rules, "BUY", 5).to_dict()
        status, _, payload = call_app("POST", "/api/basket/simulate",
                                      std_body(side="BUY", levels=5))
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["data"]["basket"], expected)
        # regression pin: move-to-target + partial numbers
        b = payload["data"]["basket"]
        self.assertAlmostEqual(b["price_move_to_target"], 9.19466667, places=6)
        self.assertAlmostEqual(b["partial_realized_pl"], 1.0)
        self.assertAlmostEqual(b["partial_close_volume"], 0.3)

    def test_parity_partial_custom_config(self):
        cfg = EAConfig()
        cfg.ProfitPartialPercent = 30.0
        cfg.ProfitPartialOnlyOnce = False
        expected = simulate_basket(cfg, self.prof, self.rules, "SELL", 8,
                                   partial_already_done=True).to_dict()
        status, _, payload = call_app("POST", "/api/basket/simulate",
                                      std_body(side="SELL", levels=8,
                                               partial_already_done=True,
                                               config=cfg.to_dict()))
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["data"]["basket"], expected)


class RiskParity(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_parity_default_thresholds(self):
        expected = build_risk_summary(self.cfg, self.prof, self.acct, self.rules,
                                      500.0, RiskThresholds()).to_dict()
        status, _, payload = call_app("POST", "/api/risk/calculate",
                                      std_body(capital=500.0))
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["data"]["summary"], expected)

    def test_parity_custom_thresholds(self):
        th = RiskThresholds(high_dd_percent=10.0, reference_adverse_move_usd=30.0,
                            max_simulated_grid_levels=25)
        expected = build_risk_summary(self.cfg, self.prof, self.acct, self.rules,
                                      500.0, th, "SELL").to_dict()
        status, _, payload = call_app("POST", "/api/risk/calculate",
                                      std_body(capital=500.0,
                                               thresholds=th.to_dict(), side="SELL"))
        self.assertEqual(payload["data"]["summary"], expected)
        # honesty flags always present
        flags = {f["flag"] for f in payload["data"]["summary"]["flags"]}
        self.assertIn("MODEL ASSUMPTION", flags)
        self.assertIn("EA BEHAVIOR NOT VERIFIED", flags)


class PresetParity(unittest.TestCase):
    """Both seller presets through every major endpoint."""

    def setUp(self):
        self.prof, self.acct, self.rules = SymbolProfile(), AccountSettings(), SimulationModelRules()

    def test_presets(self):
        for name, cfg in builtin_presets().items():
            with self.subTest(preset=name):
                body = std_body(config=cfg.to_dict(), capital=500.0)
                # grid parity
                table = build_grid_table(cfg, self.prof, self.acct, self.rules, 11, "BUY")
                status, _, payload = call_app("POST", "/api/grid/calculate",
                                              dict(body, levels=11, side="BUY"))
                self.assertEqual(status, 200, payload)
                self.assertEqual(payload["data"]["grid"], grid_dict_from_table(table))
                # worst-case parity
                expected_wc = simulate_worst_case(cfg, self.prof, self.acct, self.rules,
                                                  500.0, 50.0, BOTH_SIDES).to_dict()
                status, _, payload = call_app("POST", "/api/worst-case/simulate",
                                              dict(body, moves=[50.0], scenarios=[BOTH_SIDES]))
                self.assertEqual(payload["data"]["results"], [expected_wc])
                # risk parity
                expected_risk = build_risk_summary(cfg, self.prof, self.acct, self.rules,
                                                   500.0, RiskThresholds()).to_dict()
                status, _, payload = call_app("POST", "/api/risk/calculate", body)
                self.assertEqual(payload["data"]["summary"], expected_risk)

    def test_preset_3000_lot_pin(self):
        cfg = builtin_presets()["Seller preset - Capital $3000"]
        status, _, payload = call_app("POST", "/api/grid/calculate",
                                      std_body(config=cfg.to_dict(), levels=3,
                                               side="BUY", capital=3000.0))
        lots = [r["lot"] for r in payload["data"]["grid"]["rows"]]
        self.assertEqual(lots, [0.18, 0.19, 0.20])


class ValidationParity(unittest.TestCase):
    """Broker-constraint and config validation: core issues == API issues."""

    def setUp(self):
        self.prof, self.acct = SymbolProfile(), AccountSettings()

    def _issues_equal(self, cfg, capital=0.0, profile=None, account=None):
        expected = [i.to_dict() for i in validate_config(
            cfg, profile or self.prof, account or self.acct, capital)]
        status, _, payload = call_app("POST", "/api/validate",
                                      std_body(config=cfg.to_dict(), capital=capital,
                                               symbol_profile=(profile or self.prof).to_dict(),
                                               account=(account or self.acct).to_dict()))
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["data"]["issues"], expected)
        return payload["data"]

    def test_default_config_issues(self):
        data = self._issues_equal(EAConfig(), capital=500.0)
        self.assertFalse(data["has_errors"])

    def test_baselt_below_broker_min(self):
        cfg = EAConfig()
        cfg.BaseLot = 0.005
        data = self._issues_equal(cfg)
        codes = [i["code"] for i in data["issues"]]
        self.assertIn("BASELOT_BELOW_MIN", codes)
        self.assertIn("BASELOT_NOT_ON_STEP", codes)

    def test_baselt_above_broker_max(self):
        cfg = EAConfig()
        cfg.BaseLot = 200.0
        data = self._issues_equal(cfg)
        self.assertTrue(data["has_errors"])
        self.assertIn("BASELOT_ABOVE_MAX", [i["code"] for i in data["issues"]])
        # calc endpoint must refuse an ERROR-severity config
        status, _, payload = call_app("POST", "/api/grid/calculate",
                                      std_body(config=cfg.to_dict(), levels=5,
                                               side="BUY", capital=500.0))
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["code"], "CONFIG_INVALID")

    def test_leverage_zero(self):
        acct = AccountSettings(leverage=0)
        data = self._issues_equal(EAConfig(), account=acct)
        self.assertTrue(data["has_errors"])

    def test_bad_time_field(self):
        cfg = EAConfig()
        cfg.FridayCloseAllThaiTime = "25:99"
        data = self._issues_equal(cfg)
        self.assertTrue(data["has_errors"])
        self.assertIn("TIME_FORMAT", [i["code"] for i in data["issues"]])

    def test_insufficient_capital(self):
        data = self._issues_equal(EAConfig(), capital=10.0)
        self.assertTrue(data["has_errors"])
        self.assertIn("INSUFFICIENT_CAPITAL", [i["code"] for i in data["issues"]])


class SetBuilderParity(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_spec_example_combinations(self):
        """Spec example: GridStep 5/8 x Multiplier 1.08/1.10/1.20 (spec values)."""
        values = {
            "capital": [500.0],
            "grid_step": [5.0, 8.0],
            "base_lot": [0.1],
            "multiplier": [1.08, 1.10, 1.20],
            "basket_target": [1.68],
            "max_grid": [11],
        }
        filters = BuilderFilters(max_dd_percent=700.0)
        combos = build_combinations(values)
        self.assertEqual(len(combos), 6)

        status, _, payload = call_app(
            "POST", "/api/set-builder/generate",
            std_body(values=values, filters=filters.to_dict()))
        self.assertEqual(status, 200, payload)
        rows = payload["data"]["combinations"]
        self.assertEqual(len(rows), 6)
        for combo, row in zip(combos, rows):
            metrics = evaluate_set(
                self.cfg, self.prof, self.acct, self.rules,
                capital=combo["capital"], grid_step=combo["grid_step"],
                base_lot=combo["base_lot"], multiplier=combo["multiplier"],
                basket_target=combo["basket_target"], max_grid=int(combo["max_grid"]))
            self.assertEqual(row["metrics"], metrics.to_dict())
            passed, reasons = apply_filters(metrics, filters)
            self.assertEqual(row["passed"], passed)
            self.assertEqual(row["filter_reasons"], reasons)
        # generation order preserved (no ranking)
        steps = [r["grid_step"] for r in rows]
        self.assertEqual(steps, sorted(steps))

    def test_filter_excludes_row(self):
        values = {
            "capital": [500.0], "grid_step": [5.0], "base_lot": [0.1],
            "multiplier": [1.1], "basket_target": [1.68], "max_grid": [11],
        }
        status, _, payload = call_app(
            "POST", "/api/set-builder/generate",
            std_body(values=values, filters={"max_dd_percent": 10.0}))
        rows = payload["data"]["combinations"]
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["passed"])
        self.assertTrue(rows[0]["filter_reasons"])


class ReportParity(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_report_json_equals_core_bundle(self):
        moves = [10.0, 50.0]
        levels, side = 11, "BUY"
        bundle = ReportBundle(
            config=self.cfg, profile=self.prof, account=self.acct, capital=500.0,
            grid_tables=[build_grid_table(self.cfg, self.prof, self.acct, self.rules,
                                          levels, side)],
            worst_cases=simulate_moves(self.cfg, self.prof, self.acct, self.rules,
                                       500.0, moves),
            risk_summary=build_risk_summary(self.cfg, self.prof, self.acct, self.rules,
                                            500.0, RiskThresholds()),
            basket_sims=[simulate_basket(self.cfg, self.prof, self.rules, side, 5)],
        )
        expected = bundle.to_dict()
        val_warnings = [
            f"{i.severity}: {i.message}" for i in validate_config(
                self.cfg, self.prof, self.acct, 500.0)
            if i.severity in (WARNING, INFO)]
        expected["warnings"] = expected["warnings"] + val_warnings
        status, headers, payload = call_app(
            "POST", "/api/report",
            std_body(format="json", capital=500.0, levels=levels, side=side,
                     moves=moves, basket_side=side, basket_levels=5))
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        import json as _json
        actual = payload if isinstance(payload, dict) else _json.loads(payload)
        # 'generated' is a timestamp - everything else must match exactly
        expected.pop("generated")
        actual.pop("generated")
        self.assertEqual(actual, expected)
        self.assertIn("SIMULATION MODEL", actual["disclaimer"])


if __name__ == "__main__":
    unittest.main()
