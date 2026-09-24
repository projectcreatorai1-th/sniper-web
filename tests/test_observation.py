"""Tests: ObservationSession + CSV import with mapping/reporting (Phase 2)."""
import os
import unittest

from core.mt5_adapters import BehaviorRecord, EVENT_OPEN_POSITION
from core.observation import (
    CONTROLLED_TEST_PLANS,
    OBSERVATION_SOURCES,
    ObservationSession,
    ObservationSessionStore,
    analyze_csv_mapping,
    import_csv,
    import_file,
)
from tests import TempDirTestMixin


def write_csv(tmpdir, name, text):
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return path


VALID_CSV = "\n".join([
    "Time,Event,Side,Level,Lot,Price,TotalLots,BasketPL,Commission,Swap",
    "2024.01.02 10:00:00,open,BUY,1,0.10,2050.0,0.10,,",
    "2024.01.02 10:30:00,add,BUY,2,0.11,2045.0,0.21,,",
    "2024.01.02 10:50:00,add,BUY,3,0.12,2040.0,0.33,,",
    "2024.01.02 11:30:00,basket_close,BUY,,0.33,2048.0,,1.70,-0.20,-0.05",
]) + "\n"


class TestObservationSession(TempDirTestMixin, unittest.TestCase):
    def test_create_and_fields(self):
        s = ObservationSession.new(symbol="GOLDmicro", timeframe="M15",
                                   broker="XM Global", account_type="Hedge",
                                   source_type="MT5_CSV")
        self.assertTrue(s.session_id.startswith("OBS-"))
        self.assertEqual(s.symbol, "GOLDmicro")
        self.assertNotIn("account_number", s.to_dict())   # never stored

    def test_invalid_source_type_rejected(self):
        with self.assertRaises(ValueError):
            ObservationSession.new(source_type="TELEPATHY")

    def test_store_roundtrip_with_events(self):
        store = ObservationSessionStore(os.path.join(self.tmpdir, "obs"))
        s = ObservationSession.new(symbol="XAUUSD", source_type="MT5_CSV",
                                   events=[BehaviorRecord(event=EVENT_OPEN_POSITION,
                                                          lot=0.1, price=2000.0,
                                                          commission=None, swap=-0.1)])
        store.save(s)
        loaded = store.load(s.session_id)
        self.assertEqual(len(loaded.events), 1)
        self.assertEqual(loaded.events[0].swap, -0.1)
        self.assertIsNone(loaded.events[0].commission)     # stays UNKNOWN, not 0
        self.assertEqual(store.list_sessions(), [s.session_id])

    def test_session_separate_from_simulation_state(self):
        """ObservationSession holds observed data only - no simulation fields."""
        s = ObservationSession.new(source_type="MT5_CSV")
        d = s.to_dict()
        for sim_field in ("capital", "grid_table", "worst_case", "risk_summary"):
            self.assertNotIn(sim_field, d)


class TestCsvImport(TempDirTestMixin, unittest.TestCase):
    def test_valid_csv_import_counts_and_costs(self):
        path = write_csv(self.tmpdir, "valid.csv", VALID_CSV)
        records, result = import_csv(path)
        self.assertEqual(result.rows_read, 4)
        self.assertEqual(result.rows_imported, 4)
        self.assertEqual(result.rows_rejected, 0)
        self.assertEqual(len(records), 4)
        close = records[-1]
        self.assertEqual(close.commission, -0.20)
        self.assertEqual(close.swap, -0.05)
        self.assertEqual(records[0].confidence, "MEDIUM")

    def test_missing_timestamp_rows_rejected(self):
        text = ("Time,Event,Side\n"
                ",open,BUY\n"            # no timestamp -> rejected
                "2024.01.02 10:00:00,open,BUY\n")
        path = write_csv(self.tmpdir, "missing.csv", text)
        records, result = import_csv(path)
        self.assertEqual(result.rows_rejected, 1)
        self.assertEqual(result.rows_imported, 1)
        self.assertTrue(any("missing timestamp" in w for w in result.warnings))

    def test_invalid_csv_rejected_whole(self):
        path = write_csv(self.tmpdir, "bad.csv", "a,b,c\n1,2,3\n")
        records, result = import_csv(path)
        self.assertEqual(records, [])
        self.assertTrue(result.warnings)

    def test_unknown_columns_reported_not_imported(self):
        text = ("Time,Event,MoonPhase,Lot\n"
                "2024.01.02 10:00:00,open,Waxing,0.1\n")
        path = write_csv(self.tmpdir, "unknown.csv", text)
        records, result = import_csv(path)
        self.assertIn("MoonPhase", result.unknown_columns)
        self.assertEqual(records[0].lot, 0.1)

    def test_user_mapping_override(self):
        text = ("T,What,Size\n"
                "2024.01.02 10:00:00,open,0.10\n")
        path = write_csv(self.tmpdir, "mapped.csv", text)
        records, result = import_csv(path, user_mapping={"timestamp": "T",
                                                         "event": "What",
                                                         "lot": "Size"})
        self.assertEqual(records[0].lot, 0.10)
        self.assertEqual(result.mapping_used.get("lot"), "Size")

    def test_duplicate_rows_reported(self):
        text = ("Time,Event,Side\n"
                "2024.01.02 10:00:00,open,BUY\n"
                "2024.01.02 10:00:00,open,BUY\n")
        path = write_csv(self.tmpdir, "dup.csv", text)
        records, result = import_csv(path)
        self.assertEqual(len(records), 1)
        self.assertEqual(result.rows_rejected, 1)
        self.assertTrue(any("duplicate" in w for w in result.warnings))

    def test_missing_fields_stay_none_not_zero(self):
        path = write_csv(self.tmpdir, "sparse.csv",
                         "Time,Event\n2024.01.02 10:00:00,open\n")
        records, _ = import_csv(path)
        self.assertIsNone(records[0].lot)
        self.assertIsNone(records[0].price)
        self.assertIsNone(records[0].commission)

    def test_mapping_analysis_unknown_columns(self):
        colmap, unknown, _ = analyze_csv_mapping(
            ["Time", "Event", "WeirdCol"])
        self.assertIn("timestamp", colmap)
        self.assertIn("event", colmap)
        self.assertEqual(unknown, ["WeirdCol"])


class TestImportRouting(TempDirTestMixin, unittest.TestCase):
    def test_import_file_routes_csv(self):
        path = write_csv(self.tmpdir, "r.csv", VALID_CSV)
        records, result = import_file(path, "MT5_CSV")
        self.assertEqual(len(records), 4)
        self.assertEqual(result.source_kind, "MT5_CSV")

    def test_import_file_routes_log(self):
        path = write_csv(self.tmpdir, "r.log",
                         "2024.01.02 10:00 opened buy 0.10 price 2050\n")
        records, result = import_file(path, "MT5_JOURNAL")
        self.assertEqual(result.source_kind, "MT5_JOURNAL")

    def test_import_file_rejects_unknown_kind(self):
        with self.assertRaises(ValueError):
            import_file("x.csv", "NOPE")


class TestControlledTestPlans(unittest.TestCase):
    def test_plans_a_to_f_exist(self):
        for key in ("TEST_A_LOT", "TEST_B_GRID", "TEST_C_BUYSELL",
                    "TEST_D_BASKET", "TEST_E_PARTIAL", "TEST_F_EMERGENCY"):
            self.assertIn(key, CONTROLLED_TEST_PLANS)
            plan = CONTROLLED_TEST_PLANS[key]
            self.assertTrue(plan["name"])
            self.assertTrue(plan["capture"])
            self.assertTrue(plan["fields"])


if __name__ == "__main__":
    unittest.main()
