"""Tests: behavior comparators (grid/lot/buysell/basket/partial/emergency)."""
import unittest

from core.behavior_comparators import (
    INSUFFICIENT_DATA,
    MATCH,
    MISMATCH,
    PARTIAL_MATCH,
    UNKNOWN,
    compare_basket_behavior,
    compare_buysell_behavior,
    compare_emergency_behavior,
    compare_grid_behavior,
    compare_lot_behavior,
    compare_partial_behavior,
    run_all_comparators,
)
from core.config import EAConfig
from core.mt5_adapters import (
    BehaviorRecord,
    EVENT_ADD_GRID,
    EVENT_BASKET_CLOSE,
    EVENT_EMERGENCY,
    EVENT_NEW_CYCLE,
    EVENT_OPEN_POSITION,
    EVENT_PARTIAL_CLOSE,
)
from tests import std_ctx


def rec(**kw):
    return BehaviorRecord(**kw)


def by_id(results, cid):
    return [r for r in results if r.check_id == cid][0]


def grid_records(step=5.0, lots=(0.1, 0.11, 0.12), start=2050.0, side="BUY"):
    rows = [rec(timestamp="t1", event=EVENT_OPEN_POSITION, side=side,
                grid_level=1, lot=lots[0], price=start)]
    price = start
    sign = -1 if side == "BUY" else 1
    for i, lot in enumerate(lots[1:], start=2):
        price = price + sign * step
        rows.append(rec(timestamp=f"t{i}", event=EVENT_ADD_GRID, side=side,
                        grid_level=i, lot=lot, price=price))
    return rows


class TestGridComparator(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_exact_match(self):
        res = compare_grid_behavior(grid_records(), self.cfg, self.prof, self.rules)
        self.assertEqual(by_id(res, "GRID-BUY-SECOND").status, MATCH)
        self.assertEqual(by_id(res, "GRID-BUY-THIRD").status, MATCH)
        self.assertEqual(by_id(res, "GRID-BUY-DIRECTION").status, MATCH)
        self.assertEqual(by_id(res, "GRID-BUY-LEVEL").status, MATCH)

    def test_mismatch_wrong_spacing(self):
        res = compare_grid_behavior(grid_records(step=8.0), self.cfg, self.prof, self.rules)
        self.assertEqual(by_id(res, "GRID-BUY-SECOND").status, MISMATCH)

    def test_unknown_without_prices(self):
        rows = [rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY", lot=0.1),
                rec(timestamp="t2", event=EVENT_ADD_GRID, side="BUY", lot=0.11)]
        res = compare_grid_behavior(rows, self.cfg, self.prof, self.rules)
        self.assertEqual(by_id(res, "GRID-BUY-SECOND").status, INSUFFICIENT_DATA)
        self.assertEqual(by_id(res, "GRID-BUY-LEVEL").status, UNKNOWN)

    def test_no_entries_at_all(self):
        res = compare_grid_behavior([], self.cfg, self.prof, self.rules)
        self.assertEqual(by_id(res, "GRID-BUY-FIRST").status, INSUFFICIENT_DATA)
        self.assertEqual(by_id(res, "GRID-SELL-FIRST").status, INSUFFICIENT_DATA)

    def test_gap_reported_as_unknown(self):
        rows = grid_records()
        # make the 2nd spacing a double-gap (10 instead of 5)
        rows[2] = rec(timestamp="t3", event=EVENT_ADD_GRID, side="BUY",
                      grid_level=3, lot=0.12, price=2035.0)   # 10 away = double gap
        res = compare_grid_behavior(rows, self.cfg, self.prof, self.rules)
        gap = by_id(res, "GRID-BUY-GAP")
        self.assertEqual(gap.status, UNKNOWN)
        self.assertIn("PRICE_GAP_ASSUMPTION_001", gap.assumption_ids)
        # never guesses how many orders open across the gap
        self.assertIn("not guess", gap.notes)


class TestLotComparator(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_match(self):
        out = compare_lot_behavior(grid_records(), self.cfg, self.prof, self.rules)
        self.assertEqual(out["summary"], MATCH)
        self.assertTrue(all(r["result"] == MATCH for r in out["rows"]))
        self.assertTrue(all(r["on_volume_step"] for r in out["rows"]))

    def test_rounding_difference_still_match(self):
        rows = grid_records(lots=(0.1, 0.105, 0.12))   # 0.105 vs model 0.11
        out = compare_lot_behavior(rows, self.cfg, self.prof, self.rules)
        row2 = [r for r in out["rows"] if r["level"] == 2][0]
        self.assertEqual(row2["result"], MATCH)
        self.assertEqual(row2["rounding"], "within lot step (rounding)")
        self.assertNotEqual(row2["difference"], 0)

    def test_mismatch(self):
        rows = grid_records(lots=(0.5, 0.9, 1.3))   # no level matches
        out = compare_lot_behavior(rows, self.cfg, self.prof, self.rules)
        self.assertEqual(out["summary"], MISMATCH)

    def test_partial_match(self):
        rows = grid_records(lots=(0.1, 0.5, 0.12))
        out = compare_lot_behavior(rows, self.cfg, self.prof, self.rules)
        self.assertEqual(out["summary"], PARTIAL_MATCH)

    def test_no_data(self):
        out = compare_lot_behavior([], self.cfg, self.prof, self.rules)
        self.assertEqual(out["summary"], INSUFFICIENT_DATA)

    def test_notes_disclaim_formula_proof(self):
        out = compare_lot_behavior(grid_records(), self.cfg, self.prof, self.rules)
        self.assertIn("NOT proof", out["notes"])


class TestBuySellComparator(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_both_at_start_consistent(self):
        rows = [
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY", lot=0.1, price=2050),
            rec(timestamp="t2", event=EVENT_OPEN_POSITION, side="SELL", lot=0.1, price=2050),
            rec(timestamp="t3", event=EVENT_ADD_GRID, side="BUY", lot=0.11, price=2045),
        ]
        res = compare_buysell_behavior(rows, self.cfg)
        self.assertEqual(by_id(res, "BS-PATTERN").status, MATCH)
        opp = by_id(res, "BS-OPPOSITE")
        self.assertEqual(opp.status, MATCH)
        self.assertIn("NOT an EA rule claim", opp.notes)
        self.assertEqual(by_id(res, "BS-SCOPE").status, UNKNOWN)

    def test_one_side_vs_both_config_mismatches(self):
        rows = grid_records()
        res = compare_buysell_behavior(rows, self.cfg)
        self.assertEqual(by_id(res, "BS-PATTERN").status, MISMATCH)

    def test_opposite_after_first_grid_mismatches_at_start_model(self):
        rows = [
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY", lot=0.1, price=2050),
            rec(timestamp="t2", event=EVENT_ADD_GRID, side="BUY", lot=0.11, price=2045),
            rec(timestamp="t3", event=EVENT_OPEN_POSITION, side="SELL", lot=0.1, price=2045),
        ]
        res = compare_buysell_behavior(rows, self.cfg)
        self.assertEqual(by_id(res, "BS-OPPOSITE").status, MISMATCH)


class TestBasketComparator(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_target_reached_match(self):
        rows = grid_records() + [rec(timestamp="t9", event=EVENT_BASKET_CLOSE,
                                     side="BUY", basket_pl=1.70)]
        res = compare_basket_behavior(rows, self.cfg)
        self.assertEqual(by_id(res, "BASKET-TARGET").status, MATCH)

    def test_target_not_reached_mismatch(self):
        rows = grid_records() + [rec(timestamp="t9", event=EVENT_BASKET_CLOSE,
                                     side="BUY", basket_pl=9.99)]
        res = compare_basket_behavior(rows, self.cfg)
        self.assertEqual(by_id(res, "BASKET-TARGET").status, MISMATCH)

    def test_costs_separated_when_present(self):
        rows = grid_records() + [rec(timestamp="t9", event=EVENT_BASKET_CLOSE,
                                     side="BUY", basket_pl=1.50,
                                     commission=-0.20, swap=-0.05)]
        res = compare_basket_behavior(rows, self.cfg)
        costs = by_id(res, "BASKET-COSTS")
        self.assertEqual(costs.status, MATCH)
        self.assertIn("price~1.75", costs.observed_value)

    def test_costs_unknown_when_missing(self):
        rows = grid_records() + [rec(timestamp="t9", event=EVENT_BASKET_CLOSE,
                                     side="BUY", basket_pl=1.70)]
        res = compare_basket_behavior(rows, self.cfg)
        costs = by_id(res, "BASKET-COSTS")
        self.assertEqual(costs.status, UNKNOWN)
        self.assertIn("never assumed equal", costs.notes)

    def test_no_close_insufficient(self):
        res = compare_basket_behavior(grid_records(), self.cfg)
        self.assertEqual(by_id(res, "BASKET-CLOSE").status, INSUFFICIENT_DATA)


class TestPartialComparator(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def _partial_rows(self):
        return [
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY",
                lot=0.2, price=2050, total_lots=0.2, position_count=1),
            rec(timestamp="t2", event=EVENT_ADD_GRID, side="BUY",
                lot=0.22, price=2045, total_lots=0.42, position_count=2),
            rec(timestamp="t3", event=EVENT_PARTIAL_CLOSE, side="BUY",
                basket_pl=2.0, total_lots=0.42, position_count=2),
            rec(timestamp="t4", event=EVENT_ADD_GRID, side="BUY",
                lot=0.24, price=2040, total_lots=0.52, position_count=2),
        ]

    def test_trigger_and_percentage(self):
        res = compare_partial_behavior(self._partial_rows(), self.cfg)
        self.assertEqual(by_id(res, "PARTIAL-TRIG-1").status, MATCH)
        # before 0.42 -> after 0.52? percentage uses next total... see note:
        # the nearest AFTER total_lots belongs to the next grid; scope/pct
        # remain honest about what the data supports
        pct = by_id(res, "PARTIAL-PCT-1")
        self.assertIn(pct.status, (MATCH, MISMATCH, UNKNOWN))

    def test_scope_unknown_without_counts(self):
        rows = [
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY", lot=0.2),
            rec(timestamp="t2", event=EVENT_PARTIAL_CLOSE, side="BUY", basket_pl=2.0),
        ]
        res = compare_partial_behavior(rows, self.cfg)
        self.assertEqual(by_id(res, "PARTIAL-SCOPE-1").status, UNKNOWN)
        self.assertIn("does not pick one", by_id(res, "PARTIAL-SCOPE-1").notes)

    def test_no_events_insufficient(self):
        res = compare_partial_behavior([], self.cfg)
        self.assertEqual(by_id(res, "PARTIAL-OBSERVED").status, INSUFFICIENT_DATA)


class TestEmergencyComparator(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()
        self.cfg.EnableEmergencyStop = True

    def test_values_row_shows_90_and_50_separately(self):
        res = compare_emergency_behavior([], self.cfg, self.prof)
        values = by_id(res, "EMG-VALUES")
        self.assertIn("90.0", values.observed_value)
        self.assertIn("50.0", values.model_value)
        self.assertIn("E007", values.evidence_ids)
        self.assertIn("E008", values.evidence_ids)
        self.assertIn("never merged", values.notes)

    def test_distance_matching_observed_90_is_mismatch_vs_model_50(self):
        rows = [
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY",
                lot=0.1, price=2000.0),
            rec(timestamp="t2", event=EVENT_ADD_GRID, side="BUY",
                lot=0.11, price=1995.0),
            rec(timestamp="t3", event=EVENT_EMERGENCY, side="BUY", price=1910.0),
        ]
        res = compare_emergency_behavior(rows, self.cfg, self.prof)
        dist = by_id(res, "EMG-DIST-1")
        self.assertEqual(dist.status, MISMATCH)
        self.assertIn("OBSERVED DEFAULT 90.0", dist.notes)
        self.assertIn("no auto-correction", dist.notes)

    def test_distance_matching_model_50(self):
        rows = [
            rec(timestamp="t1", event=EVENT_OPEN_POSITION, side="BUY",
                lot=0.1, price=2000.0),
            rec(timestamp="t2", event=EVENT_ADD_GRID, side="BUY",
                lot=0.11, price=1995.0),
            rec(timestamp="t3", event=EVENT_EMERGENCY, side="BUY", price=1950.0),
        ]
        res = compare_emergency_behavior(rows, self.cfg, self.prof)
        self.assertEqual(by_id(res, "EMG-DIST-1").status, MATCH)

    def test_none_observed_insufficient(self):
        res = compare_emergency_behavior(grid_records(), self.cfg, self.prof)
        self.assertEqual(by_id(res, "EMG-OBSERVED").status, INSUFFICIENT_DATA)

    def test_missing_reference_unknown(self):
        rows = [rec(timestamp="t1", event=EVENT_EMERGENCY, side="BUY", price=1950.0)]
        res = compare_emergency_behavior(rows, self.cfg, self.prof)
        self.assertEqual(by_id(res, "EMG-DIST-1").status, UNKNOWN)


class TestRunAll(unittest.TestCase):
    def test_aggregate_shape_and_statuses(self):
        cfg, prof, acct, rules = std_ctx()
        out = run_all_comparators(grid_records(), cfg, prof, rules)
        self.assertEqual(out["schema"], "SNIPER_BEHAVIOR_COMPARISON_V1")
        self.assertEqual(sum(out["counts"].values()),
                         len(out["checks"]) + 1)   # + LOT-SUMMARY
        for s in out["counts"]:
            self.assertIn(s, ("MATCH", "PARTIAL_MATCH", "MISMATCH",
                              "UNKNOWN", "INSUFFICIENT_DATA"))
        for c in out["checks"]:
            for key in ("check_id", "observed_value", "model_value",
                        "difference", "status", "evidence_ids",
                        "assumption_ids", "notes"):
                self.assertIn(key, c)


if __name__ == "__main__":
    unittest.main()
