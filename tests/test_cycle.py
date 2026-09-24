"""Tests: cycle lifecycle model + cycle verification checks (Phase 1)."""
import unittest

from core.cycle import (
    CLOSED,
    CYCLE_END_RULE,
    CYCLE_START_RULE,
    EMERGENCY_CLOSED,
    OPEN,
    UNKNOWN,
    Cycle,
    build_cycles_from_records,
    model_cycle,
)
from core.model_vs_observed import (
    check_cycle_end,
    check_cycle_start,
    check_emergency_close,
    check_resume_new_cycle,
    MATCH,
    MISMATCH,
    UNKNOWN as CMP_UNKNOWN,
)
from core.mt5_adapters import (
    BehaviorRecord,
    EVENT_ADD_GRID,
    EVENT_BASKET_CLOSE,
    EVENT_EMERGENCY,
    EVENT_NEW_CYCLE,
    EVENT_OPEN_POSITION,
    EVENT_PARTIAL_CLOSE,
    EVENT_RESUME,
)
from tests import std_ctx


def rec(**kw):
    return BehaviorRecord(**kw)


class TestCycleBuilder(unittest.TestCase):
    def test_start_with_marker_then_positions(self):
        cycles = build_cycles_from_records([
            rec(timestamp="t1", event=EVENT_NEW_CYCLE, side="BUY", symbol="XAUUSD"),
            rec(timestamp="t2", event=EVENT_OPEN_POSITION, side="BUY",
                lot=0.1, price=2000.0, total_lots=0.1),
            rec(timestamp="t3", event=EVENT_ADD_GRID, side="BUY",
                lot=0.11, price=1995.0, total_lots=0.21),
        ])
        self.assertEqual(len(cycles), 1)          # marker does NOT split the cycle
        c = cycles[0]
        self.assertEqual(c.grid_levels, 2)
        self.assertEqual(c.initial_lot, 0.1)
        self.assertEqual(c.total_lots, 0.21)
        self.assertEqual(c.start_price, 2000.0)
        self.assertEqual(c.status, OPEN)          # window ended before terminal

    def test_basket_close_ends_cycle(self):
        cycles = build_cycles_from_records([
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY", lot=0.1, price=2000.0),
            rec(timestamp="t2", event=EVENT_ADD_GRID, side="BUY", lot=0.11, price=1995.0),
            rec(timestamp="t3", event=EVENT_BASKET_CLOSE, side="BUY", basket_pl=1.68),
        ])
        self.assertEqual(cycles[0].status, CLOSED)
        self.assertEqual(cycles[0].close_reason, EVENT_BASKET_CLOSE)
        self.assertEqual(cycles[0].basket_profit, 1.68)

    def test_emergency_close(self):
        cycles = build_cycles_from_records([
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY", lot=0.1),
            rec(timestamp="t2", event=EVENT_EMERGENCY, side="BUY", floating_pl=-500.0),
        ])
        self.assertEqual(cycles[0].status, EMERGENCY_CLOSED)
        self.assertEqual(cycles[0].floating_profit, -500.0)

    def test_partial_does_not_close(self):
        cycles = build_cycles_from_records([
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY", lot=0.2),
            rec(timestamp="t2", event=EVENT_PARTIAL_CLOSE, side="BUY", basket_pl=2.0),
        ])
        self.assertEqual(cycles[0].status, OPEN)     # partial is not terminal
        self.assertEqual(cycles[0].realized_profit, 2.0)

    def test_superseded_without_terminal_is_unknown(self):
        cycles = build_cycles_from_records([
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY", lot=0.1),
            rec(timestamp="t2", event=EVENT_OPEN_POSITION, side="BUY", lot=0.1),
        ])
        self.assertEqual(cycles[0].status, UNKNOWN)
        self.assertEqual(cycles[1].status, OPEN)

    def test_multiple_full_cycles(self):
        cycles = build_cycles_from_records([
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY", lot=0.1),
            rec(timestamp="t2", event=EVENT_BASKET_CLOSE, side="BUY", basket_pl=1.0),
            rec(timestamp="t3", event=EVENT_OPEN_POSITION, side="SELL", lot=0.1),
            rec(timestamp="t4", event=EVENT_BASKET_CLOSE, side="SELL", basket_pl=1.0),
        ])
        self.assertEqual([c.status for c in cycles], [CLOSED, CLOSED])
        self.assertEqual(cycles[0].direction, "BUY")
        self.assertEqual(cycles[1].direction, "SELL")

    def test_events_before_any_start_ignored(self):
        cycles = build_cycles_from_records([
            rec(timestamp="t0", event=EVENT_RESUME),
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY", lot=0.1),
        ])
        self.assertEqual(len(cycles), 1)


class TestModelCycle(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_model_snapshot_from_core_calculations(self):
        c = model_cycle(self.cfg, self.prof, self.rules, "BUY", 5)
        self.assertEqual(c.source, "model")
        self.assertEqual(c.grid_levels, 5)
        self.assertEqual(c.initial_lot, 0.1)
        self.assertAlmostEqual(c.total_lots, 0.60)
        self.assertIn("MODEL", c.notes)
        self.assertEqual(len(c.events), 5)


class TestCycleVerificationChecks(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def _full_cycle_records(self, with_marker=True):
        rows = []
        if with_marker:
            rows.append(rec(timestamp="t1", event=EVENT_NEW_CYCLE, side="BUY"))
        rows += [
            rec(timestamp="t2", event=EVENT_OPEN_POSITION, side="BUY",
                lot=0.1, price=2050.0),
            rec(timestamp="t3", event=EVENT_ADD_GRID, side="BUY",
                lot=0.11, price=2045.0),
            rec(timestamp="t4", event=EVENT_BASKET_CLOSE, side="BUY",
                basket_pl=1.68),
        ]
        return rows

    def test_cycle_start_match_with_aligned_marker(self):
        r = check_cycle_start(self._full_cycle_records(), self.cfg)
        self.assertEqual(r.result, MATCH)

    def test_cycle_start_unknown_without_markers(self):
        r = check_cycle_start(self._full_cycle_records(with_marker=False), self.cfg)
        self.assertEqual(r.result, CMP_UNKNOWN)

    def test_cycle_start_mismatch_when_dangling_marker(self):
        # a NEW_CYCLE marker after the basket close never becomes a real
        # cycle start (no position follows) -> marker not aligned
        rows = self._full_cycle_records(with_marker=False)
        rows.append(rec(timestamp="t9", event=EVENT_NEW_CYCLE, side="BUY"))
        r = check_cycle_start(rows, self.cfg)
        self.assertEqual(r.result, MISMATCH)

    def test_cycle_end_match(self):
        r = check_cycle_end(self._full_cycle_records(), self.cfg)
        self.assertEqual(r.result, MATCH)

    def test_cycle_end_unknown_when_never_closed(self):
        rows = [rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY", lot=0.1)]
        r = check_cycle_end(rows, self.cfg)
        self.assertEqual(r.result, CMP_UNKNOWN)

    def test_cycle_end_mismatch_on_superseded(self):
        rows = [
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY", lot=0.1),
            rec(timestamp="t2", event=EVENT_OPEN_POSITION, side="BUY", lot=0.1),
            rec(timestamp="t3", event=EVENT_BASKET_CLOSE, side="BUY", basket_pl=1.0),
        ]
        r = check_cycle_end(rows, self.cfg)
        self.assertEqual(r.result, MISMATCH)

    def test_emergency_disabled_and_none_observed_matches(self):
        self.cfg.EnableEmergencyStop = False
        r = check_emergency_close(self._full_cycle_records(), self.cfg)
        self.assertEqual(r.result, MATCH)

    def test_emergency_observed_while_disabled_mismatches(self):
        self.cfg.EnableEmergencyStop = False
        rows = self._full_cycle_records() + \
            [rec(timestamp="t9", event=EVENT_EMERGENCY, side="BUY")]
        r = check_emergency_close(rows, self.cfg)
        self.assertEqual(r.result, MISMATCH)

    def test_emergency_enabled_but_unobserved_unknown(self):
        self.cfg.EnableEmergencyStop = True
        r = check_emergency_close([], self.cfg)
        self.assertEqual(r.result, CMP_UNKNOWN)

    def test_resume_unknown_with_single_cycle(self):
        r = check_resume_new_cycle(self._full_cycle_records(), self.cfg)
        self.assertEqual(r.result, CMP_UNKNOWN)

    def test_resume_match_when_cycles_close_in_order(self):
        rows = self._full_cycle_records() + self._full_cycle_records()
        r = check_resume_new_cycle(rows, self.cfg)
        self.assertEqual(r.result, MATCH)

    def test_resume_mismatch_on_superseded(self):
        rows = [
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY", lot=0.1),
            rec(timestamp="t2", event=EVENT_OPEN_POSITION, side="BUY", lot=0.1),
            rec(timestamp="t3", event=EVENT_BASKET_CLOSE, side="BUY", basket_pl=1.0),
            rec(timestamp="t4", event=EVENT_BASKET_CLOSE, side="BUY", basket_pl=1.0),
        ]
        r = check_resume_new_cycle(rows, self.cfg)
        self.assertEqual(r.result, MISMATCH)

    def test_rules_are_labeled_model_not_verified(self):
        self.assertIn("MODEL", CYCLE_START_RULE)
        self.assertIn("NOT VERIFIED INTERNAL EA BEHAVIOR", CYCLE_START_RULE)
        self.assertIn("NOT VERIFIED INTERNAL EA BEHAVIOR", CYCLE_END_RULE)


class TestCycleSerialization(unittest.TestCase):
    def test_to_dict_schema(self):
        c = Cycle(cycle_id="C1", status=OPEN)
        d = c.to_dict()
        self.assertEqual(d["schema"], "SNIPER_CYCLE_V1")
        for key in ("cycle_id", "start_time", "end_time", "symbol", "direction",
                    "start_price", "end_price", "initial_lot", "total_lots",
                    "grid_levels", "basket_profit", "realized_profit",
                    "floating_profit", "status"):
            self.assertIn(key, d)


if __name__ == "__main__":
    unittest.main()
