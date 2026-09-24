"""Tests: model vs observed comparison (Modules 10 & 14) + rule fitting."""
import unittest

from core.model_vs_observed import (
    compare_behavior, check_grid_spacing, check_lot_progression,
    check_basket_close, check_partial_close, suggest_lot_rule_from_observed,
    MATCH, MISMATCH, UNKNOWN,
)
from core.mt5_adapters import BehaviorRecord, EVENT_ADD_GRID, EVENT_OPEN_POSITION, \
    EVENT_BASKET_CLOSE
from tests import std_ctx


def _matching_records():
    """Observations that match the default simulation model exactly:
    buy grid, step 5.0, lots 0.1/0.11/0.12."""
    return [
        BehaviorRecord(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY",
                       grid_level=1, lot=0.10, price=2050.0),
        BehaviorRecord(timestamp="t2", event=EVENT_ADD_GRID, side="BUY",
                       grid_level=2, lot=0.11, price=2045.0),
        BehaviorRecord(timestamp="t3", event=EVENT_ADD_GRID, side="BUY",
                       grid_level=3, lot=0.12, price=2040.0),
        BehaviorRecord(timestamp="t4", event=EVENT_BASKET_CLOSE, side="BUY",
                       basket_pl=1.68),
    ]


def _mismatching_records():
    return [
        BehaviorRecord(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY",
                       grid_level=1, lot=0.10, price=2050.0),
        BehaviorRecord(timestamp="t2", event=EVENT_ADD_GRID, side="BUY",
                       grid_level=2, lot=0.30, price=2040.0),   # wrong spacing AND lot
        BehaviorRecord(timestamp="t3", event=EVENT_ADD_GRID, side="BUY",
                       grid_level=3, lot=0.50, price=2030.0),
    ]


class TestChecks(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_spacing_match(self):
        res = check_grid_spacing(_matching_records(), self.cfg)
        self.assertEqual(res.result, MATCH)

    def test_spacing_mismatch(self):
        res = check_grid_spacing(_mismatching_records(), self.cfg)
        self.assertEqual(res.result, MISMATCH)

    def test_spacing_unknown_when_no_data(self):
        res = check_grid_spacing([], self.cfg)
        self.assertEqual(res.result, UNKNOWN)

    def test_lot_progression_match(self):
        res = check_lot_progression(_matching_records(), self.cfg, self.rules, self.prof)
        self.assertEqual(res.result, MATCH)

    def test_lot_progression_mismatch(self):
        res = check_lot_progression(_mismatching_records(), self.cfg, self.rules, self.prof)
        self.assertEqual(res.result, MISMATCH)

    def test_basket_close_match(self):
        res = check_basket_close(_matching_records(), self.cfg)
        self.assertEqual(res.result, MATCH)

    def test_basket_close_mismatch_wrong_level(self):
        recs = [BehaviorRecord(event=EVENT_BASKET_CLOSE, basket_pl=9.9)]
        res = check_basket_close(recs, self.cfg)
        self.assertEqual(res.result, MISMATCH)

    def test_partial_close_unknown_when_enabled_but_not_seen(self):
        res = check_partial_close([], self.cfg)
        self.assertEqual(res.result, UNKNOWN)

    def test_full_report_counts(self):
        report = compare_behavior(_matching_records(), self.cfg, self.prof, self.rules)
        self.assertGreaterEqual(report.match_count, 2)
        self.assertEqual(report.mismatch_count, 0)
        d = report.to_dict()
        self.assertIn("overall", d)
        # Phase 1: comparator extended from 6 to 10 checks
        # (+ cycle start, cycle end, emergency close, resume/new cycle)
        self.assertEqual(len(d["checks"]), 10)
        names = [c["check"] for c in d["checks"]]
        self.assertIn("Cycle start", names)
        self.assertIn("Cycle end", names)
        self.assertIn("Emergency close", names)
        self.assertIn("Resume / new cycle", names)


class TestRuleFitting(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_geometric_fit_recognized(self):
        # 10 rounded geometric levels: curvature separates GEOMETRIC from
        # ARITHMETIC/FLAT clearly
        lots = [0.10, 0.11, 0.12, 0.13, 0.15, 0.16, 0.18, 0.19, 0.21, 0.24]
        recs = [BehaviorRecord(
            event=EVENT_OPEN_POSITION if i == 0 else EVENT_ADD_GRID,
            side="BUY", grid_level=i + 1, lot=lots[i], price=2050 - 5 * i)
            for i in range(len(lots))]
        suggestion = suggest_lot_rule_from_observed(recs, self.prof)
        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion["best_rule"], "GEOMETRIC")
        self.assertAlmostEqual(suggestion["candidates"]["GEOMETRIC"]["multiplier"],
                               1.1, delta=0.01)

    def test_three_points_are_genuinely_ambiguous(self):
        # 3 near-collinear rounded points: ARITHMETIC fits at least as well -
        # the fitter must NOT overclaim GEOMETRIC from this little data
        suggestion = suggest_lot_rule_from_observed(_matching_records(), self.prof)
        self.assertIn(suggestion["best_rule"], ("ARITHMETIC", "GEOMETRIC"))
        self.assertLessEqual(
            suggestion["candidates"]["ARITHMETIC"]["mae"],
            suggestion["candidates"]["GEOMETRIC"]["mae"] + 1e-12)

    def test_insufficient_data_returns_none(self):
        self.assertIsNone(suggest_lot_rule_from_observed([], self.prof))

    def test_flat_data_fits_flat(self):
        recs = [BehaviorRecord(event=EVENT_OPEN_POSITION if i == 0 else EVENT_ADD_GRID,
                               side="BUY", grid_level=i + 1, lot=0.1, price=2050 - 5 * i)
                for i in range(5)]
        s = suggest_lot_rule_from_observed(recs, self.prof)
        self.assertEqual(s["best_rule"], "FLAT")


if __name__ == "__main__":
    unittest.main()
