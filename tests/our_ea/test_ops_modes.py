"""Phase 6.2 tests — runtime modes, kill layers, cancel-on-disconnect,
reconciliation, data pipeline (RAW immutability, DQ flags, time
integrity, execution-quality distributions)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.our_ea import ops, data_pipeline as dp


class TestRuntimeModes(unittest.TestCase):
    def test_mode_lifecycle(self):
        m = ops.ModeController()
        self.assertEqual(m.transition("OPERATOR_START"), "OBSERVATION")
        self.assertEqual(m.transition("OPERATOR_PROMOTE_SHADOW"), "SHADOW")
        self.assertEqual(m.transition("OPERATOR_PROMOTE_DEMO"), "DEMO")
        self.assertTrue(m.allows_orders())

    def test_no_automatic_skip_observation_to_demo(self):
        m = ops.ModeController()
        m.transition("OPERATOR_START")
        with self.assertRaises(ops.ModeTransitionError):
            m.transition("OPERATOR_PROMOTE_DEMO")     # undeclared

    def test_live_refused_everywhere(self):
        m = ops.ModeController()
        m.transition("OPERATOR_START")
        m.transition("OPERATOR_PROMOTE_SHADOW")
        m.transition("OPERATOR_PROMOTE_DEMO")
        with self.assertRaises(ops.ModeTransitionError):
            m.request_live()
        for event in ("OPERATOR_PROMOTE_LIVE", "AUTO_LIVE", "LIVE"):
            with self.assertRaises(ops.ModeTransitionError):
                m.transition(event)

    def test_transition_records_audit(self):
        m = ops.ModeController()
        m.transition("OPERATOR_START", operator="OP1", reason="r")
        rec = m.history[-1]
        self.assertEqual((rec.from_mode, rec.to_mode), ("INIT", "OBSERVATION"))
        self.assertTrue(all(rec.validations.values()))
        self.assertEqual(rec.operator, "OP1")

    def test_observation_shadow_no_broker_mutation(self):
        m = ops.ModeController()
        m.transition("OPERATOR_START")
        self.assertFalse(m.allows_broker_mutation())
        m.transition("OPERATOR_PROMOTE_SHADOW")
        self.assertFalse(m.allows_broker_mutation())


class TestKillSwitch(unittest.TestCase):
    def test_layers_and_sequence(self):
        kb = ops.KillSwitchBoard()
        rec = kb.engage(ops.KILL_ORDER, "test")
        self.assertEqual(rec["sequence"][0], "STOP_NEW_ORDERS")
        self.assertTrue(kb.blocks_new_orders())
        kb.engage(ops.KILL_GLOBAL, "emergency")
        self.assertTrue(kb.any_engaged())

    def test_invalid_layer_refused(self):
        with self.assertRaises(ValueError):
            ops.KillSwitchBoard().engage("NOT_A_LAYER")


class TestCancelOnDisconnect(unittest.TestCase):
    def test_sequence_and_no_resume_without_reconciliation(self):
        c = ops.CancelOnDisconnect()
        self.assertIn("STOP_NEW_ORDERS", c.on_disconnect())
        self.assertEqual(c.on_reconnect(reconciliation_ok=False),
                         "REMAIN_HALTED (reconciliation unresolved)")
        c2 = ops.CancelOnDisconnect()
        c2.on_disconnect()
        self.assertEqual(c2.on_reconnect(reconciliation_ok=True),
                         "RESUME (post-reconciliation)")

    def test_uncancellable_broker_flagged(self):
        c = ops.CancelOnDisconnect(broker_supports_cancel=False)
        self.assertIn("FLAG_PENDING_UNCANCELLABLE", c.on_disconnect())


class TestReconciliation(unittest.TestCase):
    def _pos(self, **over):
        base = {"symbol": "GOLDmicro", "side": "BUY", "volume": 0.1,
                "price": 4400.0, "state": "open"}
        base.update(over)
        return base

    def test_clean(self):
        r = ops.reconcile({"1": self._pos()}, {"1": self._pos()}, {"1"})
        self.assertEqual(r["status"], "OK")
        self.assertFalse(r["block_new_orders"])

    def test_volume_mismatch_blocks(self):
        r = ops.reconcile({"1": self._pos()}, {"1": self._pos(volume=0.2)}, {"1"})
        self.assertEqual(r["status"], "RECONCILIATION_FAILED")
        self.assertTrue(r["block_new_orders"])

    def test_missing_and_orphan(self):
        r = ops.reconcile({}, {"1": self._pos()}, set())
        self.assertEqual(r["status"], "RECONCILIATION_FAILED")
        self.assertEqual(r["orphan_positions"], ["1"])


class TestDataPipeline(unittest.TestCase):
    def _session(self):
        s = dp.DataSession(session_id="S1", source="sim", broker="XM",
                           server="demo", symbol="GOLDmicro",
                           account_mode="SHADOW", started_at=dp._utc_now())
        base = 1_700_000_000_000
        for i in range(10):
            s.add_tick(dp.Tick(ts_ms=base + i * 1000, bid=4400.0 + i,
                               ask=4400.5 + i, seq=i))
        return s, base

    def test_raw_immutable_after_seal(self):
        s, _ = self._session()
        h = s.close()
        self.assertTrue(s.verify())
        with self.assertRaises(RuntimeError):
            s.add_tick(dp.Tick(1, 1.0, 1.5))

    def test_quality_flags_not_silent_repair(self):
        s, base = self._session()
        s.add_tick(dp.Tick(ts_ms=base, bid=4400.0, ask=4400.6))   # dup ts
        s.add_tick(dp.Tick(ts_ms=base - 5000, bid=1.0, ask=9.0))  # reg + spread
        flags = dp.check_quality(s)
        kinds = {f["kind"] for f in flags}
        self.assertIn("duplicate_timestamp", kinds)
        self.assertIn("timestamp_regression", kinds)
        self.assertIn("impossible_spread", kinds)

    def test_time_integrity(self):
        s, base = self._session()
        ti = dp.time_integrity(s.ticks)
        self.assertTrue(ti["monotonic"])
        self.assertEqual(ti["canonical"], "UTC (ms)")

    def test_execution_quality_distributions(self):
        ev = ([{"event_type": "ORDER_SUBMIT", "timestamp_ms": 100},
               {"event_type": "ORDER_FILLED", "timestamp_ms": 150},
               {"event_type": "ORDER_SUBMIT", "timestamp_ms": 200},
               {"event_type": "ORDER_REJECTED", "timestamp_ms": 400,
                "status": "TIMEOUT"},
               {"event_type": "ORDER_FILLED", "timestamp_ms": 460,
                "requested_lot": 0.2, "filled_lot": 0.1,
                "slippage": 0.3}])
        q = dp.execution_quality(ev)
        self.assertEqual(q["order_latency_ms"]["n"], 3)
        self.assertGreaterEqual(q["order_latency_ms"]["p95"],
                                q["order_latency_ms"]["p50"])
        self.assertEqual(q["rejections"], 1)
        self.assertEqual(q["partial_fills"], 1)


if __name__ == "__main__":
    unittest.main()
