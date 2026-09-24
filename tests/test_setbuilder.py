"""Tests: test sessions (Module 15), model version store, set store,
set builder, project/report IO."""
import json
import os
import unittest

from core.config import EAConfig
from core.model_rules import (ModelVersionStore, SimulationModelRules,
                              LOT_ARITHMETIC_STEP)
from core.mt5_adapters import BehaviorRecord, EVENT_ADD_GRID
from core.sessions import TestSession, SessionStore
from core.setbuilder import (SetStore, build_combinations, evaluate_set,
                             apply_filters, BuilderFilters, grid_capacity_levels)
from tests import TempDirTestMixin, std_ctx


class TestSessions(TempDirTestMixin, unittest.TestCase):
    def test_new_session_id(self):
        s = TestSession.new(symbol="XAUUSD", broker="DemoBroker")
        self.assertTrue(s.session_id.startswith("S"))
        self.assertEqual(s.symbol, "XAUUSD")
        self.assertEqual(s.ea_version, "1.68")

    def test_save_load_delete_cycle(self):
        store = SessionStore(os.path.join(self.tmpdir, "sessions"))
        s = TestSession.new(symbol="XAUUSD", account_type="demo",
                            initial_balance=5000.0,
                            config=EAConfig().to_dict())
        s.observed_events.append(BehaviorRecord(
            timestamp="t", event=EVENT_ADD_GRID, side="BUY", lot=0.11).to_dict())
        store.save(s)
        self.assertEqual(store.list_sessions(), [s.session_id])
        loaded = store.load(s.session_id)
        self.assertEqual(loaded.symbol, "XAUUSD")
        self.assertEqual(len(loaded.observed_events), 1)
        recs = loaded.events_as_records()
        self.assertEqual(recs[0].event, EVENT_ADD_GRID)
        store.delete(s.session_id)
        self.assertEqual(store.list_sessions(), [])

    def test_schema_versioned(self):
        s = TestSession.new()
        self.assertEqual(s.to_dict()["schema"], "SNIPER_TEST_SESSION_V1")

    def test_sessions_isolated(self):
        store = SessionStore(os.path.join(self.tmpdir, "sessions"))
        a = TestSession.new(symbol="A")
        b = TestSession.new(symbol="B")
        store.save(a)
        store.save(b)
        self.assertNotEqual(store.load(a.session_id).symbol,
                            store.load(b.session_id).symbol)


class TestModelVersionStore(TempDirTestMixin, unittest.TestCase):
    def test_initial_version_created(self):
        store = ModelVersionStore(os.path.join(self.tmpdir, "mv.json"))
        self.assertEqual(len(store.all_versions()), 1)
        self.assertEqual(store.active_rules().model_version, "SM-001")

    def test_apply_new_version_bumps_and_persists(self):
        path = os.path.join(self.tmpdir, "mv.json")
        store = ModelVersionStore(path)
        rules = store.active_rules()
        rules.lot_formula = LOT_ARITHMETIC_STEP
        rules.arithmetic_step_lots = 0.02
        new = store.apply_new_version(rules, source="observed-applied",
                                      changes=["lot formula -> ARITHMETIC"],
                                      notes="user confirmed",
                                      based_on_evidence=["E007"],
                                      confirmed_by="test-user")
        self.assertEqual(new.model_version, "SM-002")
        self.assertEqual(len(store.all_versions()), 2)
        # reload from disk keeps history
        store2 = ModelVersionStore(path)
        self.assertEqual(len(store2.all_versions()), 2)
        self.assertEqual(store2.active_rules().lot_formula, LOT_ARITHMETIC_STEP)
        entry = store2.all_versions()[-1]
        self.assertEqual(entry.confirmed_by, "test-user")
        self.assertEqual(entry.previous_version, "SM-001")
        self.assertEqual(entry.based_on_evidence, ["E007"])

    def test_apply_requires_explicit_confirmation(self):
        # Phase 2: model changes without human confirmation are rejected
        store = ModelVersionStore(os.path.join(self.tmpdir, "mv2.json"))
        rules = store.active_rules()
        with self.assertRaises(ValueError):
            store.apply_new_version(rules, source="manual-edit",
                                    changes=["no confirm"])

    def test_invalid_rules_rejected(self):
        store = ModelVersionStore(os.path.join(self.tmpdir, "mv.json"))
        rules = store.active_rules()
        rules.lot_formula = "NOT_A_FORMULA"
        with self.assertRaises(ValueError):
            store.apply_new_version(rules, "manual", ["bad"])


class TestSetBuilder(TempDirTestMixin, unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()
        self.prof.reference_price = 2000.0

    def test_combinations_cartesian(self):
        combos = build_combinations({
            "capital": [500], "grid_step": [5.0, 8.0], "base_lot": [0.1],
            "multiplier": [1.1, 1.2], "basket_target": [1.68], "max_grid": [10],
        })
        self.assertEqual(len(combos), 4)
        self.assertIn({"capital": 500.0, "grid_step": 8.0, "base_lot": 0.1,
                       "multiplier": 1.2, "basket_target": 1.68, "max_grid": 10.0},
                      combos)

    def test_too_many_combinations_rejected(self):
        with self.assertRaises(ValueError):
            build_combinations({
                "capital": list(range(80)), "grid_step": list(range(80)),
                "base_lot": [0.1], "multiplier": [1.1], "basket_target": [1.68],
                "max_grid": [10],
            })

    def test_evaluate_set_metrics(self):
        m = evaluate_set(self.cfg, self.prof, self.acct, self.rules,
                         capital=500.0, grid_step=5.0, base_lot=0.1,
                         multiplier=1.1, basket_target=1.68, max_grid=10)
        self.assertEqual(m.max_grid, 10)
        self.assertAlmostEqual(m.max_single_lot, 0.23)   # 0.1*1.1^9=0.2358 floor->0.23 (MC-001)
        self.assertLess(m.estimated_worst_floating_loss, 0)
        self.assertGreater(m.grid_capacity_levels, 0)
        self.assertTrue(m.assumptions)

    def test_filters(self):
        m = evaluate_set(self.cfg, self.prof, self.acct, self.rules,
                         capital=500.0, grid_step=5.0, base_lot=0.1,
                         multiplier=1.1, basket_target=1.68, max_grid=10)
        passed, reasons = apply_filters(
            m, BuilderFilters(max_dd_percent=1.0, max_grid=3,
                              max_lot=0.5, max_margin_usage_percent=1.0))
        self.assertFalse(passed)
        self.assertEqual(len(reasons), 3)
        passed, _ = apply_filters(m, BuilderFilters())
        self.assertTrue(passed)

    def test_grid_capacity_levels(self):
        # tiny capital hits the margin-level stop quickly
        self.assertLess(grid_capacity_levels(self.cfg, self.prof, self.acct,
                                             self.rules, capital=100.0), 10)
        # huge capital runs until a single order exceeds broker lot_max(100):
        # 0.1*1.1^(n-1) > 100 first happens at level 74
        self.assertEqual(grid_capacity_levels(self.cfg, self.prof, self.acct,
                                              self.rules, capital=10_000_000_000.0), 74)


class TestSetStore(TempDirTestMixin, unittest.TestCase):
    def _store(self):
        return SetStore(os.path.join(self.tmpdir, "sets.json"))

    def test_save_duplicate_delete(self):
        store = self._store()
        store.save_set("setA", EAConfig(), 500.0)
        store.duplicate_set("setA", "setB")
        self.assertEqual(store.names(), ["setA", "setB"])
        store.delete_set("setA")
        self.assertEqual(store.names(), ["setB"])
        with self.assertRaises(KeyError):
            store.delete_set("setA")

    def test_empty_name_rejected(self):
        store = self._store()
        with self.assertRaises(ValueError):
            store.save_set("  ", EAConfig(), 500.0)

    def test_export_import_roundtrip(self):
        store = self._store()
        store.save_set("myset", EAConfig(), 750.0)
        path = os.path.join(self.tmpdir, "myset.json")
        store.export_set("myset", path)
        store.delete_set("myset")
        name = store.import_set(path)
        self.assertEqual(name, "myset")
        self.assertEqual(store.get_set("myset")["capital"], 750.0)

    def test_invalid_import_raises(self):
        path = os.path.join(self.tmpdir, "bad.json")
        with open(path, "w") as f:
            f.write('{"nope": 1}')
        store = self._store()
        with self.assertRaises(ValueError):
            store.import_set(path)


if __name__ == "__main__":
    unittest.main()
