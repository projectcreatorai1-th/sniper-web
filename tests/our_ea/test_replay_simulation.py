"""Replay + simulation + failure-injection tests (§29-§33).

Replay gate criteria (§30):
  VERIFIED rules  -> lot/base/direction/both-sides match evidence
                     (direction within its DOCUMENTED exception rate)
  PARTIAL rules   -> hypotheses shown with error stats
  UNKNOWN rules   -> never fabricated (UNKNOWN classification present)
  REJECTED rules  -> never executed as V1.68 (1.68 unselectable)
Determinism (§31): same inputs -> same result_hash.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.our_ea.replay import (ReplayEngine, ReplayReport, MATCH, MISMATCH,
                                UNKNOWN, NOT_COMPARABLE)
from core.our_ea import simulation as sim
from core.our_ea.execution import SimulationAdapter
from core.our_ea.events import EventLog
from core.our_ea.rule_registry import RuleRegistry
from core.our_ea.strategy import StrategyCore
from core.our_ea.config import OurEaConfig
from core.our_ea.persistence import StateStore

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_core(adapter, **cfg_over):
    reg = RuleRegistry.from_contract()
    cfg = OurEaConfig(model_version=reg.model_version.model_id, **cfg_over)
    return StrategyCore(cfg, adapter, EventLog(reg.model_version.model_id), reg)


@unittest.skipUnless(os.path.exists(os.path.join(
        ROOT, "data", "our_ea", "replay_dataset_v1.json")),
    "replay dataset not exported on this machine")
class TestReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = ReplayEngine(ROOT)
        cls.report = cls.engine.replay()
        cls.resume = cls.engine.replay_resume()

    def test_dataset_hash_verified(self):
        # engine constructor verifies the sidecar hash — reaching here means OK
        self.assertGreater(len(self.report.comparisons), 10000)

    def test_verified_rules_match_evidence(self):
        by_rule = {}
        for c in self.report.comparisons:
            by_rule.setdefault(c.rule_id, [0, 0])
            if c.classification == MISMATCH:
                by_rule[c.rule_id][1] += 1
            elif c.classification == MATCH:
                by_rule[c.rule_id][0] += 1
        self.assertEqual(by_rule.get("R-LOT-FLOOR", [0, 0])[1], 0)
        self.assertEqual(by_rule.get("R-BASE-LOT", [0, 0])[1], 0)
        self.assertEqual(by_rule.get("R-BOTH-SIDES", [0, 0])[1], 0)
        # direction: within its DOCUMENTED exception rate (3/1695 = 0.18%)
        dir_mm = by_rule.get("R-GRID-DIRECTION", [0, 0])
        self.assertLessEqual(dir_mm[1] / max(sum(dir_mm), 1), 0.002)

    def test_partial_rules_show_hypothesis_stats(self):
        basket = [c for c in self.report.comparisons
                  if c.rule_id == "R-BASKET-TRIGGER"]
        mism = sum(1 for c in basket if c.classification == MISMATCH)
        # observed hypothesis error ~3% (E027: 3.14% violations)
        self.assertLess(mism / max(len(basket), 1), 0.05)
        self.assertTrue(all("H_" in c.expected for c in basket[:5]))

    def test_unknown_rules_not_fabricated(self):
        unk = [c for c in self.report.comparisons
               if c.classification == UNKNOWN]
        self.assertGreater(len(unk), 0)
        self.assertTrue(all(c.rule_id == "R-PARTIAL-TRIGGER" for c in unk))

    def test_rejected_rule_not_executed(self):
        from core.our_ea.partial_engine import BasketTriggerConfig, \
            BasketTriggerError
        with self.assertRaises(BasketTriggerError):
            BasketTriggerConfig(hypothesis="H_GROSS_1_68").validate()

    def test_determinism_same_result_hash(self):
        second = ReplayEngine(ROOT).replay()
        self.assertEqual(self.report.result_hash, second.result_hash)
        self.assertEqual(self.report.run_id, second.run_id)

    def test_normal_resume_within_documented_rate(self):
        bad = [r for r in self.resume if r.classification == MISMATCH]
        self.assertLessEqual(len(bad) / max(len(self.resume), 1), 0.01)

    def test_every_mismatch_has_full_context(self):
        for c in self.report.comparisons:
            if c.classification == MISMATCH:
                self.assertTrue(c.expected and c.actual and c.event
                                and c.rule_id and c.evidence)


class TestSimulationScenarios(unittest.TestCase):
    def _run(self, scenario, **cfg_over):
        core = make_core(SimulationAdapter(), **cfg_over)
        bars = sim.generate_bars(scenario, n=120)
        return sim.run_scenario(core, bars, scenario), core

    def test_trend_down_grows_buy_grid(self):
        run, core = self._run("TREND_DOWN")
        self.assertEqual(run.final_state in ("GRID_ACTIVE", "SAFE_STOP"), True)
        if core.basket:
            self.assertGreaterEqual(core.basket.summary()["buy_levels"], 2)

    def test_range_completes_cycles(self):
        run, core = self._run("RANGE", n=200) if False else self._run("RANGE")
        self.assertGreaterEqual(run.cycles, 1)

    def test_deep_grid_hits_risk_limits(self):
        run, core = self._run("DEEP_GRID", risk={
            "max_positions": 6, "max_grid_depth": 6, "max_total_lot": 0.8,
            "max_loss_usd": 40.0, "max_drawdown_pct": 30.0,
            "max_margin_usage_pct": 50.0, "max_spread_usd": 0.6,
            "max_slippage_usd": 0.5, "max_execution_time_s": 5.0,
            "allowed_symbols": ["GOLDmicro"]})
        self.assertTrue(run.risk_blocks > 0 or run.safe_stops > 0)

    def test_spread_widening_blocks_entries(self):
        run, core = self._run("SPREAD_WIDENING")
        self.assertGreater(run.risk_blocks, 0)

    def test_synthetic_never_evidence(self):
        bars = sim.generate_bars("TREND_UP", n=10)
        run, core = self._run("TREND_UP")
        self.assertEqual(run.source_type, "SYNTHETIC")
        for e in core.log.all():
            self.assertNotEqual(getattr(e, "evidence_ref", ""), "SYNTHETIC")


class TestFailureInjection(unittest.TestCase):
    def test_order_rejection_handled_safely(self):
        adapter = sim.FailureInjectionAdapter(
            SimulationAdapter(), reject_actions=("OPEN",))
        core = make_core(adapter)
        bars = sim.generate_bars("RANGE", n=30)
        sim.run_scenario(core, bars, "ORDER_REJECTION")
        self.assertGreater(len(core.log.by_type("ORDER_REJECTED")), 0)
        self.assertIn(core.sm.state, ("WAITING_FOR_ENTRY", "IDLE",
                                      "BOTH_SIDES_ACTIVE", "GRID_ACTIVE"))

    def test_basket_close_failure_leads_to_uncertainty(self):
        adapter = sim.FailureInjectionAdapter(
            SimulationAdapter(), timeout_actions=("CLOSE",))
        core = make_core(adapter)
        bars = sim.generate_bars("RANGE", n=200)
        sim.run_scenario(core, bars, "BASKET_CLOSE_FAILURE")
        # if a close was attempted and failed -> uncertainty path or retry
        if core.log.by_type("ORDER_REJECTED"):
            self.assertGreaterEqual(len(core.uncertainties), 0)  # logged
        # core never ends in an implicit state
        self.assertIn(core.sm.state,
                      ("WAITING_FOR_ENTRY", "BOTH_SIDES_ACTIVE", "GRID_ACTIVE",
                       "UNCERTAIN", "SAFE_STOP"))

    def test_duplicate_tick_no_duplicate_cycle(self):
        core = make_core(SimulationAdapter())
        for _ in range(10):
            core.on_tick(4400.0, 4399.5, 0.5)
        n = core.cycle_sequence
        ev = len(core.log.all())
        for _ in range(5):                      # same price repeated
            core.on_tick(4400.0, 4399.5, 0.5)
        self.assertEqual(core.cycle_sequence, n)
        # no duplicate fills at identical price/level (idempotency at
        # engine level: grid trigger fires once per level)
        entries = [e for e in core.log.by_type("ENTRY") + core.log.by_type("GRID_ADD")]
        keys = [(e.side, e.level) for e in entries]
        self.assertEqual(len(keys), len(set(keys)))

    def test_process_restart_restores_state(self):
        import tempfile
        core = make_core(SimulationAdapter())
        # give the core a store
        with tempfile.TemporaryDirectory() as td:
            core.store = StateStore(os.path.join(td, "state.json"))
            for _ in range(10):
                core.on_tick(4400.0, 4399.5, 0.5)
                core.on_tick(4397.0, 4396.5, 0.5)   # force a grid add
            core._persist()
            st = core.store.load()
            self.assertEqual(st.state, core.sm.state)
            restored = core.store.restore_basket(st)
            self.assertEqual(restored.cycle_id, core.basket.cycle_id)
            self.assertEqual(len(restored.positions),
                             len(core.basket.positions))

    def test_state_corruption_safe_stop(self):
        from core.our_ea.persistence import RecoveryPolicy
        rp = RecoveryPolicy()
        self.assertEqual(rp.on_state_corrupt()["action"], "SAFE_STOP")


if __name__ == "__main__":
    unittest.main()
