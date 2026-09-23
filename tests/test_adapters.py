"""Tests: MT5 data pipeline adapters (Module 13)."""
import os
import unittest

from core.mt5_adapters import (CSVAdapter, TesterReportAdapter, LogAdapter,
                               ManualAdapter, BehaviorRecord, load_adapter,
                               normalize_event, EVENT_ADD_GRID, EVENT_BASKET_CLOSE,
                               EVENT_OPEN_POSITION, EVENT_UNKNOWN, EVENT_TYPES)
from tests import TempDirTestMixin

BEHAVIOR_CSV = "\n".join([
    "timestamp,symbol,event,side,ticket,grid_level,lot,price,balance,equity,margin,"
    "free_margin,floating_pl,basket_pl,position_count,total_lots,drawdown",
    "2024.01.02 09:00:01,XAUUSD,NEW_CYCLE,BUY,101,1,0.10,2050.00,5000,5000,40,4960,0,0,1,0.10,0",
    "2024.01.02 09:30:00,XAUUSD,ADD_GRID,BUY,102,2,0.11,2045.00,5000,4995,84,4911,-50,-50,2,0.21,1",
    "2024.01.02 12:00:00,XAUUSD,BASKET_CLOSE,BUY,103,,0.21,2046.00,5060,5060,0,5060,1.68,1.68,0,0,0",
])


class TestCSVAdapter(TempDirTestMixin, unittest.TestCase):
    def test_standard_schema(self):
        path = os.path.join(self.tmpdir, "b.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write(BEHAVIOR_CSV)
        records = CSVAdapter(path).load()
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].event, "NEW_CYCLE")
        self.assertEqual(records[1].event, EVENT_ADD_GRID)
        self.assertEqual(records[2].event, EVENT_BASKET_CLOSE)
        self.assertAlmostEqual(records[1].lot, 0.11)
        self.assertEqual(records[1].grid_level, 2)
        self.assertAlmostEqual(records[2].basket_pl, 1.68)

    def test_alias_headers(self):
        path = os.path.join(self.tmpdir, "alias.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write("time,type,direction,volume,price\n"
                    "2024.01.02 09:00:00,open,BUY,0.1,2050\n")
        records = CSVAdapter(path).load()
        self.assertEqual(records[0].event, EVENT_OPEN_POSITION)
        self.assertEqual(records[0].side, "BUY")

    def test_non_behavior_csv_rejected(self):
        path = os.path.join(self.tmpdir, "bad.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write("a,b,c\n1,2,3\n")
        with self.assertRaises(ValueError):
            CSVAdapter(path).load()

    def test_roundtrip_dict(self):
        r = BehaviorRecord(timestamp="t", event=EVENT_ADD_GRID, side="SELL",
                           grid_level=3, lot=0.12, price=1990.0)
        d = r.to_dict()
        r2 = BehaviorRecord.from_dict(d)
        self.assertEqual(r2.grid_level, 3)
        self.assertAlmostEqual(r2.lot, 0.12)


class TestTesterReportAdapter(TempDirTestMixin, unittest.TestCase):
    def test_derives_events_from_deals(self):
        csv = "\n".join("\t".join(r) for r in [
            ["Time", "Deal", "Symbol", "Type", "Direction", "Volume", "Price",
             "Order", "Commission", "Swap", "Profit", "Balance", "Comment"],
            ["2024.01.02 09:00:00", "1", "XAUUSD", "balance", "", "", "", "",
             "0", "0", "5000", "5000", ""],
            ["2024.01.02 09:00:01", "2", "XAUUSD", "buy", "in", "0.10", "2050",
             "1", "0", "0", "0", "5000", ""],
            ["2024.01.02 09:30:00", "3", "XAUUSD", "buy", "in", "0.11", "2045",
             "2", "0", "0", "0", "5000", "grid"],
            ["2024.01.02 12:00:00", "4", "XAUUSD", "buy", "out", "0.21", "2046",
             "3", "0", "0", "1.68", "5001.68", "close all"],
        ])
        path = os.path.join(self.tmpdir, "tester.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write(csv)
        records = TesterReportAdapter(path).load()
        events = [r.event for r in records]
        self.assertEqual(events, [EVENT_OPEN_POSITION, EVENT_ADD_GRID,
                                  EVENT_BASKET_CLOSE])
        self.assertEqual(records[0].grid_level, 1)
        self.assertEqual(records[1].grid_level, 2)
        self.assertEqual(records[1].total_lots, 0.21)

    def test_summary_only_report_raises(self):
        path = os.path.join(self.tmpdir, "summary.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("Total Net Profit: 100\nTotal Trades: 5\n")
        with self.assertRaises(ValueError):
            TesterReportAdapter(path).load()


class TestLogAdapter(TempDirTestMixin, unittest.TestCase):
    def test_keyword_lines(self):
        log = "\n".join([
            "2024.01.02 09:00:00 cycle started on XAUUSD",
            "2024.01.02 09:00:01 opened BUY 0.10 at 2050",
            "2024.01.02 09:30:00 grid add level 2 lot 0.11 price 2045",
            "2024.01.02 10:00:00 partial close executed",
            "2024.01.02 12:00:00 basket close all at profit 1.68",
            "2024.01.03 08:00:00 resume after emergency",
            "irrelevant line without keywords",
        ])
        path = os.path.join(self.tmpdir, "ea.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write(log)
        records = LogAdapter(path).load()
        events = [r.event for r in records]
        self.assertIn("NEW_CYCLE", events)
        self.assertIn(EVENT_OPEN_POSITION, events)
        self.assertIn(EVENT_ADD_GRID, events)
        self.assertIn("PARTIAL_CLOSE", events)
        self.assertIn(EVENT_BASKET_CLOSE, events)
        self.assertIn("RESUME", events)
        grid_rec = next(r for r in records if r.event == EVENT_ADD_GRID)
        self.assertEqual(grid_rec.grid_level, 2)
        self.assertAlmostEqual(grid_rec.lot, 0.11)

    def test_no_keywords_raises(self):
        path = os.path.join(self.tmpdir, "empty.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write("hello world\nnothing here\n")
        with self.assertRaises(ValueError):
            LogAdapter(path).load()


class TestManualAdapter(unittest.TestCase):
    def test_add_and_load(self):
        ad = ManualAdapter()
        ad.add(BehaviorRecord(timestamp="t", event=EVENT_ADD_GRID, lot=0.2))
        self.assertEqual(len(ad.load()), 1)
        ad.add(BehaviorRecord(timestamp="t2", event="weird"))
        self.assertEqual(ad.load()[1].event, EVENT_UNKNOWN)


class TestLoadAdapter(TempDirTestMixin, unittest.TestCase):
    def test_dispatch_by_extension(self):
        csv_path = os.path.join(self.tmpdir, "b.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(BEHAVIOR_CSV)
        adapter, records = load_adapter(csv_path)
        self.assertEqual(adapter.name, "csv")
        self.assertEqual(len(records), 3)

    def test_explicit_kind(self):
        path = os.path.join(self.tmpdir, "r.csv")
        with open(path, "w", encoding="utf-8") as f:
            f.write(BEHAVIOR_CSV)
        adapter, records = load_adapter(path, "csv")
        self.assertEqual(len(records), 3)


class TestEventNormalization(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(normalize_event("open"), EVENT_OPEN_POSITION)
        self.assertEqual(normalize_event("ADD_GRID"), EVENT_ADD_GRID)
        self.assertEqual(normalize_event("basket_close"), EVENT_BASKET_CLOSE)
        self.assertEqual(normalize_event("nonsense"), EVENT_UNKNOWN)
        for ev in EVENT_TYPES:
            self.assertEqual(normalize_event(ev), ev)


if __name__ == "__main__":
    unittest.main()
