"""Runtime verification against the LIVE server (default http://127.0.0.1:8765).

Run while the server is up:
    python tools/make_check_payloads.py
    python tools/runtime_check.py [base_url]
Prints a checklist; exits non-zero on any failure. This script talks to the
real HTTP server (not in-process) - it is a deployment smoke test.
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
PAYLOADS = os.path.join(os.environ.get("TEMP", "."), "sniper_web_check")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import EAConfig
from core.symbol_profile import AccountSettings, SymbolProfile

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(("PASS  " if ok else "FAIL  ") + name + ("  -- " + str(detail) if detail and not ok else ""))


def http(method, path, body=None, headers=None, raw_body=None):
    url = BASE + path
    data = raw_body if raw_body is not None else (
        json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method,
                                 headers=headers or {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return res.status, dict(res.headers), res.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def jbody(path, body=None):
    status, headers, data = http("POST" if body is not None else "GET", path, body)
    try:
        return status, json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return status, data


def load(name):
    with open(os.path.join(PAYLOADS, name), encoding="utf-8") as f:
        return json.load(f)


def multipart(filename, path):
    boundary = "verifyBound7788"
    with open(path, "rb") as f:
        content = f.read()
    head = (f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n").encode()
    body = head + content + f"\r\n--{boundary}--\r\n".encode()
    return body, {"Content-Type": f"multipart/form-data; boundary={boundary}",
                  "Content-Length": str(len(body))}


def main():
    # 1. health
    status, payload = jbody("/api/health")
    check("backend startup + /api/health", status == 200 and payload["data"]["status"] == "ok")

    # 2. frontend
    status, headers, data = http("GET", "/")
    check("frontend / (index.html)", status == 200 and b"SNIPER CashFlow Analyzer" in data)
    status, headers, data = http("GET", "/static/app.js")
    check("frontend /static/app.js", status == 200 and b"javascript" in headers.get("Content-Type", "").encode())

    # 3. config
    status, payload = jbody("/api/config")
    check("/api/config (27 params, presets, profiles)",
          status == 200 and payload["data"]["parameter_count"] == 27
          and len(payload["data"]["presets"]) == 3 and len(payload["data"]["profiles"]) == 3)

    # 4. validate (ok + warning case)
    status, payload = jbody("/api/validate", load("validate.json"))
    check("/api/validate default config", status == 200 and not payload["data"]["has_errors"])
    status, payload = jbody("/api/validate", load("validate_warn.json"))
    codes = [i["code"] for i in payload["data"]["issues"]]
    check("/api/validate broker constraints (BaseLot<min)",
          status == 200 and "BASELOT_BELOW_MIN" in codes and "BASELOT_NOT_ON_STEP" in codes)

    # 5. grid
    status, payload = jbody("/api/grid/calculate", load("grid.json"))
    lots = [r["lot"] for r in payload["data"]["grid"]["rows"]] if status == 200 else []
    check("/api/grid/calculate (11 levels, golden lots)",
          status == 200 and lots[:5] == [0.1, 0.11, 0.12, 0.13, 0.15]
          and abs(payload["data"]["grid"]["rows"][10]["cumulative_lot"] - 1.85) < 1e-9)

    # 6. worst case
    status, payload = jbody("/api/worst-case/simulate", load("worst.json"))
    both50 = [r for r in payload["data"]["results"]
              if r["scenario"] == "BOTH_SIDES" and r["adverse_move"] == 50.0]
    r = both50[0] if both50 else {}
    check("/api/worst-case/simulate ($50 BOTH golden)",
          status == 200 and r.get("grid_levels") == 11
          and abs(r.get("total_lots", 0) - 1.95) < 1e-9
          and abs(r.get("floating_pl", 0) + 3255.0) < 1e-9)

    # 7. risk
    status, payload = jbody("/api/risk/calculate", load("risk.json"))
    flags = {f["flag"] for f in payload["data"]["summary"]["flags"]} if status == 200 else set()
    check("/api/risk/calculate + honesty flags",
          status == 200 and "MODEL ASSUMPTION" in flags
          and "EA BEHAVIOR NOT VERIFIED" in flags)

    # 8. basket
    status, payload = jbody("/api/basket/simulate", load("basket.json"))
    b = payload["data"]["basket"] if status == 200 else {}
    check("/api/basket/simulate (partial + target)",
          status == 200 and abs(b.get("partial_close_volume", 9) - 0.3) < 1e-9
          and abs(b.get("price_move_to_target", 9) - 9.04393443) < 1e-6)

    # 9. set builder
    status, payload = jbody("/api/set-builder/generate", load("setbuilder.json"))
    data = payload["data"] if status == 200 else {}
    check("/api/set-builder/generate (6 combos, no ranking)",
          status == 200 and data.get("total") == 6
          and len(data.get("combinations", [])) == 6
          and "not ranked" in data.get("note", ""))

    # 10. backtest upload + analyze
    body, headers = multipart("deals.csv", os.path.join(PAYLOADS, "deals.csv"))
    status, _, raw = http("POST", "/api/backtest/analyze", raw_body=body, headers=headers)
    payload = json.loads(raw.decode("utf-8"))
    s = payload["data"]["summary"] if status == 200 else {}
    a = payload["data"]["analysis"] if status == 200 else {}
    check("/api/backtest/analyze upload CSV",
          status == 200 and abs(s.get("net_profit", 0) - 19.6) < 1e-9
          and s.get("trades") == 1
          and a.get("max_grid_depth_total") == 1)

    # 11. report export (json + html)
    status, headers, data = http("POST", "/api/report", load("report.json"))
    rep = json.loads(data.decode("utf-8")) if status == 200 else {}
    check("/api/report JSON", status == 200 and rep.get("schema") == "SNIPER_REPORT_V1"
          and "SIMULATION MODEL" in rep.get("disclaimer", ""))
    body_html = load("report.json")
    body_html["format"] = "html"
    status, headers, data = http("POST", "/api/report", body_html)
    check("/api/report HTML (self-contained, printable)",
          status == 200 and data.strip().startswith(b"<html"))
    csv_req = load("report.json")
    csv_req["format"] = "csv"
    status, headers, data = http("POST", "/api/report", csv_req)
    check("/api/report CSV", status == 200 and b"SECTION" in data[:200])

    # 12. parity spot check: web result == core result (same live server)
    from core.grid import build_grid_table
    from core.model_rules import SimulationModelRules
    cfg = EAConfig()
    prof = SymbolProfile()
    acct = AccountSettings()
    rules = SimulationModelRules()
    table = build_grid_table(cfg, prof, acct, rules, 11, "BUY")
    status, payload = jbody("/api/grid/calculate", load("grid.json"))
    check("live parity: API grid rows == core build_grid_table rows",
          payload["data"]["grid"]["rows"] == table.to_dicts())

    # 13. malformed input
    status, _, raw = http("POST", "/api/validate", raw_body=b"{not json",
                          headers={"Content-Type": "application/json"})
    check("malformed JSON -> 400", status == 400 and b"VALIDATION_ERROR" in raw)
    bad = load("grid.json")
    bad["levels"] = 99999
    status, payload = jbody("/api/grid/calculate", bad)
    check("out-of-range levels -> 400", status == 400 and not payload["ok"])

    # 14. upload security: wrong extension rejected, traversal blocked
    body, headers = multipart("evil.py", os.path.join(PAYLOADS, "evil.py"))
    status, _, raw = http("POST", "/api/backtest/analyze", raw_body=body, headers=headers)
    check("upload .py rejected", status == 400 and b"UNSUPPORTED_FILE_TYPE" in raw)
    body, headers = multipart("..\\..\\evil.csv", os.path.join(PAYLOADS, "deals.csv"))
    status, _, raw = http("POST", "/api/backtest/analyze", raw_body=body, headers=headers)
    payload = json.loads(raw.decode("utf-8"))
    check("upload traversal filename sanitized",
          status == 200 and "\\" not in payload["data"]["summary"]["source_file"]
          and "/" not in payload["data"]["summary"]["source_file"])
    status, _, raw = http("GET", "/static/../core/calculations.py")
    check("static traversal blocked", status == 404)

    failed = [r for r in RESULTS if not r[1]]
    print("-" * 60)
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        for name, _, detail in failed:
            print("FAILED:", name, detail)
        sys.exit(1)


if __name__ == "__main__":
    main()
