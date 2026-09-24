"""Forensics package tests.

Fixtures here are SYNTHETIC test data for engine verification only —
they are never registered as evidence (rule: synthetic != observation).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.forensics.lot_engine import (LotEngine, LotEngineConfig,
                                       LotEngineError, OBSERVED_FLOOR_LADDER)
from core.forensics.mt5_report import (Position, Deal, MT5Report)
from core.forensics.cycle_reconstruction import (
    reconstruct_cycles, CONF_HIGH, CONF_LOW, FLAG_STILL_OPEN)
from core.forensics.partial_close import extract_partial_deals
from core.forensics.basket_forensics import (
    basket_from_cycle, replay_trigger_hypotheses, trigger_conclusion)
from core.forensics.grid_trigger import (
    collect_add_observations, replay_anchor_hypotheses, anchor_conclusion)


def mk_pos(ticket, side, vol, ot, op, ct, cp, profit=0.0):
    return Position(ticket=ticket, side=side, volume=vol, open_time=ot,
                    open_price=op, close_time=ct, close_price=cp,
                    commission=0.0, swap=0.0, profit=profit)


def mk_deal(deal_id, side, direction, vol, time, profit=0.0, order_id=""):
    return Deal(deal_id=deal_id, side=side, direction=direction, volume=vol,
                price=0.0, time=time, order_id=order_id, commission=0.0,
                fee=0.0, swap=0.0, profit=profit, balance=0.0, comment="")


class TestLotEngine(unittest.TestCase):
    def test_ladder_matches_real_observations(self):
        eng = LotEngine()
        for lvl, expect in enumerate(OBSERVED_FLOOR_LADDER, 1):
            self.assertEqual(eng.lot(lvl), expect, f"L{lvl}")

    def test_floor_not_round(self):
        eng = LotEngine()
        self.assertEqual(eng.lot(5), 0.14)    # round would give 0.15
        self.assertEqual(eng.lot(7), 0.17)    # round would give 0.18
        self.assertEqual(eng.lot(10), 0.23)   # round would give 0.24

    def test_l1_through_l50_monotonic_and_stepped(self):
        eng = LotEngine()
        ladder = eng.ladder(50)
        self.assertEqual(ladder[0], 0.10)
        for a, b in zip(ladder, ladder[1:]):
            self.assertGreater(b, a)
        for v in ladder:
            self.assertAlmostEqual(v / 0.01, round(v / 0.01), places=9)

    def test_floating_point_stability(self):
        # 0.1*1.1^k accumulates fp error; flooring must stay deterministic
        eng = LotEngine()
        self.assertEqual(eng.lot(12), 0.28)
        self.assertEqual(eng.lot(19), 0.55)
        self.assertEqual(eng.level_of_lot(0.28), 12)

    def test_broker_constraints(self):
        eng = LotEngine(LotEngineConfig(min_volume=0.10, max_volume=0.20))
        self.assertEqual(eng.lot(1), 0.10)
        self.assertEqual(eng.lot(50), 0.20)   # clamped to max
        tiny = LotEngine(LotEngineConfig(base_lot=0.001, volume_step=0.001,
                                         min_volume=0.10))
        self.assertEqual(tiny.lot(1), 0.10)   # clamped up to min

    def test_custom_step_config(self):
        eng = LotEngine(LotEngineConfig(volume_step=0.10))
        self.assertEqual(eng.lot(1), 0.10)
        self.assertEqual(eng.lot(2), 0.10)    # floor(0.11/0.10)*0.10 = 0.10

    def test_invalid_config_rejected(self):
        with self.assertRaises(LotEngineError):
            LotEngine(LotEngineConfig(multiplier=0.5))
        with self.assertRaises(LotEngineError):
            eng = LotEngine(LotEngineConfig(base_lot=-1))
            eng.lot(1)
        with self.assertRaises(LotEngineError):
            LotEngine().lot(0)

    def test_verify_sequence(self):
        eng = LotEngine()
        r = eng.verify_sequence([0.10, 0.11, 0.12, 0.13, 0.14])
        self.assertEqual(r["match_pct"], 100.0)
        r = eng.verify_sequence([0.10, 0.11, 0.15])
        self.assertEqual(r["matched"], 2)
        self.assertEqual(r["first_mismatch"]["level"], 3)


def build_synthetic_report():
    """Two clean cycles + one partial-close deal + one open cycle.
    Synthetic fixture for engine tests ONLY (not evidence)."""
    positions = [
        # cycle 1: BUY+SELL pair then grid adds, closes together
        mk_pos("T1", "BUY", 0.10, "2026.01.01 10:00:00", 4000.0, "2026.01.01 11:00:00", 4010.0, 1.0),
        mk_pos("T2", "SELL", 0.10, "2026.01.01 10:00:00", 3999.5, "2026.01.01 11:00:01", 3990.0, 0.9),
        mk_pos("T3", "BUY", 0.11, "2026.01.01 10:30:00", 3995.0, "2026.01.01 11:00:00", 4010.0, 1.5),
        # cycle 2
        mk_pos("T4", "BUY", 0.10, "2026.01.01 11:00:01", 4010.0, "2026.01.01 12:00:00", 4020.0, 1.0),
        mk_pos("T5", "SELL", 0.10, "2026.01.01 11:00:02", 4009.5, "2026.01.01 12:00:00", 4000.0, 0.2),
        # open cycle at export
        mk_pos("T6", "BUY", 0.10, "2026.01.01 12:00:01", 4020.0, "", 0.0),
        mk_pos("T7", "SELL", 0.10, "2026.01.01 12:00:01", 4019.5, "", 0.0),
    ]
    deals = [
        mk_deal("D1", "BUY", "in", 0.10, "2026.01.01 10:00:00", order_id="T1"),
        mk_deal("D2", "SELL", "in", 0.10, "2026.01.01 10:00:00", order_id="T2"),
        mk_deal("D3", "BUY", "in", 0.11, "2026.01.01 10:30:00", order_id="T3"),
        # full closes for cycle 1
        mk_deal("D4", "SELL", "out", 0.10, "2026.01.01 11:00:00", profit=1.0),
        mk_deal("D5", "BUY", "out", 0.10, "2026.01.01 11:00:01", profit=0.9),
        mk_deal("D6", "SELL", "out", 0.11, "2026.01.01 11:00:00", profit=1.5),
        # intra-position partial close on T6 (BUY): SELL out 0.04 unmatched
        mk_deal("D7", "SELL", "out", 0.04, "2026.01.01 12:30:00", profit=1.0),
    ]
    return MT5Report(account_id="SYNTH", account_line="synthetic",
                     sha256="0" * 64, source_path="synthetic",
                     positions=positions, orders=[], deals=deals,
                     open_positions=[], balance_rows=[])


class TestCycleReconstruction(unittest.TestCase):
    def setUp(self):
        self.rep = build_synthetic_report()
        self.cycles = reconstruct_cycles(self.rep)

    def test_cycle_count_and_members(self):
        self.assertEqual(len(self.cycles), 3)
        self.assertEqual([len(c.members) for c in self.cycles], [3, 2, 2])

    def test_cycle_ids_and_order(self):
        self.assertEqual(self.cycles[0].cycle_id, "SYNTH-C0000")
        self.assertLess(self.cycles[0].start_time, self.cycles[1].start_time)

    def test_initial_pair_detection(self):
        c1 = self.cycles[0]
        sides = {m["side"] for m in c1.initial_entries}
        self.assertEqual(sides, {"BUY", "SELL"})
        self.assertEqual(len(c1.grid_entries), 1)

    def test_open_cycle_flagged_low_confidence(self):
        last = self.cycles[-1]
        self.assertEqual(last.confidence, CONF_LOW)
        self.assertIn(FLAG_STILL_OPEN, last.flags)
        self.assertEqual(last.end_time, "")

    def test_first_cycle_flagged_truncated(self):
        self.assertIn("TRUNCATED_AT_REPORT_START", self.cycles[0].flags)

    def test_basket_summary(self):
        c1 = self.cycles[0]
        self.assertAlmostEqual(c1.basket_close["gross"], 3.4)
        self.assertEqual(c1.basket_close["positions"], 3)

    def test_immutable(self):
        import dataclasses
        self.assertTrue(dataclasses.is_dataclass(self.cycles[0]))
        with self.assertRaises(Exception):
            self.cycles[0].confidence = "X"


class TestPartialClose(unittest.TestCase):
    def test_unmatched_out_deal_detected(self):
        rep = build_synthetic_report()
        partials = extract_partial_deals(rep)
        self.assertEqual(len(partials), 1)
        p = partials[0]
        self.assertEqual(p.volume, 0.04)
        self.assertEqual(p.position_side, "BUY")
        self.assertEqual(p.attributed_ticket, "T6")

    def test_matched_full_closes_not_partials(self):
        rep = build_synthetic_report()
        partials = extract_partial_deals(rep)
        ids = {p.deal_id for p in partials}
        self.assertNotIn("D4", ids)
        self.assertNotIn("D6", ids)


class TestBasketForensics(unittest.TestCase):
    def test_hypothesis_replay(self):
        rep = build_synthetic_report()
        cycles = [c for c in reconstruct_cycles(rep) if c.end_time]
        baskets = [basket_from_cycle(c) for c in cycles]
        hyps = replay_trigger_hypotheses(baskets)
        names = {h.name: h for h in hyps}
        # gross values 3.4 and 1.9: T=1.00 has 0 violations
        self.assertEqual(names["H_GROSS_1_00"].violations, 0)
        self.assertGreater(names["H_GROSS_1_68"].violations, 0)

    def test_trigger_conclusion_partial(self):
        rep = build_synthetic_report()
        cycles = [c for c in reconstruct_cycles(rep) if c.end_time]
        hyps = replay_trigger_hypotheses([basket_from_cycle(c) for c in cycles])
        concl = trigger_conclusion(hyps)
        self.assertEqual(concl["basket_amount"], "OBSERVED")
        self.assertEqual(concl["trigger_status"], "PARTIAL")


class TestGridTrigger(unittest.TestCase):
    def test_prev_entry_distance(self):
        rep = build_synthetic_report()
        cycles = reconstruct_cycles(rep)
        obs = collect_add_observations(cycles, high_confidence_only=False)
        buys = [o for o in obs if o.side == "BUY" and o.cycle_id == "SYNTH-C0000"]
        self.assertEqual(buys[0].d_prev_entry, 5.0)   # 4000 -> 3995

    def test_avg_price_differs(self):
        rep = build_synthetic_report()
        cycles = reconstruct_cycles(rep)
        obs = collect_add_observations(cycles, high_confidence_only=False)
        buys = [o for o in obs if o.side == "BUY" and o.cycle_id == "SYNTH-C0000"]
        self.assertAlmostEqual(buys[0].d_avg_price, 4000.0 - 3995.0)  # only T1 open
        # with two open positions VWAP shifts: second add
        sells = [o for o in obs if o.side == "SELL" and o.cycle_id == "SYNTH-C0001"]
        self.assertEqual(len(sells), 0)

    def test_conclusion_unknown_when_empty(self):
        concl = anchor_conclusion({"step_usd": 5.0, "anchors": {}})
        self.assertEqual(concl["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
