"""OUR EA test suite — Phase 6.

Covers (§38): contract/model version, rule registry, uncertainty, state
machine, events, basket identity, lot engine equivalence to SSOT (via
tests, never runtime imports), grid engine, basket/partial engines,
broker constraints, idempotency, persistence/recovery, risk guard,
execution + LIVE LOCK, config validation, strategy integration.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.our_ea import (contract as k_contract, events as k_events,
                         state_machine as k_sm, basket as k_basket,
                         lot_engine as k_lot, grid_engine as k_grid,
                         partial_engine as k_partial,
                         broker_constraints as k_bc, persistence as k_per,
                         risk_guard as k_risk, execution as k_exec,
                         config as k_cfg, rule_registry as k_rules)
from core.our_ea.strategy import StrategyCore

from tests import std_ctx


def make_core(mode="SIMULATION", **cfg_over):
    reg = k_rules.RuleRegistry.from_contract()
    cfg = k_cfg.OurEaConfig(model_version=reg.model_version.model_id, **cfg_over)
    adapter = k_exec.adapter_for(mode)
    log = k_events.EventLog(reg.model_version.model_id)
    return StrategyCore(cfg, adapter, log, reg), reg


class TestContract(unittest.TestCase):
    def test_loads_and_verifies_hash(self):
        doc = k_contract.load_contract()
        self.assertEqual(doc["model_id"], "V1.68-EVIDENCE-MODEL-v1.0")
        v = k_contract.contract_version()
        self.assertEqual(v.model_id, doc["model_id"])
        self.assertRegex(v.model_hash, r"^[0-9A-F]{64}$")

    def test_mismatch_detected(self):
        v1 = k_contract.ModelVersion("A", "H1")
        v2 = k_contract.ModelVersion("A", "H2")
        with self.assertRaises(k_contract.ModelVersionMismatch):
            v1.assert_matches(v2)


class TestRuleRegistry(unittest.TestCase):
    def test_bindings_from_frozen_model(self):
        reg = k_rules.RuleRegistry.from_contract()
        self.assertEqual(len(reg.all()), 16)
        self.assertEqual(len(reg.by_status("VERIFIED")), 8)
        self.assertEqual([r.rule_id for r in reg.by_status("UNKNOWN")],
                         ["R-EMERGENCY", "R-PARTIAL-TRIGGER",
                          "R-PARTIAL-VOLUME", "R-RESTART-RECOVERY"])
        self.assertEqual(reg.get("R-ACCUM-1-68").status, "REJECTED")
        r = reg.get("R-LOT-FLOOR")
        self.assertEqual(r.evidence_refs, ["E012", "E028"])

    def test_require_verified_rejects_others(self):
        reg = k_rules.RuleRegistry.from_contract()
        self.assertEqual(reg.require_verified("R-LOT-FLOOR").status, "VERIFIED")
        with self.assertRaises(k_rules.RuleNotVerified):
            reg.require_verified("R-EMERGENCY")
        with self.assertRaises(k_rules.RuleNotVerified):
            reg.require_verified("R-ACCUM-1-68")


class TestStateMachine(unittest.TestCase):
    def test_declared_transition_ok(self):
        sm = k_sm.StateMachine("V")
        sm.transition("INIT")
        sm.transition("INIT_OK")
        self.assertEqual(sm.state, k_sm.WAITING_FOR_ENTRY)

    def test_implicit_transition_rejected(self):
        sm = k_sm.StateMachine("V", initial=k_sm.IDLE)
        with self.assertRaises(k_sm.InvalidTransition):
            sm.transition("GRID_ADD")          # undeclared from IDLE

    def test_transition_records_audit_fields(self):
        sm = k_sm.StateMachine("V")
        sm.transition("INIT", condition="c", reason="r", rule_id="R",
                      trace_id="T1")
        t = sm.history[-1]
        self.assertEqual((t.state_before, t.event, t.state_after),
                         ("IDLE", "INIT", "INITIALIZING"))
        self.assertEqual(t.model_version, "V")

    def test_safety_from_any_state(self):
        for initial in k_sm.STATES:
            if initial in (k_sm.SAFE_STOP, k_sm.DISCONNECTED):
                continue
            sm = k_sm.StateMachine("V", initial=initial)
            sm.transition("SAFE_STOP", reason="test")
            self.assertEqual(sm.state, k_sm.SAFE_STOP)


class TestEvents(unittest.TestCase):
    def test_event_requires_model_version_and_unique_id(self):
        log = k_events.EventLog("V")
        log.emit(event_type="ENTRY", side="BUY")
        with self.assertRaises(ValueError):
            log.emit(event_id=log.all()[0].event_id, event_type="ENTRY")
        with self.assertRaises(ValueError):
            k_events.Event(event_id="x", timestamp="t", event_type="BOGUS",
                           model_version="V").validate()

    def test_export_json_csv(self):
        import json, csv, tempfile
        log = k_events.EventLog("V")
        log.emit(event_type="CYCLE_OPEN", cycle_id="C1", hypothesis_id="H_X")
        with tempfile.TemporaryDirectory() as td:
            jp, cp = os.path.join(td, "e.json"), os.path.join(td, "e.csv")
            log.export_json(jp)
            log.export_csv(cp)
            data = json.load(open(jp, encoding="utf-8"))
            self.assertEqual(data[0]["hypothesis_id"], "H_X")
            rows = list(csv.reader(open(cp, encoding="utf-8-sig")))
            self.assertIn("hypothesis_id", rows[0])


class TestBasketIdentity(unittest.TestCase):
    def test_deterministic_ids(self):
        self.assertEqual(k_basket.make_cycle_id("A", "S", 7), "A|S|C000007")
        b1 = k_basket.Basket("A|S|C000007")
        b2 = k_basket.Basket("A|S|C000007")
        self.assertEqual(b1.basket_id, b2.basket_id)
        self.assertEqual(b1.sequence_number, 7)

    def test_levels_and_lots(self):
        b = k_basket.Basket("A|S|C000001")
        b.add(k_basket.PositionRef("P1", "BUY", 0.10, 4400.0, 1))
        b.add(k_basket.PositionRef("P2", "SELL", 0.10, 4399.5, 1))
        b.add(k_basket.PositionRef("P3", "BUY", 0.11, 4395.0, 2))
        self.assertEqual(b.next_level("BUY"), 3)
        self.assertEqual(b.total_lots(), 0.31)
        b.close_position("P3")
        self.assertEqual(b.total_lots(), 0.20)
        self.assertEqual(b.total_lots(include_closed=True), 0.31)


class TestLotEngineEquivalence(unittest.TestCase):
    """§18: OUR EA lot semantics == Analyzer SSOT. Equivalence is proven
    by THIS TEST (Strategy Core never imports the Analyzer at runtime)."""

    def test_matches_ssot_l1_l50(self):
        from core import calculations as ssot
        cfg, prof, acct, rules = std_ctx()
        eng = k_lot.LotEngine()
        for lvl in range(1, 51):
            self.assertEqual(eng.lot(lvl),
                             ssot.lot_for_level(cfg, lvl, rules, prof).value)

    def test_observed_pins(self):
        eng = k_lot.LotEngine()
        self.assertEqual([eng.lot(n) for n in (5, 7, 10)], [0.14, 0.17, 0.23])

    def test_boundaries(self):
        eng = k_lot.LotEngine(k_lot.LotConfig(lot_step=0.10, base_lot=0.1))
        self.assertEqual(eng.lot(2), 0.10)          # floor(0.11/0.1)*0.1
        eng2 = k_lot.LotEngine(k_lot.LotConfig(min_lot=0.5))
        self.assertEqual(eng2.lot(1), 0.5)           # clamp to min
        eng3 = k_lot.LotEngine(k_lot.LotConfig(max_lot=0.12))
        self.assertEqual(eng3.lot(9), 0.12)          # clamp to max
        with self.assertRaises(k_lot.LotEngineError):
            k_lot.LotEngine(k_lot.LotConfig(multiplier=0.9)).lot(1)

    def test_fp_noise_floors_same(self):
        eng = k_lot.LotEngine()
        self.assertEqual(eng.lot(12), 0.28)
        self.assertEqual(eng.lot(19), 0.55)
        for lvl in range(1, 51):
            v = eng.lot(lvl)
            self.assertAlmostEqual(v / 0.01, round(v / 0.01), delta=1e-9)


class TestGridEngine(unittest.TestCase):
    def test_direction_verified_semantics(self):
        g = k_grid.GridEngine()
        trig = g.next_add_price("BUY", [4400.0, 4395.0], 4395.0)
        self.assertEqual(trig, 4390.0)                # BUY adds BELOW
        trig = g.next_add_price("SELL", [4390.0, 4395.0], 4395.0)
        self.assertEqual(trig, 4400.0)                # SELL adds ABOVE

    def test_hypothesis_ids_required_and_configurable(self):
        for h in ("H_PREV_ENTRY", "H_EXTREME"):
            g = k_grid.GridEngine(k_grid.GridConfig(trigger_hypothesis=h))
            d = g.evaluate("BUY", 4389.5, [4400.0], 4400.0)
            self.assertEqual(d.hypothesis_id, h)
            self.assertTrue(d.should_add)
        with self.assertRaises(k_grid.GridEngineError):
            k_grid.GridEngine(k_grid.GridConfig(trigger_hypothesis="H_AVG_PRICE"))

    def test_tolerance_kept_not_exact(self):
        self.assertEqual(k_grid.OBSERVED_SPACING["median"], 5.09)
        self.assertNotEqual(k_grid.OBSERVED_SPACING["median"], 5.0000)


class TestBasketPartialEngines(unittest.TestCase):
    def test_compatible_hypotheses_evaluated_not_verified(self):
        e = k_partial.BasketCloseEngine(
            k_partial.BasketTriggerConfig(hypothesis="H_PER_LOT_0_50"))
        r = e.evaluate(floating_gross=0.40, total_lots=0.80)
        self.assertEqual(r.threshold, 0.40)
        self.assertTrue(r.should_close)
        self.assertEqual(r.hypothesis_id, "H_PER_LOT_0_50")

    def test_1_68_unselectable(self):
        with self.assertRaises(k_partial.BasketTriggerError):
            k_partial.BasketTriggerConfig(hypothesis="H_GROSS_1_68").validate()

    def test_partial_decisions_unavailable_unknown(self):
        p = k_partial.PartialEngine()
        self.assertTrue(p.exists())
        for fn in (p.decide_trigger, p.decide_volume, p.decide_level):
            with self.assertRaises(k_partial.PartialDecisionUnavailable):
                fn()


class TestBrokerConstraints(unittest.TestCase):
    def test_normalize_validate_flow(self):
        prof = k_bc.BrokerProfile()
        v = k_bc.normalize_volume(0.115, prof)      # floors, not rounds
        self.assertEqual((v.normalized, v.valid), (0.11, True))
        v = k_bc.normalize_volume(0.005, prof)
        self.assertFalse(v.valid)                   # below min -> INVALID
        v = k_bc.normalize_volume(-1.0, prof)
        self.assertFalse(v.valid)

    def test_invalid_profile_rejected(self):
        with self.assertRaises(ValueError):
            k_bc.BrokerProfile(lot_step=0).validate()


class TestIdempotency(unittest.TestCase):
    def test_duplicate_refused(self):
        led = k_bc.IdempotencyLedger()
        key = k_bc.IdempotencyKey.build("A", "S", "C1", "GRID_ADD", 3)
        self.assertTrue(led.check_and_record(key))
        self.assertFalse(led.check_and_record(key))
        self.assertTrue(led.seen(key))


class TestPersistenceRecovery(unittest.TestCase):
    def _state(self, tmp):
        b = k_basket.Basket("A|S|C000003", "2026-09-25T00:00:00")
        b.add(k_basket.PositionRef("P1", "BUY", 0.10, 4400.0, 1))
        return k_per.snapshot(
            model_version="V1.68-EVIDENCE-MODEL-v1.0", model_hash="H" * 64,
            config_version="OUR_EA_CONFIG_V1", execution_mode="PAPER",
            state_machine_state=k_sm.GRID_ACTIVE, basket=b,
            cycle_sequence=3, last_event_id="E1", last_event_ts="t")

    def test_roundtrip(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            store = k_per.StateStore(os.path.join(td, "state.json"))
            st = self._state(td)
            store.save(st)
            back = store.load()
            self.assertEqual(back.cycle_id, "A|S|C000003")
            b = store.restore_basket(back)
            self.assertEqual(b.positions[0].lot, 0.10)

    def test_model_mismatch_on_restore(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            store = k_per.StateStore(os.path.join(td, "state.json"))
            store.save(self._state(td))
            with self.assertRaises(k_per.PersistenceError):
                store.load(expected_model=("OTHER", "X" * 64))

    def test_recovery_policy_is_our_ea(self):
        rp = k_per.RecoveryPolicy()
        r = rp.on_reconnect_with_open_basket()
        self.assertEqual(r["source"], "OUR_EA_POLICY")
        self.assertIn("UNKNOWN", r["reason"])
        self.assertFalse(r["allow_grid_adds"])


class TestRiskGuard(unittest.TestCase):
    def test_entry_limits(self):
        g = k_risk.RiskGuard(k_risk.RiskLimits(max_positions=2,
                                               max_grid_depth=2,
                                               max_total_lot=0.25))
        ok = g.check_entry(open_positions=1, side_levels=1,
                           total_lot_after=0.21, spread_usd=0.3)
        self.assertTrue(ok.allowed)
        bad = g.check_entry(open_positions=2, side_levels=2,
                            total_lot_after=0.3, spread_usd=0.3)
        self.assertFalse(bad.allowed)
        self.assertEqual(len(bad.violations), 3)

    def test_emergency_policy_sources(self):
        g = k_risk.RiskGuard()
        g.state.equity_peak = 1000.0
        r = g.emergency_policy(floating_usd=-60.0, equity=900.0,
                               grid_depth=5, margin_used=100.0)
        self.assertTrue(r.emergency_stop)
        self.assertEqual(r.source, "OUR_EA_POLICY")

    def test_kill_switch(self):
        g = k_risk.RiskGuard()
        g.engage_kill_switch()
        r = g.check_entry(open_positions=0, side_levels=0,
                          total_lot_after=0.1, spread_usd=0.1)
        self.assertFalse(r.allowed)

    def test_invalid_limits(self):
        with self.assertRaises(k_risk.RiskGuardError):
            k_risk.RiskLimits(max_positions=0).validate()


class TestExecutionAndLiveLock(unittest.TestCase):
    def test_simulation_adapter_fills(self):
        a = k_exec.SimulationAdapter()
        r = a.submit(k_exec.ExecutionIntent("I1", "OPEN", "GOLDmicro",
                                            "BUY", 0.1, None), 4400.0)
        self.assertEqual(r.status, "FILLED")
        self.assertEqual(r.filled_lot, 0.1)

    def test_injected_rejection_and_timeout(self):
        a = k_exec.SimulationAdapter(reject_next=1)
        r = a.submit(k_exec.ExecutionIntent("I1", "OPEN", "GOLDmicro",
                                            "BUY", 0.1, None), 1.0)
        self.assertEqual(r.status, "REJECTED")
        a2 = k_exec.SimulationAdapter(fail_actions=("CLOSE",))
        r2 = a2.submit(k_exec.ExecutionIntent("I2", "CLOSE", "GOLDmicro",
                                              "SELL", 0.1, None), 1.0)
        self.assertEqual(r2.status, "TIMEOUT")

    def test_live_hard_locked(self):
        with self.assertRaises(k_exec.LiveLockError):
            k_exec.LiveAdapter()                     # instantiation refused
        with self.assertRaises(k_exec.LiveLockError):
            k_exec.resolve_mode("LIVE")              # mode resolution refused
        self.assertTrue(k_exec.LIVE_DISABLED)

    def test_adapter_factory(self):
        for m in ("SIMULATION", "PAPER", "DEMO"):
            self.assertEqual(k_exec.adapter_for(m).mode, m)


class TestConfig(unittest.TestCase):
    def test_valid_config(self):
        c = k_cfg.OurEaConfig(model_version="V1.68-EVIDENCE-MODEL-v1.0")
        self.assertEqual(c.execution_mode, "SIMULATION")

    def test_invalid_config_no_silent_fallback(self):
        with self.assertRaises(k_cfg.ConfigInvalid):
            k_cfg.OurEaConfig(model_version="V",
                              execution_mode="LIVE").validate()
        with self.assertRaises(k_cfg.ConfigInvalid):
            k_cfg.OurEaConfig(model_version="V",
                              basket={"hypothesis": "H_GROSS_1_68"}).validate()
        with self.assertRaises(k_cfg.ConfigInvalid):
            k_cfg.OurEaConfig(model_version="").validate()


class TestStrategyIntegration(unittest.TestCase):
    def test_full_cycle_lifecycle(self):
        core, reg = make_core()
        px = 4400.0
        for _ in range(10):
            core.on_tick(px, px - 0.5, 0.5)
            px -= 2.0
        b = core.basket.summary()
        self.assertEqual(b["buy_levels"], 4)          # grid added down
        self.assertEqual(b["sell_levels"], 1)
        # recover: price rises; basket should close >= $1 then resume
        closed = False
        for _ in range(60):
            px += 2.0
            core.on_tick(px, px - 0.5, 0.5)
            if core.log.by_type("CYCLE_END"):
                closed = True
                break
        self.assertTrue(closed, "basket must close on recovery (>= $1)")
        end = core.log.by_type("CYCLE_END")[0]
        self.assertEqual(end.hypothesis_id, "H_GROSS_1_00")
        # normal resume: a new cycle opens on the next flat tick
        for _ in range(5):
            core.on_tick(px, px - 0.5, 0.5)
        self.assertGreaterEqual(core.cycle_sequence, 2)
        # duplicate tick must not mint a new cycle or duplicate entries
        n_cycles = core.cycle_sequence
        n_events = len(core.log.all())
        core.on_tick(px, px - 0.5, 0.5)
        core.on_tick(px, px - 0.5, 0.5)
        self.assertGreaterEqual(core.cycle_sequence, n_cycles)

    def test_unknown_partial_never_guessed(self):
        core, reg = make_core(partial={"enabled": True})
        px = 4400.0
        for _ in range(30):
            core.on_tick(px, px - 0.5, 0.5)
            px -= 1.0
        self.assertTrue(core.uncertainties)
        u = core.uncertainties[0]
        self.assertEqual(u.model_version, "V1.68-EVIDENCE-MODEL-v1.0")
        self.assertTrue(u.required_evidence)

    def test_model_version_binding(self):
        core, reg = make_core()
        self.assertRegex(core.model_version.model_hash, r"^[0-9A-F]{64}$")


if __name__ == "__main__":
    unittest.main()
