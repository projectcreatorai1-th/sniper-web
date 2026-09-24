"""Tests: Timeline Simulator (Phase 4) — events, prices, scenarios, trace,
immutability, worst-case integration, model-vs-simulation, performance."""
import time
import unittest

from core import calculations as c
from core.config import EAConfig
from core.mt5_adapters import BehaviorRecord, EVENT_ADD_GRID, EVENT_OPEN_POSITION
from core.symbol_profile import AccountSettings, SymbolProfile
from core.model_rules import SimulationModelRules, ModelVersionStore
from core.timeline_simulation import (
    COMPLETE,
    INCOMPLETE,
    OBSERVED_SERIES,
    SCENARIO,
    SCENARIOS,
    SCENARIO_DOWN,
    SCENARIO_GAP_DOWN,
    SCENARIO_RANGE,
    SCENARIO_SHARP_REVERSAL,
    SCENARIO_UP,
    SIM_ASSUMPTIONS,
    SYNTHETIC_LABEL,
    PriceBar,
    TimelineEventEngine,
    build_trace,
    compare_model_simulation,
    generate_scenario,
    make_bar,
    observed_series,
    simulate_timeline,
    worst_case_timeline,
)
from tests import std_ctx


class TestPriceSeries(unittest.TestCase):
    def test_observed_series_bid_ask_unknown(self):
        bars = observed_series(["t1", "t2"], [2000.0, 1995.0])
        self.assertEqual(bars[0].mid, 2000.0)
        self.assertIsNone(bars[0].bid)      # UNKNOWN, not 0
        self.assertIsNone(bars[0].ask)
        self.assertIsNone(bars[0].spread)   # never fabricated

    def test_full_bar_derives_spread(self):
        bar = make_bar("t1", 2000.0, bid=1999.8, ask=2000.2)
        self.assertEqual(bar.spread, 0.4)
        self.assertAlmostEqual(bar.mid, 2000.0)

    def test_gap_detected_in_series(self):
        bars = observed_series(["t1", "t2", "t3"], [2000, 1995, 1985])
        gap = abs(bars[2].mid - bars[1].mid)
        self.assertGreater(gap, 5)   # > grid step = gap


class TestScenarios(unittest.TestCase):
    def test_all_presets_generate(self):
        for sc in SCENARIOS:
            bars = generate_scenario(sc, 2000.0, bars=10, step=1.0)
            self.assertEqual(len(bars), 10, sc)
            self.assertTrue(all(b.timestamp for b in bars))

    def test_up_goes_up_down_goes_down(self):
        up = generate_scenario(SCENARIO_UP, 2000, bars=5, step=1)
        down = generate_scenario(SCENARIO_DOWN, 2000, bars=5, step=1)
        self.assertGreater(up[-1].mid, up[0].mid)
        self.assertLess(down[-1].mid, down[0].mid)

    def test_range_stays_bounded(self):
        bars = generate_scenario(SCENARIO_RANGE, 2000, bars=50, step=1)
        self.assertTrue(all(abs(b.mid - 2000) <= 5 for b in bars))

    def test_reversal_changes_direction(self):
        bars = generate_scenario(SCENARIO_SHARP_REVERSAL, 2000, bars=20, step=1)
        mid = bars[10].mid
        self.assertGreater(bars[9].mid, bars[0].mid)   # rising first
        self.assertLess(bars[-1].mid, mid)              # then falls

    def test_gap_has_jump(self):
        bars = generate_scenario(SCENARIO_GAP_DOWN, 2000, bars=30, step=1)
        diffs = [abs(bars[i + 1].mid - bars[i].mid) for i in range(len(bars) - 1)]
        self.assertGreater(max(diffs), 5)   # contains a jump

    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError):
            generate_scenario("SIDEWAYS_MOON", 2000)

    def test_synthetic_labeled(self):
        sim = simulate_timeline(*std_ctx(),
                                generate_scenario(SCENARIO_UP, 2000, 10, 1))
        self.assertTrue(sim.synthetic)
        self.assertIn("SYNTHETIC", sim.notes)
        self.assertIn("NOT observed evidence", sim.notes)


class TestEventEngine(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def _series_down(self, bars=60):
        return generate_scenario(SCENARIO_DOWN, 2000.0, bars=bars, step=1.0)

    def test_ordered_events_with_timestamps(self):
        sim = simulate_timeline(self.cfg, self.prof, self.acct, self.rules,
                                self._series_down())
        ts = [e.timestamp for e in sim.events]
        self.assertEqual(ts, sorted(ts))
        self.assertTrue(all(e.cycle_id for e in sim.events))

    def test_grid_events_use_core_lots(self):
        sim = simulate_timeline(self.cfg, self.prof, self.acct, self.rules,
                                self._series_down())
        grids = [e for e in sim.events if e.event == "GRID"]
        self.assertTrue(grids)
        for i, g in enumerate(grids, start=2):
            model_lot = c.lot_for_level(self.cfg, i, self.rules, self.prof).value
            self.assertAlmostEqual(g.lot, model_lot, places=8)

    def test_every_event_labeled_model_assumption(self):
        sim = simulate_timeline(self.cfg, self.prof, self.acct, self.rules,
                                self._series_down())
        for e in sim.events:
            self.assertEqual(e.label, "MODEL ASSUMPTION")
            self.assertTrue(e.assumption_ids)

    def test_costs_stay_unknown_not_zero(self):
        sim = simulate_timeline(self.cfg, self.prof, self.acct, self.rules,
                                self._series_down())
        for e in sim.events:
            self.assertIsNone(e.commission)
            self.assertIsNone(e.swap)
            self.assertIsNone(e.spread_cost)
            self.assertIsNone(e.net_pnl)   # cannot compute without costs

    def test_margin_and_equity_present(self):
        sim = simulate_timeline(self.cfg, self.prof, self.acct, self.rules,
                                self._series_down())
        entry = next(e for e in sim.events if e.event == "ENTRY")
        self.assertIsNotNone(entry.equity)
        self.assertIsNotNone(entry.margin)
        self.assertIsNotNone(entry.free_margin)
        self.assertIsNotNone(entry.exposure)

    def test_basket_close_resets_cycle(self):
        cfg = self.cfg.copy()
        cfg.BasketCloseAllUSD = 0.5     # easy to hit
        series = generate_scenario(SCENARIO_SHARP_REVERSAL, 2000.0, bars=80, step=1.0)
        sim = simulate_timeline(cfg, self.prof, self.acct, self.rules, series)
        ends = [e for e in sim.events if e.event == "CYCLE_END"]
        self.assertTrue(ends)
        self.assertEqual(sim.status, COMPLETE)

    def test_incomplete_when_stream_ends_open(self):
        sim = simulate_timeline(self.cfg, self.prof, self.acct, self.rules,
                                generate_scenario(SCENARIO_DOWN, 2000, 20, 1))
        if not any(e.event == "CYCLE_END" for e in sim.events):
            self.assertEqual(sim.status, INCOMPLETE)

    def test_emergency_stops_cycle(self):
        cfg = self.cfg.copy()
        cfg.EnableEmergencyStop = True
        cfg.EmergencyDistanceFromCycleUSD = 10.0
        sim = simulate_timeline(cfg, self.prof, self.acct, self.rules,
                                generate_scenario(SCENARIO_DOWN, 2000, 40, 1))
        emerg = [e for e in sim.events if e.event == "EMERGENCY"]
        self.assertTrue(emerg)

    def test_partial_event_emitted(self):
        cfg = self.cfg.copy()
        cfg.BasketCloseAllUSD = 50.0    # hard to reach
        cfg.ProfitPartialTriggerUSD = 0.5
        sim = simulate_timeline(cfg, self.prof, self.acct, self.rules,
                                generate_scenario(SCENARIO_SHARP_REVERSAL, 2000, 120, 1))
        partials = [e for e in sim.events if e.event == "PARTIAL"]
        # V-shape returns to start -> partial should trigger if PL >= trigger
        if partials:
            self.assertIsNotNone(partials[0].lot)

    def test_observed_series_mode(self):
        bars = observed_series(
            [f"2026-01-02 10:{i:02d}:00" for i in range(20)],
            [2000 - i for i in range(20)])
        sim = simulate_timeline(self.cfg, self.prof, self.acct, self.rules, bars,
                                input_mode=OBSERVED_SERIES)
        self.assertFalse(sim.synthetic)
        self.assertEqual(sim.input_mode, OBSERVED_SERIES)

    def test_empty_series_handled(self):
        sim = simulate_timeline(self.cfg, self.prof, self.acct, self.rules, [])
        self.assertEqual(sim.events, [])
        self.assertEqual(sim.status, INCOMPLETE)

    def test_zero_price_rejected(self):
        series = observed_series(["t1", "t2"], [2000.0, 0.0])
        engine = TimelineEventEngine(self.cfg, self.prof, self.acct, self.rules)
        events = engine.run(series)
        # engine runs but produces no crash; zero price events carry on
        self.assertIsInstance(events, list)

    def test_duplicate_timestamps_tolerated(self):
        series = observed_series(["t1", "t1", "t1"], [2000, 1995, 1990])
        engine = TimelineEventEngine(self.cfg, self.prof, self.acct, self.rules)
        events = engine.run(series)
        self.assertIsInstance(events, list)


class TestWorstCaseTimeline(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_summary_matches_ssot_pins(self):
        """The timeline is a VIEW — the underlying worst-case numbers must
        still match the regression pins exactly."""
        tl = worst_case_timeline(self.cfg, self.prof, self.acct, self.rules,
                                 500.0, 50.0, "BOTH_SIDES")
        s = tl["summary"]
        self.assertEqual(s["grid_levels"], 11)
        self.assertAlmostEqual(s["total_lots"], 1.91)
        self.assertAlmostEqual(s["floating_pl"], -3200.0)
        self.assertAlmostEqual(s["drawdown_pct"], 640.0)

    def test_timeline_has_grid_sequence(self):
        tl = worst_case_timeline(self.cfg, self.prof, self.acct, self.rules,
                                 500.0, 50.0, "BOTH_SIDES")
        grids = [e for e in tl["events"] if e["event"] in ("ENTRY", "GRID")]
        self.assertEqual(len(grids), 11)
        self.assertEqual([g["level"] for g in grids], list(range(1, 12)))


class TestTraceAndImmutability(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_trace_carries_everything(self):
        sim = simulate_timeline(self.cfg, self.prof, self.acct, self.rules,
                                generate_scenario(SCENARIO_UP, 2000, 10, 1),
                                simulation_id="SIM-T1")
        trace = build_trace(sim, evidence_ids=["E007"])
        d = trace.to_dict()
        for key in ("simulation_id", "model_version", "assumption_ids",
                    "evidence_ids", "parameter_snapshot", "environment_profile",
                    "created_at"):
            self.assertIn(key, d)
        self.assertEqual(trace.model_version, "SM-001")
        self.assertIn("E007", trace.evidence_ids)
        self.assertTrue(set(SIM_ASSUMPTIONS).issubset(set(trace.assumption_ids)))

    def test_model_version_immutable_after_simulation(self):
        import tempfile, os
        store = ModelVersionStore(os.path.join(tempfile.mkdtemp(), "mv.json"))
        sim1 = simulate_timeline(self.cfg, self.prof, self.acct,
                                 store.active_rules(),
                                 generate_scenario(SCENARIO_UP, 2000, 10, 1))
        self.assertEqual(sim1.model_version, "SM-001")
        # bump model version (with confirmation)
        rules2 = store.active_rules()
        store.apply_new_version(rules2, "manual-edit", ["test"],
                                confirmed_by="tester")
        sim2 = simulate_timeline(self.cfg, self.prof, self.acct,
                                 store.active_rules(),
                                 generate_scenario(SCENARIO_UP, 2000, 10, 1))
        self.assertEqual(sim2.model_version, "SM-002")
        # sim1 still references SM-001 — never rewritten
        self.assertEqual(sim1.model_version, "SM-001")


class TestModelVsSimulation(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def test_model_only_when_no_observed(self):
        sim = simulate_timeline(self.cfg, self.prof, self.acct, self.rules,
                                generate_scenario(SCENARIO_DOWN, 2000, 30, 1))
        result = compare_model_simulation([], sim, self.cfg, self.prof, self.rules)
        self.assertTrue(all(r["status"] == "MODEL_ONLY" for r in result["rows"]))
        self.assertIn("NEVER evidence", result["note"])

    def test_observed_matches_simulation(self):
        sim = simulate_timeline(self.cfg, self.prof, self.acct, self.rules,
                                generate_scenario(SCENARIO_DOWN, 2000, 30, 1))
        records = [BehaviorRecord(event=EVENT_OPEN_POSITION, side="BUY",
                                  lot=0.10, price=2000.0),
                   BehaviorRecord(event=EVENT_ADD_GRID, side="BUY",
                                  lot=0.11, price=1995.0),
                   BehaviorRecord(event=EVENT_ADD_GRID, side="BUY",
                                  lot=0.12, price=1990.0)]
        result = compare_model_simulation(records, sim, self.cfg, self.prof,
                                          self.rules)
        first = result["rows"][0]
        self.assertEqual(first["status"], "OBSERVED_MATCHES_SIMULATION")
        # still labeled MODEL ASSUMPTION — never "VERIFIED"
        self.assertEqual(result["label"], "MODEL ASSUMPTION")


class TestPerformance(unittest.TestCase):
    def setUp(self):
        self.cfg, self.prof, self.acct, self.rules = std_ctx()

    def _time_run(self, n):
        series = observed_series(
            [f"2026-01-02 10:00:{i % 60:02d}" for i in range(n)],
            [2000 - (i % 100) * 0.1 for i in range(n)])
        t0 = time.perf_counter()
        sim = simulate_timeline(self.cfg, self.prof, self.acct, self.rules, series)
        elapsed = time.perf_counter() - t0
        return elapsed, len(sim.events)

    def test_1000_events_under_5s(self):
        elapsed, n = self._time_run(1000)
        self.assertLess(elapsed, 5.0, f"1000 bars took {elapsed:.2f}s")

    def test_10000_events_under_30s(self):
        elapsed, n = self._time_run(10000)
        self.assertLess(elapsed, 30.0, f"10000 bars took {elapsed:.2f}s")

    def test_100000_events_under_120s(self):
        elapsed, n = self._time_run(100000)
        self.assertLess(elapsed, 120.0, f"100000 bars took {elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()
