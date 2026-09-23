"""Real-HTTP tests: live threaded WSGI server on 127.0.0.1 (ephemeral port).

Covers: static frontend serving + traversal protection, API over HTTP,
backtest upload (CSV/HTML/TXT parse parity vs core), and upload security
(extension whitelist, size limit, malformed multipart, empty file).
"""
import http.client
import json
import os
import tempfile
import threading
import unittest

from wsgiref.simple_server import WSGIRequestHandler, make_server

from core.backtest_io import parse_backtest_file

from webhelpers import multipart_body, std_body
from web.backend.app import application
from web.backend.run_server import ThreadingWSGIServer


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass


class LiveServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0, application,
                                 server_class=ThreadingWSGIServer,
                                 handler_class=QuietHandler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    # ---- helpers -----------------------------------------------------------
    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request(method, path, body=body, headers=headers or {})
        res = conn.getresponse()
        data = res.read()
        hdrs = {k.lower(): v for k, v in res.getheaders()}
        conn.close()
        return res.status, hdrs, data

    def get_json(self, path):
        status, headers, data = self.request("GET", path)
        return status, json.loads(data.decode("utf-8"))

    def post_json(self, path, body):
        status, headers, data = self.request(
            "POST", path, body=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        return status, json.loads(data.decode("utf-8"))

    # ---- static / core serving ---------------------------------------------
    def test_index_html(self):
        status, headers, data = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["content-type"])
        self.assertIn("SNIPER CashFlow Analyzer", data.decode("utf-8"))
        self.assertIn("nosniff", headers["x-content-type-options"])

    def test_static_js_css(self):
        status, headers, data = self.request("GET", "/static/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers["content-type"])
        status, headers, data = self.request("GET", "/static/style.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", headers["content-type"])

    def test_path_traversal_blocked(self):
        for path in ("/static/../backend/app.py",
                     "/static/..%2Fbackend/app.py",
                     "/static/../../core/calculations.py"):
            status, _, data = self.request("GET", path)
            self.assertEqual(status, 404, path)

    def test_favicon_404_not_spa_fallback(self):
        status, headers, data = self.request("GET", "/favicon.ico")
        self.assertEqual(status, 404)
        self.assertIn("json", headers["content-type"])  # error envelope, not html

    def test_spa_fallback_for_page_path(self):
        status, headers, data = self.request("GET", "/some/spa/route")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["content-type"])

    # ---- API over real HTTP --------------------------------------------------
    def test_health_http(self):
        status, payload = self.get_json("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["status"], "ok")

    def test_grid_http_golden(self):
        status, payload = self.post_json("/api/grid/calculate",
                                         std_body(levels=5, side="BUY", capital=500.0))
        self.assertEqual(status, 200)
        lots = [r["lot"] for r in payload["data"]["grid"]["rows"]]
        self.assertEqual(lots, [0.1, 0.11, 0.12, 0.13, 0.15])

    def test_worst_case_http_golden(self):
        status, payload = self.post_json(
            "/api/worst-case/simulate",
            std_body(capital=500.0, moves=[50.0], scenarios=["BOTH_SIDES"]))
        self.assertEqual(status, 200)
        r = payload["data"]["results"][0]
        self.assertEqual(r["grid_levels"], 11)
        self.assertAlmostEqual(r["total_lots"], 1.95)
        self.assertAlmostEqual(r["floating_pl"], -3255.0)

    def test_unknown_api_http(self):
        status, payload = self.get_json("/api/missing")
        self.assertEqual(status, 404)
        self.assertFalse(payload["ok"])


CSV_DEALS = (
    "Time\tDeal\tSymbol\tType\tDirection\tVolume\tPrice\tOrder\tCommission\tSwap\tProfit\tBalance\tComment\n"
    "2024.01.02 10:00:00\t1\t\tbalance\t\t0\t0\t0\t0\t0\t500\t500\t\n"
    "2024.01.02 10:05:00\t2\tXAUUSD\tbuy\tin\t0.1\t2050.0\t1\t0\t0\t0\t500\t500\t\n"
    "2024.01.02 10:10:00\t3\tXAUUSD\tbuy\tin\t0.1\t2045.0\t2\t0\t0\t0\t500\t500\t\n"
    "2024.01.02 11:00:00\t4\tXAUUSD\tsell\tout\t0.2\t2048.0\t3\t-0.4\t0\t25\t524.6\t524.6\tt/p\n"
)

HTML_REPORT = """<html><body>
<p>Expert Advisor: SNIPER-CashFlow &nbsp; Symbol: XAUUSD &nbsp; Period: H1</p>
<table>
<tr><td>Total Net Profit:</td><td>1 234.56</td></tr>
<tr><td>Profit Factor:</td><td>2.10</td></tr>
<tr><td>Balance Drawdown Maximal:</td><td>120.00 (10.00%)</td></tr>
<tr><td>Total Trades:</td><td>45</td></tr>
<tr><td>Initial Deposit:</td><td>500.00</td></tr>
</table>
<table>
<tr><th>Time</th><th>Deal</th><th>Symbol</th><th>Type</th><th>Direction</th>
<th>Volume</th><th>Price</th><th>Order</th><th>Commission</th><th>Swap</th>
<th>Profit</th><th>Balance</th></tr>
<tr><td>2024.01.02 10:00:00</td><td>1</td><td></td><td>balance</td><td></td>
<td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>500</td><td>500</td></tr>
<tr><td>2024.01.02 10:05:00</td><td>2</td><td>XAUUSD</td><td>buy</td><td>in</td>
<td>0.10</td><td>2050.00</td><td>1</td><td>0</td><td>0</td><td>0</td><td>500</td></tr>
<tr><td>2024.01.02 11:00:00</td><td>3</td><td>XAUUSD</td><td>sell</td><td>out</td>
<td>0.10</td><td>2052.00</td><td>2</td><td>-0.2</td><td>0</td><td>19.8</td><td>519.6</td></tr>
</table>
</body></html>"""

TXT_REPORT = (
    "Total Net Profit: 250.00\n"
    "Profit Factor: 1.85\n"
    "Total Trades: 30\n"
    "Initial Deposit: 1000.00\n"
)


class UploadTest(LiveServerTest):
    def upload(self, filename, content, field="file", raw_body=None,
               content_type=None):
        if raw_body is None:
            raw_body, content_type = multipart_body(filename, content, field=field)
        headers = {"Content-Type": content_type,
                   "Content-Length": str(len(raw_body))}
        return self.request("POST", "/api/backtest/analyze", body=raw_body,
                            headers=headers)

    def _core_reference(self, content, suffix):
        tmp = tempfile.NamedTemporaryFile(mode="wb", suffix=suffix, delete=False)
        try:
            tmp.write(content.encode("utf-8"))
            tmp.close()
            return parse_backtest_file(tmp.name).to_dict()
        finally:
            os.unlink(tmp.name)

    def test_csv_deals_upload_parity_with_core(self):
        status, headers, data = self.upload("deals.csv", CSV_DEALS)
        self.assertEqual(status, 200, data)
        payload = json.loads(data.decode("utf-8"))
        summary = payload["data"]["summary"]
        expected = self._core_reference(CSV_DEALS, ".csv")
        expected.pop("source_file")
        got = dict(summary)
        got.pop("source_file")
        self.assertEqual(got, expected)
        # sanity on computed values (from the deal list)
        self.assertAlmostEqual(summary["net_profit"], 24.6)
        self.assertEqual(summary["trades"], 1)
        self.assertEqual(summary["initial_deposit"], 500.0)
        self.assertEqual(summary["balance_curve"], [500.0, 500.0, 500.0, 524.6])
        self.assertEqual(payload["data"]["analysis"]["max_grid_depth_total"], 2)
        self.assertAlmostEqual(payload["data"]["analysis"]["max_lot"], 0.1)

    def test_html_report_upload(self):
        """With a deals table present, the core parser prefers deal-computed
        values over the summary labels (documented core behavior)."""
        status, _, data = self.upload("report.html", HTML_REPORT)
        self.assertEqual(status, 200, data)
        payload = json.loads(data.decode("utf-8"))
        summary = payload["data"]["summary"]
        expected = self._core_reference(HTML_REPORT, ".html")
        expected.pop("source_file")
        got = dict(summary)
        got.pop("source_file")
        self.assertEqual(got, expected)
        self.assertAlmostEqual(summary["net_profit"], 19.6)   # 19.8 - 0.2 commission
        self.assertEqual(summary["trades"], 1)
        self.assertAlmostEqual(summary["initial_deposit"], 500.0)

    def test_html_summary_only_upload(self):
        """HTML without a deals table: summary labels parsed, missing = None."""
        html = """<html><body><table>
        <tr><td>Total Net Profit:</td><td>1 234.56</td></tr>
        <tr><td>Profit Factor:</td><td>2.10</td></tr>
        <tr><td>Balance Drawdown Maximal:</td><td>120.00 (10.00%)</td></tr>
        <tr><td>Total Trades:</td><td>45</td></tr>
        <tr><td>Initial Deposit:</td><td>500.00</td></tr>
        </table></body></html>"""
        status, _, data = self.upload("summary_only.html", html)
        self.assertEqual(status, 200, data)
        summary = json.loads(data.decode("utf-8"))["data"]["summary"]
        self.assertAlmostEqual(summary["net_profit"], 1234.56)
        self.assertAlmostEqual(summary["profit_factor"], 2.10)
        self.assertEqual(summary["trades"], 45)
        self.assertAlmostEqual(summary["max_drawdown"], 120.0)
        self.assertAlmostEqual(summary["max_drawdown_percent"], 10.0)
        self.assertAlmostEqual(summary["initial_deposit"], 500.0)
        self.assertEqual(summary["deals"], [])

    def test_txt_report_upload(self):
        status, _, data = self.upload("report.txt", TXT_REPORT)
        self.assertEqual(status, 200, data)
        summary = json.loads(data.decode("utf-8"))["data"]["summary"]
        self.assertAlmostEqual(summary["net_profit"], 250.0)
        self.assertAlmostEqual(summary["profit_factor"], 1.85)
        self.assertEqual(summary["trades"], 30)
        self.assertEqual(summary["balance_curve"], [])

    def test_upload_wrong_extension_rejected(self):
        for name in ("evil.py", "script.exe", "data.json", "shell.bat", "noext"):
            status, _, data = self.upload(name, "print('hi')\n")
            self.assertEqual(status, 400, name)
            payload = json.loads(data.decode("utf-8"))
            self.assertEqual(payload["error"]["code"], "UNSUPPORTED_FILE_TYPE")

    def test_upload_filename_traversal_sanitized(self):
        status, _, data = self.upload("..\\..\\evil.csv", CSV_DEALS)
        self.assertEqual(status, 200, data)
        summary = json.loads(data.decode("utf-8"))["data"]["summary"]
        self.assertNotIn("\\", summary["source_file"])
        self.assertNotIn("/", summary["source_file"])

    def test_upload_empty_file_rejected(self):
        status, _, data = self.upload("empty.csv", "   \n  ")
        self.assertEqual(status, 400)

    def test_upload_missing_file_field(self):
        raw, ctype = multipart_body("x.csv", CSV_DEALS, field="not_file")
        status, _, data = self.upload(None, None, raw_body=raw, content_type=ctype)
        self.assertEqual(status, 400)

    def test_upload_malformed_multipart(self):
        status, _, data = self.upload(
            None, None,
            raw_body=b"garbage--not-a-multipart-body",
            content_type="multipart/form-data; boundary=xyz")
        self.assertEqual(status, 400)

    def test_upload_not_multipart(self):
        status, _, data = self.request(
            "POST", "/api/backtest/analyze", body=b"hello",
            headers={"Content-Type": "text/plain"})
        self.assertEqual(status, 400)

    def test_upload_too_large_rejected(self):
        old = os.environ.get("WEB_MAX_UPLOAD_MB")
        os.environ["WEB_MAX_UPLOAD_MB"] = "1"
        try:
            big_csv = ("Time\tProfit\tBalance\n" + "2024.01.02 10:00:00\t1\t2\n" * 60000)
            self.assertGreater(len(big_csv.encode("utf-8")), 1024 * 1024)
            status, _, data = self.upload("big.csv", big_csv)
            self.assertEqual(status, 413)
            payload = json.loads(data.decode("utf-8"))
            self.assertEqual(payload["error"]["code"], "PAYLOAD_TOO_LARGE")
        finally:
            if old is None:
                os.environ.pop("WEB_MAX_UPLOAD_MB", None)
            else:
                os.environ["WEB_MAX_UPLOAD_MB"] = old

    def test_malformed_csv_returns_na_not_crash(self):
        status, _, data = self.upload("junk.csv", "header,without,meaning\n1,2,3\n")
        self.assertEqual(status, 200, data)
        payload = json.loads(data.decode("utf-8"))
        summary = payload["data"]["summary"]
        # nothing invented: unparsable fields stay None
        self.assertIsNone(summary["net_profit"])
        self.assertEqual(summary["balance_curve"], [])
        self.assertTrue(summary["notes"])


if __name__ == "__main__":
    unittest.main()
