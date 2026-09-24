"""Tests: cycle timeline + behavior verification report (Phase 2)."""
import unittest

from core.behavior_report import build_behavior_report
from core.cycle import (
    build_cycle_timeline,
    build_cycle_timelines,
)
from core.mt5_adapters import (
    BehaviorRecord,
    EVENT_ADD_GRID,
    EVENT_BASKET_CLOSE,
    EVENT_EMERGENCY,
    EVENT_OPEN_POSITION,
    EVENT_PARTIAL_CLOSE,
    EVENT_RESUME,
)
from core.observation import ObservationSession
from tests import std_ctx


def rec(**kw):
    return BehaviorRecord(**kw)


def full_cycle(start="2024.01.02 10:00:00", side="BUY"):
    return [
        rec(timestamp=start, event=EVENT_OPEN_POSITION, side=side,
            lot=0.10, price=2050.0, total_lots=0.10, position_count=1,
            equity=500.0, margin=41.0),
        rec(timestamp="2024.01.02 10:30:00", event=EVENT_ADD_GRID, side=side,
            lot=0.11, price=2045.0, total_lots=0.21, position_count=2,
            equity=470.0, margin=86.0, drawdown=6.0),
        rec(timestamp="2024.01.02 11:00:00", event=EVENT_BASKET_CLOSE, side=side,
            basket_pl=1.68, price=2048.0, total_lots=0.0, position_count=0,
            equity=501.68),
    ]


class TestCycleTimeline(unittest.TestCase):
    def test_complete_cycle(self):
        from core.cycle import build_cycles_from_records
        cycles = build_cycles_from_records(full_cycle())
        tl = build_cycle_timeline(cycles[0])
        self.assertEqual(tl["status"], "COMPLETE")
        self.assertEqual(tl["missing"], [])
        self.assertEqual(len(tl["rows"]), 3)
        row2 = tl["rows"][1]
        self.assertEqual(row2["seq"], 2)
        self.assertEqual(row2["total_lots"], 0.21)
        self.assertEqual(row2["equity"], 470.0)

    def test_incomplete_when_terminal_missing(self):
        from core.cycle import build_cycles_from_records
        rows = full_cycle()[:2]     # never closed
        cycles = build_cycles_from_records(rows)
        tl = build_cycle_timeline(cycles[0])
        self.assertEqual(tl["status"], "INCOMPLETE")
        self.assertIn("terminal event", tl["missing"])

    def test_incomplete_when_timestamps_missing(self):
        from core.cycle import build_cycles_from_records
        rows = [
            rec(event=EVENT_OPEN_POSITION, side="BUY", lot=0.1, price=2050.0),
            rec(event=EVENT_BASKET_CLOSE, side="BUY", basket_pl=1.68),
        ]
        cycles = build_cycles_from_records(rows)
        tl = build_cycle_timeline(cycles[0])
        self.assertEqual(tl["status"], "INCOMPLETE")
        self.assertIn("timestamps", tl["missing"])

    def test_emergency_cycle(self):
        from core.cycle import build_cycles_from_records
        rows = [
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY",
                lot=0.1, price=2000.0),
            rec(timestamp="t2", event=EVENT_EMERGENCY, side="BUY", price=1910.0),
        ]
        tl = build_cycle_timelines(rows)[0]
        self.assertEqual(tl["cycle_status"], "EMERGENCY_CLOSED")

    def test_resume_then_new_cycle(self):
        rows = full_cycle() + [
            rec(timestamp="2024.01.03 08:00:00", event=EVENT_RESUME),
        ] + full_cycle(start="2024.01.03 09:00:00")
        tls = build_cycle_timelines(rows)
        self.assertEqual(len(tls), 2)
        self.assertTrue(all(t["status"] == "COMPLETE" for t in tls))

    def test_never_fills_missing_events(self):
        from core.cycle import build_cycles_from_records
        rows = [rec(timestamp="t1", event=EVENT_ADD_GRID, side="BUY", lot=0.1)]
        cycles = build_cycles_from_records(rows)
        # ADD_GRID with no cycle starts one (first position semantics)
        tl = build_cycle_timeline(cycles[0])
        self.assertEqual(len(tl["rows"]), 1)     # nothing invented


class TestBehaviorReport(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def _session(self, events):
        return ObservationSession.new(symbol="XAUUSD", timeframe="M15",
                                      broker="XM Global", account_type="Hedge",
                                      source_type="MT5_CSV",
                                      parameters=self.cfg.to_dict(),
                                      events=events)

    def test_report_has_all_15_sections(self):
        rep = build_behavior_report(self._session(full_cycle()), self.prof, self.rules)
        for key in ("environment", "session", "parameters", "observed_events",
                    "grid_behavior", "lot_behavior", "buy_sell_behavior",
                    "basket_behavior", "partial_close", "emergency",
                    "cycle_timeline", "model_comparison", "mismatches",
                    "unknowns", "evidence", "assumptions"):
            self.assertIn(key, rep, f"missing section: {key}")
        self.assertEqual(rep["schema"], "SNIPER_BEHAVIOR_VERIFICATION_REPORT_V1")

    def test_parameters_section_shows_90_and_50(self):
        rep = build_behavior_report(self._session(full_cycle()), self.prof, self.rules)
        recs = rep["parameters"]["emergency_distance_records"]
        kinds = {r["kind"]: r["value"] for r in recs}
        self.assertEqual(kinds["OBSERVED VALUE"], 90.0)
        self.assertEqual(kinds["RECOMMENDED PRESET"], 50.0)

    def test_parameter_21_stays_unknown(self):
        rep = build_behavior_report(self._session(full_cycle()), self.prof, self.rules)
        p21 = rep["parameters"]["parameter_21"]
        self.assertEqual(p21["status"], "UNKNOWN")
        self.assertEqual(p21["mapping"], "UNVERIFIED CANDIDATE")

    def test_traceability(self):
        rep = build_behavior_report(self._session(full_cycle()), self.prof, self.rules)
        self.assertIn("session:", rep["evidence"]["ids"][0])
        self.assertTrue(rep["assumptions"]["ids"])
        self.assertTrue(rep["assumptions"]["details"])
        # every assumption id referenced exists in the registry
        for d in rep["assumptions"]["details"]:
            self.assertTrue(d.get("assumption_id"))

    def test_counts_consistent(self):
        rep = build_behavior_report(self._session(full_cycle()), self.prof, self.rules)
        counts = rep["model_comparison"]["counts"]
        self.assertEqual(rep["model_comparison"]["statuses_supported"],
                         ["MATCH", "PARTIAL_MATCH", "MISMATCH", "UNKNOWN",
                          "INSUFFICIENT_DATA"])
        self.assertIn("DISABLED", rep["model_comparison"]["auto_correction"])
        self.assertEqual(counts["MISMATCH"], len(rep["mismatches"]))

    def test_observed_events_summary(self):
        rows = full_cycle() + [rec(timestamp="t9", event=EVENT_PARTIAL_CLOSE,
                                   side="BUY", basket_pl=2.0, commission=-0.1)]
        rep = build_behavior_report(self._session(rows), self.prof, self.rules)
        self.assertEqual(rep["observed_events"]["total"], 4)
        self.assertEqual(rep["observed_events"]["by_event"]["BASKET_CLOSE"], 1)
        self.assertEqual(rep["observed_events"]["cost_fields_present"]["commission"], 1)

    def test_test_plans_included(self):
        rep = build_behavior_report(self._session([]), self.prof, self.rules)
        self.assertIn("TEST_A_LOT", rep["controlled_test_plans"])
        self.assertIn("TEST_F_EMERGENCY", rep["controlled_test_plans"])


if __name__ == "__main__":
    unittest.main()
