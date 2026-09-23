"""Tests: MT5 backtest import (Module 6) — CSV/HTML/TXT parsers."""
import os
import unittest

from core.backtest_io import (parse_backtest_file, parse_deals_csv,
                              summary_from_deals, _parse_number)
from tests import TempDirTestMixin

DEALS_CSV = "\t".join  # tab separated, like MT5 report exports


def _sample_deals_csv() -> str:
    rows = [
        ["Time", "Deal", "Symbol", "Type", "Direction", "Volume", "Price",
         "Order", "Commission", "Swap", "Profit", "Balance", "Comment"],
        ["2024.01.02 09:00:00", "1", "XAUUSD", "balance", "", "", "", "",
         "0.00", "0.00", "5000.00", "5000.00", ""],
        ["2024.01.02 09:00:01", "2", "XAUUSD", "buy", "in", "0.10", "2050.00",
         "1", "0.00", "0.00", "0.00", "5000.00", ""],
        ["2024.01.02 09:30:00", "3", "XAUUSD", "buy", "in", "0.10", "2045.00",
         "2", "0.00", "0.00", "0.00", "5000.00", "grid"],
        ["2024.01.02 12:00:00", "4", "XAUUSD", "buy", "out", "0.20", "2048.00",
         "3", "-0.40", "0.00", "60.00", "5059.60", "basket close"],
        ["2024.01.03 09:00:00", "5", "XAUUSD", "buy", "in", "0.10", "2040.00",
         "4", "0.00", "0.00", "0.00", "5059.60", ""],
        ["2024.01.03 10:00:00", "6", "XAUUSD", "buy", "out", "0.10", "2035.00",
         "5", "-0.20", "0.00", "-50.00", "5009.40", "basket close"],
        ["2024.01.04 09:00:00", "7", "XAUUSD", "sell", "in", "0.10", "2030.00",
         "6", "0.00", "0.00", "0.00", "5009.40", ""],
        ["2024.01.04 11:00:00", "8", "XAUUSD", "sell", "out", "0.10", "2025.00",
         "7", "-0.20", "0.00", "50.00", "5059.20", "basket close"],
    ]
    return "\n".join(DEALS_CSV(r) for r in rows)


SUMMARY_HTML = """<html><head><meta charset="utf-8"><title>Strategy Tester Report</title></head><body>
<h2>Strategy Tester Report (Expert Advisor SUPERRICH_SNIPER)</h2>
<div>Symbol: XAUUSD Period: H1 2023.01.01 - 2024.01.01</div>
<table>
<tr><td>Total Net Profit:</td><td>1 234.56</td><td>1 234.56</td></tr>
<tr><td>Gross Profit:</td><td>2 469.12</td></tr>
<tr><td>Gross Loss:</td><td>-1 234.56</td></tr>
<tr><td>Profit Factor:</td><td>2.00</td></tr>
<tr><td>Expected Payoff:</td><td>12.35</td></tr>
<tr><td>Balance Drawdown Maximal:</td><td>234.56 (4.12%)</td></tr>
<tr><td>Balance Drawdown Relative:</td><td>4.12% (234.56)</td></tr>
<tr><td>Total Trades:</td><td>100</td></tr>
<tr><td>Winning Trades:</td><td>70 (70.00%)</td></tr>
<tr><td>Losing Trades:</td><td>30 (30.00%)</td></tr>
<tr><td>Largest profit trade:</td><td>120.00</td></tr>
<tr><td>Largest loss trade:</td><td>-80.00</td></tr>
<tr><td>Average profit trade:</td><td>35.27</td></tr>
<tr><td>Average loss trade:</td><td>-41.15</td></tr>
</table>
</body></html>"""

SUMMARY_TXT = """
Strategy Tester Report
Total Net Profit: 500.25
Gross Profit: 800.50
Gross Loss: -300.25
Profit Factor: 2.66
Expected Payoff: 5.00
Total Trades: 100
Winning Trades: 60
Losing Trades: 40
"""


class TestNumberParsing(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(_parse_number("1 234.56"), 1234.56)
        self.assertEqual(_parse_number("1,234.56"), 1234.56)
        self.assertEqual(_parse_number("1234,56"), 1234.56)
        self.assertEqual(_parse_number("-12.34%"), -12.34)
        self.assertIsNone(_parse_number("abc"))
        self.assertIsNone(_parse_number(""))


class TestDealsCSV(TempDirTestMixin, unittest.TestCase):
    def _write(self, content, name="report.csv", enc="utf-8"):
        path = os.path.join(self.tmpdir, name)
        with open(path, "w", encoding=enc, newline="") as f:
            f.write(content)
        return path

    def test_parse_and_summary(self):
        path = self._write(_sample_deals_csv())
        deals, notes = parse_deals_csv(path)
        self.assertEqual(len(deals), 8)
        s = summary_from_deals(deals, notes)
        self.assertEqual(s.initial_deposit, 5000.0)
        self.assertEqual(s.trades, 3)
        self.assertAlmostEqual(s.net_profit, 59.2)      # 59.6 - 50.2 + 49.8
        self.assertAlmostEqual(s.gross_profit, 109.4)   # 59.6 + 49.8
        self.assertAlmostEqual(s.gross_loss, -50.2)
        self.assertAlmostEqual(s.profit_factor, 109.4 / 50.2, places=3)
        self.assertEqual(s.winning_trades, 2)
        self.assertEqual(s.losing_trades, 1)
        self.assertAlmostEqual(s.largest_profit, 59.6)
        self.assertAlmostEqual(s.largest_loss, -50.2)
        # drawdown from balance series 5000 -> 5059.6 -> 5009.4 -> 5059.2
        self.assertAlmostEqual(s.max_drawdown, 50.2)
        self.assertAlmostEqual(s.relative_drawdown, 50.2 / 5059.6 * 100, places=3)
        self.assertEqual(len(s.balance_curve), 8)
        self.assertEqual(s.symbol, "XAUUSD")

    def test_utf16_file(self):
        path = os.path.join(self.tmpdir, "u16.csv")
        with open(path, "w", encoding="utf-16") as f:
            f.write(_sample_deals_csv())
        deals, _ = parse_deals_csv(path)
        self.assertEqual(len(deals), 8)

    def test_parse_backtest_file_dispatch(self):
        s = parse_backtest_file(self._write(_sample_deals_csv()))
        self.assertEqual(s.source_format, "csv")
        self.assertAlmostEqual(s.net_profit, 59.2)

    def test_empty_csv_notes(self):
        s = parse_backtest_file(self._write("nothing useful here"))
        self.assertIsNone(s.net_profit)
        self.assertTrue(s.notes)


class TestHTMLReport(TempDirTestMixin, unittest.TestCase):
    def test_summary_labels(self):
        path = os.path.join(self.tmpdir, "r.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(SUMMARY_HTML)
        s = parse_backtest_file(path)
        self.assertEqual(s.source_format, "html")
        self.assertAlmostEqual(s.net_profit, 1234.56)
        self.assertAlmostEqual(s.gross_profit, 2469.12)
        self.assertAlmostEqual(s.gross_loss, -1234.56)
        self.assertAlmostEqual(s.profit_factor, 2.0)
        self.assertAlmostEqual(s.expected_payoff, 12.35)
        self.assertAlmostEqual(s.max_drawdown, 234.56)
        self.assertAlmostEqual(s.max_drawdown_percent, 4.12)
        self.assertAlmostEqual(s.relative_drawdown, 4.12)
        self.assertEqual(s.trades, 100)
        self.assertEqual(s.winning_trades, 70)
        self.assertEqual(s.losing_trades, 30)
        self.assertAlmostEqual(s.largest_profit, 120.0)
        self.assertAlmostEqual(s.largest_loss, -80.0)

    def test_html_with_deals_table_computes_curve(self):
        html = SUMMARY_HTML + "<table><tr>" + "".join(
            f"<td>{h}</td>" for h in
            ["Time", "Deal", "Symbol", "Type", "Direction", "Volume", "Price",
             "Order", "Commission", "Swap", "Profit", "Balance", "Comment"]) + "</tr>"
        html += "<tr><td>2024.01.02 09:00:00</td><td>1</td><td>XAUUSD</td><td>balance</td><td></td><td></td><td></td><td></td><td>0</td><td>0</td><td>1000</td><td>1000</td><td></td></tr>"
        html += "<tr><td>2024.01.02 10:00:00</td><td>2</td><td>XAUUSD</td><td>buy</td><td>in</td><td>0.1</td><td>2050</td><td>1</td><td>0</td><td>0</td><td>0</td><td>1000</td><td></td></tr>"
        html += "<tr><td>2024.01.02 11:00:00</td><td>3</td><td>XAUUSD</td><td>buy</td><td>out</td><td>0.1</td><td>2052</td><td>2</td><td>0</td><td>0</td><td>20</td><td>1020</td><td></td></tr>"
        html += "</table></body></html>"
        path = os.path.join(self.tmpdir, "r2.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        s = parse_backtest_file(path)
        self.assertTrue(s.deals)
        self.assertAlmostEqual(s.net_profit, 20.0)
        self.assertEqual(s.trades, 1)


class TestTXTReport(TempDirTestMixin, unittest.TestCase):
    def test_txt_labels(self):
        path = os.path.join(self.tmpdir, "r.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(SUMMARY_TXT)
        s = parse_backtest_file(path)
        self.assertEqual(s.source_format, "txt")
        self.assertAlmostEqual(s.net_profit, 500.25)
        self.assertAlmostEqual(s.profit_factor, 2.66)
        self.assertEqual(s.trades, 100)
        self.assertEqual(s.winning_trades, 60)

    def test_missing_fields_stay_none(self):
        path = os.path.join(self.tmpdir, "r2.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("no numbers here")
        s = parse_backtest_file(path)
        self.assertIsNone(s.net_profit)
        self.assertIsNone(s.profit_factor)
        self.assertTrue(s.notes)


class TestSummaryRoundTrip(unittest.TestCase):
    def test_dict_roundtrip(self):
        from core.backtest_io import BacktestSummary, DealRecord
        s = BacktestSummary(net_profit=10.0, trades=2,
                            deals=[DealRecord(time="t", type="buy", direction="in")])
        d = s.to_dict()
        s2 = BacktestSummary.from_dict(d)
        self.assertEqual(s2.net_profit, 10.0)
        self.assertEqual(len(s2.deals), 1)


if __name__ == "__main__":
    unittest.main()
