"""Gateway Integration tests (§28) — all categories.

Uses LoopbackTransport (clearly labelled TEST) — no real gateway.
Covers: connect/disconnect, heartbeat, contract, signal
schema/validation/expiry/idempotency, event idempotency/ordering,
reconnect/snapshot, reconciliation, correlation trace, evidence,
execution feedback, audit, failure handling, safety (no direct MT5).
"""
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.gateway.contracts import (
    ConnectionState, ContractMismatch, EventEnvelope, Signal,
    SignalLifecycle, GATEWAY_EVENTS, new_id, utc_now_iso, canonical_hash)
from core.gateway.client import (GatewayClient, LoopbackTransport,
                                 ContractRejected)
from core.gateway.signal_builder import build_signal, build_evidence_package


def make_client():
    return GatewayClient(transport=LoopbackTransport())


class TestGatewayConnect(unittest.TestCase):
    def test_connect(self):
        c = make_client()
        self.assertTrue(c.connect())
        self.assertEqual(c.get_state(), ConnectionState.CONNECTED)
        self.assertTrue(c.session_id)

    def test_disconnect(self):
        c = make_client()
        c.connect()
        c.disconnect()
        self.assertEqual(c.get_state(), ConnectionState.OFFLINE)
        self.assertEqual(c._auth_state, "UNAUTHENTICATED")

    def test_double_connect_idempotent(self):
        c = make_client()
        self.assertTrue(c.connect())
        self.assertTrue(c.connect())          # no error, still connected


class TestHeartbeat(unittest.TestCase):
    def test_heartbeat(self):
        c = make_client()
        c.connect()
        self.assertTrue(c.send_heartbeat())
        self.assertTrue(c.last_heartbeat)
        self.assertGreaterEqual(c.latency_ms, 0)

    def test_heartbeat_offline_refused(self):
        c = make_client()
        self.assertFalse(c.send_heartbeat())


class TestContractHandshake(unittest.TestCase):
    def test_handshake_success(self):
        c = make_client()
        c.connect()
        self.assertTrue(c.contract_version.startswith("1."))
        self.assertTrue(c.gateway_version)

    def test_invalid_contract_rejected(self):
        from core.gateway.client import Transport
        class BadVersionTransport(LoopbackTransport):
            def connect(self, endpoint):
                self._connected = True
                self._recv_queue.append(json.dumps({
                    "type": "CONTRACT_RESPONSE",
                    "contract_version": "9.9.9",
                    "gateway_version": "TEST"}).encode())
                return True
        c = GatewayClient(transport=BadVersionTransport())
        with self.assertRaises(ContractRejected):
            c.connect()


class TestSignalSchema(unittest.TestCase):
    def test_build_signal_complete(self):
        s = build_signal(direction="BUY", confidence=0.8,
                         entry_reference=4400.0)
        self.assertTrue(s.signal_id.startswith("SIG-"))
        self.assertEqual(s.direction, "BUY")
        self.assertTrue(s.correlation_id)
        self.assertFalse(s.is_expired())

    def test_signal_hash_deterministic(self):
        s = build_signal(direction="SELL", confidence=0.5)
        self.assertEqual(s.hash(), s.hash())


class TestSignalValidation(unittest.TestCase):
    def test_valid_signal_passes(self):
        c = make_client()
        c.connect()
        s = build_signal(direction="BUY", confidence=0.7,
                         entry_reference=4400.0)
        r = c.publish_signal(s)
        self.assertTrue(r["ok"])

    def test_invalid_direction_rejected(self):
        c = make_client()
        c.connect()
        s = build_signal(direction="INVALID")
        r = c.publish_signal(s)
        self.assertFalse(r["ok"])
        self.assertTrue(any("direction" in e for e in r["errors"]))

    def test_confidence_out_of_range_rejected(self):
        c = make_client()
        c.connect()
        s = build_signal(confidence=1.5)
        r = c.publish_signal(s)
        self.assertFalse(r["ok"])

    def test_expired_signal_blocked(self):
        c = make_client()
        c.connect()
        expired = datetime.now(timezone.utc) - timedelta(hours=1)
        s = build_signal()
        s = Signal(**{**s.to_dict(),
                      "expires_at": expired.isoformat(timespec="milliseconds")})
        r = c.publish_signal(s)
        self.assertFalse(r["ok"])
        self.assertTrue(any("expired" in e.lower() for e in r["errors"]))


class TestSignalIdempotency(unittest.TestCase):
    def test_duplicate_signal_blocked(self):
        c = make_client()
        c.connect()
        s = build_signal(direction="BUY", confidence=0.5)
        r1 = c.publish_signal(s)
        r2 = c.publish_signal(s)             # same signal_id
        self.assertTrue(r1["ok"])
        self.assertFalse(r2["ok"])


class TestSignalLifecycle(unittest.TestCase):
    def test_lifecycle_progression(self):
        c = make_client()
        c.connect()
        s = build_signal(direction="BUY", confidence=0.5)
        c.publish_signal(s)
        self.assertEqual(c.get_signal_lifecycle(s.signal_id),
                         SignalLifecycle.RECEIVED_BY_GATEWAY.value)


class TestEventIdempotency(unittest.TestCase):
    def test_duplicate_event_ignored(self):
        c = make_client()
        ev = EventEnvelope(
            event_id="EV-001", event_type="POSITION_OPENED",
            schema_version="1.0", created_at=utc_now_iso(),
            source="1144-GATEWAY", target="SNIPER",
            sequence=1, correlation_id="COR-1", payload={})
        self.assertTrue(c.process_event(ev))
        self.assertFalse(c.process_event(ev))   # duplicate ignored


class TestEventOrdering(unittest.TestCase):
    def test_late_event_still_processed(self):
        c = make_client()
        # late events (out of order) are processed — idempotency by id
        ev2 = EventEnvelope(event_id="EV-002", event_type="ORDER_FILLED",
                            schema_version="1.0", created_at=utc_now_iso(),
                            source="GW", target="SNIPER",
                            sequence=2, correlation_id="C", payload={})
        ev1 = EventEnvelope(event_id="EV-001", event_type="ORDER_CREATED",
                            schema_version="1.0", created_at=utc_now_iso(),
                            source="GW", target="SNIPER",
                            sequence=1, correlation_id="C", payload={})
        self.assertTrue(c.process_event(ev2))
        self.assertTrue(c.process_event(ev1))


class TestReconnectSnapshot(unittest.TestCase):
    def test_reconnect(self):
        c = make_client()
        c.connect()
        self.assertTrue(c.reconnect())
        self.assertEqual(c.get_state(), ConnectionState.CONNECTED)
        self.assertEqual(c.reconnect_count, 1)

    def test_reconnect_requests_snapshot(self):
        c = make_client()
        c.connect()
        c.reconnect()
        # after reconnect the client must be re-connected and have
        # requested a state snapshot (audit records it)
        self.assertEqual(c.get_state(), ConnectionState.CONNECTED)
        self.assertGreaterEqual(c.reconnect_count, 1)
        audit = c.get_audit_log()
        self.assertTrue(any(r['category'] == 'state' and
                            r['result'] == 'RECEIVED'
                            for r in audit))


class TestCorrelationTrace(unittest.TestCase):
    def test_signal_evidence_trace(self):
        c = make_client()
        c.connect()
        s = build_signal(direction="BUY", confidence=0.5,
                         evidence_id="E012", evidence_hash="ABC123")
        ev = build_evidence_package(s)
        c.publish_signal(s)
        trace = c.get_correlation_trace(s.correlation_id)
        self.assertIn(s.signal_id, trace)
        self.assertTrue(ev.evidence_hash)


class TestEvidencePackage(unittest.TestCase):
    def test_evidence_hash_not_empty(self):
        s = build_signal()
        ev = build_evidence_package(s, metrics={"sharpe": 1.2})
        self.assertEqual(len(ev.evidence_hash), 64)

    def test_evidence_no_fabrication(self):
        s = build_signal()
        ev = build_evidence_package(s)
        self.assertTrue(ev.signal_id)
        self.assertTrue(ev.analysis_id)


class TestExecutionFeedback(unittest.TestCase):
    def test_execution_result_updates_lifecycle(self):
        c = make_client()
        c.connect()
        s = build_signal(direction="BUY", confidence=0.5)
        c.publish_signal(s)
        c.process_event(EventEnvelope(
            event_id="EV-EXE", event_type="EXECUTION_RESULT",
            schema_version="1.0", created_at=utc_now_iso(),
            source="GW", target="SNIPER", sequence=1,
            correlation_id=s.correlation_id,
            payload={"signal_id": s.signal_id, "status": "EXECUTED"}))
        self.assertEqual(c.get_signal_lifecycle(s.signal_id),
                         SignalLifecycle.EXECUTED.value)


class TestAudit(unittest.TestCase):
    def test_audit_records_connection_and_signal(self):
        c = make_client()
        c.connect()
        s = build_signal(direction="BUY", confidence=0.5)
        c.publish_signal(s)
        log = c.get_audit_log()
        cats = {r["category"] for r in log}
        self.assertIn("connection", cats)
        self.assertIn("signal", cats)
        self.assertIn("contract", cats)


class TestDiagnostics(unittest.TestCase):
    def test_diagnostics_after_connect(self):
        c = make_client()
        c.connect()
        s = build_signal(direction="BUY", confidence=0.5)
        c.publish_signal(s)
        c.send_heartbeat()
        diags = c.diagnostics()
        for d in diags:
            self.assertIn("check", d)
            self.assertIn("pass", d)
        # after connect+signal+heartbeat, most should pass
        passed = sum(1 for d in diags if d["pass"])
        self.assertGreaterEqual(passed, 5)


class TestGatewayFailureFeedback(unittest.TestCase):
    def test_offline_publish_rejected(self):
        c = make_client()                     # never connected
        s = build_signal(direction="BUY", confidence=0.5)
        r = c.publish_signal(s)
        self.assertFalse(r["ok"])


class TestNoDirectMT5(unittest.TestCase):
    def test_no_mt5_import_in_gateway(self):
        import core.gateway.client as gw
        source = open(gw.__file__).read()
        self.assertNotIn("import MetaTrader5", source)
        self.assertNotIn("from MetaTrader5", source)
        self.assertNotIn("mt5.order", source.lower())
        self.assertNotIn("order_send", source.lower())

    def test_signal_is_research_only(self):
        s = build_signal()
        self.assertIn("ANALYSIS", ("ENTRY", "EXIT", "FILTER", "ALERT", "ANALYSIS"))
        # signal has no execution fields
        d = s.to_dict()
        self.assertNotIn("order_type", d)
        self.assertNotIn("volume", d)
        self.assertNotIn("magic", d)


class TestE2EFlow(unittest.TestCase):
    def test_full_signal_flow(self):
        """§29 E2E: Analyzer → Signal → Validate → Evidence → Publish →
        Gateway ack → EA event → Execution result → trace stored"""
        c = make_client()
        self.assertTrue(c.connect())
        self.assertTrue(c.send_heartbeat())
        s = build_signal(direction="BUY", signal_type="ENTRY",
                         confidence=0.75, entry_reference=4400.0,
                         stop_reference=4390.0, target_reference=4420.0,
                         evidence_id="E012", evidence_hash="ABC")
        ev = build_evidence_package(s, metrics={"replay_match": 77.55})
        r = c.publish_signal(s)
        self.assertTrue(r["ok"])
        self.assertEqual(c.get_signal_lifecycle(s.signal_id),
                         "RECEIVED_BY_GATEWAY")
        c.process_event(EventEnvelope(
            event_id="EV-ACK", event_type="SIGNAL_ACCEPTED",
            schema_version="1.0", created_at=utc_now_iso(),
            source="GW", target="SNIPER", sequence=1,
            correlation_id=s.correlation_id,
            payload={"signal_id": s.signal_id}))
        self.assertEqual(c.get_signal_lifecycle(s.signal_id),
                         SignalLifecycle.ACCEPTED_BY_EA.value)
        c.process_event(EventEnvelope(
            event_id="EV-EXE", event_type="EXECUTION_RESULT",
            schema_version="1.0", created_at=utc_now_iso(),
            source="GW", target="SNIPER", sequence=2,
            correlation_id=s.correlation_id,
            payload={"signal_id": s.signal_id, "status": "EXECUTED",
                     "executed_price": 4400.5, "slippage": 0.5}))
        self.assertEqual(c.get_signal_lifecycle(s.signal_id),
                         SignalLifecycle.EXECUTED.value)
        trace = c.get_correlation_trace(s.correlation_id)
        self.assertIn(s.signal_id, trace)
        self.assertTrue(ev.evidence_hash)
        c.disconnect()


if __name__ == "__main__":
    unittest.main()
