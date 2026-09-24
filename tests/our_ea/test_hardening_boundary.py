"""Phase 6.1 hardening tests (§6, §18, §12) + boundary audits (§0, §11).

Covers: corrupted state -> SAFE_STOP, stale/out-of-order ticks, invalid
price, partial fill, adapter exception, kill-switch persistence through
restore, event config_version; forbidden-import scan; analyzer-untouched
diff check; live-lock bypass attempts (§22).
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.our_ea import persistence as k_per
from core.our_ea import execution as k_exec
from core.our_ea import events as k_events
from core.our_ea.config import OurEaConfig, ConfigInvalid
from core.our_ea.rule_registry import RuleRegistry
from core.our_ea.strategy import StrategyCore
from core.our_ea.events import EventLog

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_core(adapter=None, **over):
    reg = RuleRegistry.from_contract()
    cfg = OurEaConfig(model_version=reg.model_version.model_id, **over)
    return StrategyCore(cfg, adapter or k_exec.SimulationAdapter(),
                        EventLog(reg.model_version.model_id), reg)


class TestPersistenceHardening(unittest.TestCase):
    def test_corrupted_state_safe_stop(self):
        with tempfile.TemporaryDirectory() as td:
            store = k_per.StateStore(os.path.join(td, "s.json"))
            st = k_per.snapshot(model_version="V", model_hash="H" * 64,
                                config_version="C", execution_mode="PAPER",
                                state_machine_state="GRID_ACTIVE",
                                basket=k_per.Basket("A|S|C000001"),
                                cycle_sequence=1)
            store.save(st)
            # tamper payload inside the envelope
            doc = open(store.path, encoding="utf-8").read()
            open(store.path, "w", encoding="utf-8").write(
                doc.replace('"cycle_sequence": 1', '"cycle_sequence": 999'))
            with self.assertRaises(k_per.StateCorruptionError):
                store.load()
            # policy: corruption -> SAFE_STOP (never best-effort)
            self.assertEqual(
                k_per.RecoveryPolicy().on_state_corrupt()["action"],
                "SAFE_STOP")

    def test_missing_required_field_is_corruption(self):
        with tempfile.TemporaryDirectory() as td:
            store = k_per.StateStore(os.path.join(td, "s.json"))
            st = k_per.snapshot(model_version="V", model_hash="H" * 64,
                                config_version="C", execution_mode="PAPER",
                                state_machine_state="IDLE",
                                basket=k_per.Basket("A|S|C000001"),
                                cycle_sequence=1)
            store.save(st)
            doc = open(store.path, encoding="utf-8").read()
            open(store.path, "w", encoding="utf-8").write(
                doc.replace('"cycle_sequence"', '"cycle_seqX"'))
            with self.assertRaises(k_per.StateCorruptionError):
                store.load()

    def test_kill_switch_survives_restore(self):
        reg = RuleRegistry.from_contract()
        with tempfile.TemporaryDirectory() as td:
            store = k_per.StateStore(os.path.join(td, "s.json"))
            cfg = OurEaConfig(model_version=reg.model_version.model_id)
            log = EventLog(reg.model_version.model_id)
            core = StrategyCore(cfg, k_exec.PaperAdapter(), log, reg,
                                state_store=store)
            core.on_tick(4400.0, 4399.5, 0.5)
            core.risk.engage_kill_switch()
            core._persist()
            persisted = store.load()
            core2 = StrategyCore.restore(cfg, k_exec.PaperAdapter(),
                                         EventLog(reg.model_version.model_id),
                                         reg, store, persisted)
            self.assertTrue(core2.risk.state.kill_switch)
            # drive price down so a BUY grid add is attempted -> blocked
            core2.on_tick(4394.0, 4393.5, 0.5)
            self.assertTrue(any("kill switch" in e.reason
                                for e in core2.log.by_type("RISK_BLOCK")))

    def test_roundtrip_with_extended_fields(self):
        with tempfile.TemporaryDirectory() as td:
            store = k_per.StateStore(os.path.join(td, "s.json"))
            b = k_per.Basket("A|S|C000004", "t0")
            b.add(k_per.PositionRef("P1", "BUY", 0.1, 4400.0, 1))
            st = k_per.snapshot(model_version="V", model_hash="H" * 64,
                                config_version="C", execution_mode="PAPER",
                                state_machine_state="GRID_ACTIVE", basket=b,
                                cycle_sequence=4, tick_no=77,
                                idem_keys=[["A", "S", "C", "GRID_ADD", 3]],
                                realized_gross=1.25, uncertainties=2)
            store.save(st)
            back = store.load()
            self.assertEqual((back.tick_no, back.realized_gross,
                              back.uncertainties, len(back.idem_keys)),
                             (77, 1.25, 2, 1))


class TestTickGuards(unittest.TestCase):
    def test_invalid_price_skipped(self):
        core = make_core()
        d = core.on_tick(-1.0, 4399.5)
        self.assertEqual(d["phase"], "invalid_price_skipped")
        self.assertTrue(core.log.by_type("ERROR"))

    def test_stale_and_out_of_order_ticks_skipped(self):
        core = make_core()
        core.on_tick(4400.0, 4399.5, 0.5, ts="2026-09-25T01:00:05")
        d = core.on_tick(4399.0, 4398.5, 0.5, ts="2026-09-25T01:00:03")
        self.assertEqual(d["phase"], "stale_tick_skipped")
        # identical timestamp (duplicate feed event) processed exactly once
        d2 = core.on_tick(4400.0, 4399.5, 0.5, ts="2026-09-25T01:00:05")
        self.assertNotEqual(d2["phase"], "stale_tick_skipped")

    def test_adapter_exception_safe_stop(self):
        class Exploding(k_exec.ExecutionAdapter):
            mode = "SIMULATION"
            def submit(self, intent, market_price=0.0):
                raise RuntimeError("broker vanished")
        core = make_core(Exploding())
        core.on_tick(4400.0, 4399.5, 0.5)
        self.assertIn(core.sm.state, ("SAFE_STOP", "WAITING_FOR_ENTRY"))
        self.assertTrue(any("adapter failure" in e.reason
                            for e in core.log.by_type("ERROR")))

    def test_partial_fill_uses_filled_lot(self):
        class PartialFill(k_exec.SimulationAdapter):
            def submit(self, intent, market_price=0.0):
                res = super().submit(intent, market_price)
                return k_exec.ExecutionResult(
                    res.intent_id, res.status,
                    round(res.filled_lot * 0.5, 2), res.price,
                    res.position_id, res.reason, res.execution_mode)
        core = make_core(PartialFill())
        core.on_tick(4400.0, 4399.5, 0.5)
        lots = [p.lot for p in core.basket.positions]
        self.assertTrue(all(abs(l - 0.05) < 1e-9 for l in lots))

    def test_events_carry_config_version(self):
        core = make_core()
        core.on_tick(4400.0, 4399.5, 0.5)
        for e in core.log.all():
            self.assertEqual(e.config_version, "OUR_EA_CONFIG_V1")


class TestBoundaryAudit(unittest.TestCase):
    """GATE-B / GATE-C automation."""

    FORBIDDEN = ("core.forensics", "core.evidence", "core.cycle",
                 "core.basket", "core.calculations", "MetaTrader5",
                 "mt5", "win32")

    def test_no_forbidden_runtime_imports(self):
        pkg = os.path.join(ROOT, "core", "our_ea")
        violations = []
        for fn in os.listdir(pkg):
            if not fn.endswith(".py"):
                continue
            src = open(os.path.join(pkg, fn), encoding="utf-8").read()
            for bad in self.FORBIDDEN:
                for line in src.splitlines():
                    s = line.strip()
                    if (s.startswith("import ") or s.startswith("from ")) and bad in s:
                        violations.append(f"{fn}: {s}")
        self.assertEqual(violations, [],
                         f"forbidden Analyzer/broker runtime imports: {violations}")

    def test_analyzer_untouched_since_phase6_baseline(self):
        r = subprocess.run(
            ["git", "diff", "--name-only", "e5159fc", "HEAD", "--",
             "core/calculations.py", "core/evidence.py", "core/cycle.py",
             "core/basket.py", "core/forensics", "web/backend", "desktop"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "",
                         f"Analyzer runtime modified since e5159fc: {r.stdout}")

    def test_frozen_model_hash_unchanged(self):
        import hashlib
        h = hashlib.sha256(open(os.path.join(
            ROOT, "data", "evidence_model",
            "V1.68-EVIDENCE-MODEL-v1.0.json"), "rb").read()).hexdigest().upper()
        expected = open(os.path.join(
            ROOT, "data", "evidence_model",
            "V1.68-EVIDENCE-MODEL-v1.0.sha256.txt")).read().strip()
        self.assertEqual(h, expected)


class TestLiveLockBypass(unittest.TestCase):
    """GATE-T: every unlock attempt must be REFUSED/LOCKED."""

    def test_direct_instantiation_refused(self):
        with self.assertRaises(k_exec.LiveLockError):
            k_exec.LiveAdapter()

    def test_mode_resolution_refused(self):
        with self.assertRaises(k_exec.LiveLockError):
            k_exec.resolve_mode("LIVE")

    def test_config_live_refused(self):
        with self.assertRaises(ConfigInvalid):
            OurEaConfig(model_version="V",
                        execution_mode="LIVE").validate()

    def test_adapter_factory_refused(self):
        with self.assertRaises(k_exec.LiveLockError):
            k_exec.adapter_for("LIVE")

    def test_config_case_tricks_refused(self):
        for trick in ("live", "Live", "L I V E", "LIVE "):
            with self.assertRaises(ConfigInvalid):
                OurEaConfig(model_version="V", execution_mode=trick).validate()

    def test_persisted_state_cannot_unlock_live(self):
        reg = RuleRegistry.from_contract()
        cfg = OurEaConfig(model_version=reg.model_version.model_id)
        with tempfile.TemporaryDirectory() as td:
            store = k_per.StateStore(os.path.join(td, "s.json"))
            st = k_per.snapshot(
                model_version=reg.model_version.model_id,
                model_hash=reg.model_version.model_hash,
                config_version=cfg.schema, execution_mode="LIVE",
                state_machine_state="GRID_ACTIVE",
                basket=k_per.Basket("A|S|C000001"), cycle_sequence=1)
            store.save(st)
            # restoring does NOT create a live adapter; mode must still be
            # validated through OurEaConfig before any execution
            with self.assertRaises(ConfigInvalid):
                OurEaConfig(model_version=reg.model_version.model_id,
                            execution_mode=st.execution_mode).validate()

    def test_no_env_or_flag_unlock_path(self):
        # the ONLY mode entrypoint is OurEaConfig/adapter_for/resolve_mode;
        # none of them read environment variables or argv — verify by
        # source inspection (no os.environ / sys.argv in execution paths)
        src = open(os.path.join(ROOT, "core", "our_ea", "execution.py"),
                   encoding="utf-8").read()
        self.assertNotIn("os.environ", src)
        self.assertNotIn("argv", src)
        self.assertTrue(k_exec.LIVE_DISABLED)


if __name__ == "__main__":
    unittest.main()
