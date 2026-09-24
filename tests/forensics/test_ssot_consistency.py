"""SSOT consistency — every lot computation must flow through ONE formula.

The forensics LotEngine (floor, from real observations) and the analyzer
SSOT core.calculations (now floored after MC-001 owner confirmation)
must produce IDENTICAL ladders for the default configuration. Any
divergence means someone re-implemented the lot formula — forbidden.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.forensics.lot_engine import LotEngine, LotEngineConfig
from core.forensics.cycle_reconstruction import reconstruct_cycles
from core.forensics.mt5_report import load_report
from tests import std_ctx
from core import calculations as c

DESKTOP = r"C:\Users\BANK\Desktop"
ACCOUNTS = ["335504856", "391629843", "411173797", "440192945"]


class TestSSOTConsistency(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_ssot_equals_forensics_engine_l1_l50(self):
        eng = LotEngine()
        for lvl in range(1, 51):
            ssot = c.lot_for_level(self.cfg, lvl, self.rules, self.prof).value
            self.assertEqual(ssot, eng.lot(lvl), f"L{lvl} diverged")

    def test_ssot_is_floor_not_round(self):
        # the exact points where the old round SSOT was wrong (E012)
        for lvl, floor_value in [(5, 0.14), (7, 0.17), (10, 0.23),
                                 (12, 0.28), (14, 0.34), (18, 0.50)]:
            got = c.lot_for_level(self.cfg, lvl, self.rules, self.prof).value
            self.assertEqual(got, floor_value, f"L{lvl}")

    def test_real_data_matches_ssot_on_clean_cycles(self):
        """The SSOT must reproduce the observed lots 100% on anomaly-free
        cycles (owner-confirmed MC-001). Skips silently when the source
        xlsx files are not present on this machine."""
        eng = LotEngine()
        checked = 0
        for acct in ACCOUNTS:
            path = os.path.join(DESKTOP, f"ReportHistory-{acct}.xlsx")
            if not os.path.exists(path):
                continue
            rep = load_report(path)
            for cyc in reconstruct_cycles(rep):
                if cyc.confidence != "HIGH":
                    continue
                for side in ("BUY", "SELL"):
                    seq = [m["volume"] for m in cyc.members if m["side"] == side]
                    for lvl, v in enumerate(seq, 1):
                        self.assertEqual(
                            v, eng.lot(lvl),
                            f"{cyc.cycle_id} {side} L{lvl}: {v} != SSOT")
                        checked += 1
        if checked:
            self.assertGreater(checked, 4000)   # full dataset sanity

    def test_custom_config_flows_through_ssot(self):
        cfg, prof, acct, rules = std_ctx()
        cfg.BaseLot = 0.18
        cfg.LotMultiplier = 1.08
        prof.lot_step = 0.01
        self.assertEqual(c.lot_for_level(cfg, 3, rules, prof).value, 0.20)
        eng = LotEngine(LotEngineConfig(base_lot=0.18, multiplier=1.08))
        self.assertEqual(eng.lot(3), 0.20)


if __name__ == "__main__":
    unittest.main()
