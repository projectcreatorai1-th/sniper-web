# WEB ARCHITECTURE — SNIPER CashFlow Analyzer (Web Version)

> อัปเดต: 2026-09-23 · Web ของ EA SNIPER CashFlow V1.68 Simulator
> **`core/` คือ Source of Truth เดียว** — Web เรียกใช้ผ่าน Backend โดยตรง ไม่มีสูตรซ้ำ

---

## 1. ภาพรวม

| ส่วน | เทคโนโลยี | หน้าที่ |
|---|---|---|
| Desktop (เดิม ห้ามแตะ) | Python 3.10+ stdlib + tkinter | แอป Windows 11 หน้า (ไม่เปลี่ยนแปลง) |
| **Core** (เดิม ห้ามแตะ) | Pure Python, ไม่มี dependency | สูตรทั้งหมดอยู่ใน `core/calculations.py` จุดเดียว |
| Web Backend | **Python stdlib WSGI** (ไม่ต้อง install เพิ่ม) | HTTP API + static files, import `core.*` ตรง ๆ |
| Web Frontend | HTML + CSS + vanilla JavaScript (ไม่ต้อง build) | SPA hash-routing 8 หน้า + Assumptions |
| Web Tests | unittest (stdlib) | Parity + API + HTTP + upload security |

เหตุผลที่เลือก stdlib WSGI: โปรเจกต์เดิมใช้ stdlib ล้วน (zero dependency) — Web ใช้แนวทางเดียวกัน
ทำให้ `python web/backend/run_server.py` เปิดเว็บได้ทันทีบน Windows โดยไม่ต้อง pip install อะไรเลย
และแอปเป็น WSGI application จริง จึง deploy ด้วย WSGI server ใดก็ได้ (เช่น waitress) ภายหลัง

## 2. Core เดิมอยู่ตรงไหน และ Web เรียกอย่างไร

```
web/frontend (browser)          web/backend (WSGI)                core/ (ไม่แก้)
─────────────────────           ─────────────────────            ─────────────────
index.html/app.js  ──HTTP──▶  web/backend/api.py  ──import──▶  core/grid.py
   ห้ามคำนวณสูตรเอง             เรียกฟังก์ชัน Core          core/worst_case.py
   (format/แสดงผลเท่านั้น)      + validate input            core/risk.py
                                                           core/basket.py
                                                           core/setbuilder.py
                                                           core/backtest_io.py
                                                           core/backtest_analysis.py
                                                           core/report.py
                                                           core/validation.py
                                                           core/assumptions.py
                                                           core/config.py / symbol_profile.py / model_rules.py
```

- ฟังก์ชัน Core ที่ Backend เรียก (ทั้งหมดคืน structured result พร้อม assumption IDs):
  - `core.config.EAConfig.from_dict/to_dict`, `builtin_presets()`
  - `core.symbol_profile.SymbolProfile/AccountSettings.from_dict`, `builtin_profiles()`
  - `core.model_rules.SimulationModelRules.from_dict`, `ModelVersionStore().active_rules()`
  - `core.validation.validate_config()`, `has_errors()`
  - `core.grid.build_grid_table()`
  - `core.worst_case.simulate_worst_case()`, `DEFAULT_MOVE_PRESETS`
  - `core.basket.simulate_basket()`
  - `core.risk.build_risk_summary()`, `RiskThresholds.from_dict()`
  - `core.setbuilder.build_combinations()`, `evaluate_set()`, `apply_filters()`, `BuilderFilters`
  - `core.backtest_io.parse_backtest_file()` (upload → temp file → parse → ลบไฟล์)
  - `core.backtest_analysis.analyze_backtest()`
  - `core.report.ReportBundle`, `export_report_json/csv/html()`
  - `core.assumptions.default_registry()` (อ่านอย่างเดียว — Web ไม่เขียน overrides)
- **Backend ไม่มีสูตรคำนวณเลย** — ทำหน้าที่ parse/validate request, เรียก Core, serialize ผลเป็น JSON
- **Frontend ไม่มีสูตรคำนวณเลย** — ทำหน้าที่เก็บ input, เรียก API, format/แสดงผล (format ตัวเลขเพื่อแสดงผลไม่ใช่การคำนวณ)

## 3. API Endpoints

Base URL: same-origin (`/api/...`) — ไม่เปิด CORS (frontend ถูก serve จาก backend ตัวเดียวกัน)

| Method | Path | หน้าที่ |
|---|---|---|
| GET | `/api/health` | สถานะ service + core/model version |
| GET | `/api/config` | defaults 27 params + presets + symbol profiles + thresholds + model rules + move presets |
| GET | `/api/assumptions` | Assumption Registry ทั้งหมด (สถานะ 4 แบบ) |
| POST | `/api/validate` | รัน `validate_config` จริง คืน issues (ERROR/WARNING/INFO) |
| POST | `/api/grid/calculate` | ตาราง grid + สรุปรวม (+ basket sim ถอดออกไป endpoint แยก) |
| POST | `/api/worst-case/simulate` | จำลอง adverse move หลายระยะ × 3 scenarios |
| POST | `/api/risk/calculate` | Risk summary + flags (threshold ผู้ใช้กำหนดได้) |
| POST | `/api/basket/simulate` | Basket close / partial close simulation |
| POST | `/api/set-builder/generate` | สร้าง combinations + metrics + filters (ไม่มี ranking) |
| POST | `/api/backtest/analyze` | Upload CSV/HTML/TXT (multipart) → parse + analyze |
| POST | `/api/report` | สร้างรายงาน JSON/CSV/HTML (download) |

### 3.1 Response envelope

```json
{ "ok": true,  "data": { ... } }
{ "ok": false, "error": { "code": "VALIDATION_ERROR", "message": "...", "details": [...] } }
```

HTTP status: 200 (สำเร็จ), 400 (input ไม่ผ่าน validation — รวม core `ValueError`),
404 (path ไม่มี), 405 (method ผิด), 413 (body ใหญ่เกิน), 500 (unexpected — log traceback)

ผลการคำนวณทุกชนิดแนบสิ่งเหล่านี้เสมอ:
- `assumptions`: assumption IDs ที่ตัวเลขชุดนั้นใช้ (มาจาก Core)
- `assumption_details`: รายละเอียด + สถานะ (VERIFIED_FROM_DOCUMENTATION / OBSERVED_FROM_TESTING / MODEL_ASSUMPTION / UNKNOWN) จาก `AssumptionRegistry.describe()`
- `disclaimer`: `"Simulation Model — not verified internal EA formula"`

### 3.2 Request schema (ใช้ schema เดียวกับ Core ทุกกรณี)

ทุก POST รับ JSON object หลัก:

```jsonc
{
  "config":        { ...SNIPER_V1_68_CONFIG (EAConfig.to_dict()) },   // 27 params
  "symbol_profile":{ ...SymbolProfile.to_dict() },                    // broker constraints
  "account":       { ...AccountSettings.to_dict() },                  // leverage/margin_rate
  "model_rules":   { ...SimulationModelRules.to_dict() },             // optional → default = active rules
  "capital":       500.0,
  ...endpoint-specific fields
}
```

- `config` ต้องเป็น known keys ของ EAConfig เท่านั้น (unknown key → 400 พร้อมระบุชื่อ key)
- ชนิดข้อมูลถูก coerce โดย `EAConfig.from_dict` / `SymbolProfile.from_dict` ฯลฯ ของ Core เอง
- ค่าที่ผิดรูปแบบ (เช่น `GridStepUSD: "abc"`) → 400
- Endpoint-specific fields:
  - `/api/grid/calculate`: `levels` (1–500), `side` ("BUY"|"SELL"), `start_price?`
  - `/api/worst-case/simulate`: `moves` (list ≥ 0, 1–12 ค่า), `scenarios?` (subset ของ BUY_ADVERSE/SELL_ADVERSE/BOTH_SIDES), `start_price?`
  - `/api/risk/calculate`: `thresholds?` (RiskThresholds), `side?` ("BUY"|"SELL")
  - `/api/basket/simulate`: `side`, `levels`, `start_price?`, `current_price?`, `partial_already_done?`
  - `/api/set-builder/generate`: `values` `{capital?, grid_step, base_lot, multiplier, basket_target?, max_grid?}` (list หรือค่าเดี่ยว), `filters?` (max_dd_percent / max_grid / max_lot / max_margin_usage_percent)
  - `/api/backtest/analyze`: `multipart/form-data` field `file` (.csv/.html/.htm/.txt, ≤ 8MB)
  - `/api/report`: `format` ("json"|"csv"|"html"), section flags `include_grid/levels/side`, `include_worst_case/moves`, `include_risk`, `include_basket`, `backtest_summary?` (ผลจาก /api/backtest/analyze ก่อนหน้า)

### 3.3 Validation ก่อนคำนวณ (ทุก endpoint)

1. Body ต้องเป็น JSON object ขนาด ≤ 2MB
2. โครงสร้าง/ชนิด field ตรง schema (ข้างบน) — ผิด → 400
3. `SimulationModelRules.validate()` (Core) — ผิด → 400
4. `validate_config()` (Core) — ถ้ามี **ERROR** → 400 พร้อม issues ทั้งชุด
5. WARNING/INFO ไม่บล็อก — แนบกลับเป็น `validation` ในผลลัพธ์ให้ UI แสดงตรงจุด

## 4. Desktop/Web Parity Strategy

- **คำนวณชุดเดียว**: Web backend เรียกฟังก์ชัน Core ตัวเดียวกับที่ Desktop (tkinter) เรียก —
  input เดียวกันต้องได้ผลเดียวกัน *โดย construction*
- **พิสูจน์ด้วย automated parity tests** (`tests/web/`): ทุก case เรียก Core ตรง ๆ (แทน Desktop)
  แล้วเทียบกับผลจาก Web API **ทั้ง in-process (WSGI) และผ่าน HTTP จริง** — เทียบด้วย equality
  เป๊ะ (dict === dict) เพราะเป็น deterministic เช่นเดียวกันโดยไม่ต้องใช้ tolerance
  (JSON round-trip ของ float ใน Python เป๊ะโดย repr)
- **Golden regression pins**: ค่าอ้างอิงจาก `tests/test_regression.py`
  (เช่น worst case $50 BOTH_SIDES = 11 levels / 1.95 lots / floating −$3,255 / DD 651%)
  ถูก assert ซ้ำผ่าน Web API เพื่อกัน core เปลี่ยนโดยไม่ตั้งใจ
- Assumption overrides (`data/assumptions_overrides.json`) และ model rules
  (`data/model_versions.json`) ถูกอ่านจากที่เดียวกัน → สถานะ assumptions ตรงกันทั้งสองฝั่ง
  (Web เปิดแบบ read-only — การแก้สถานะทำใน Desktop เพื่อกัน multi-user เขียนชนกัน)

## 5. Security

- เป็น calculator/analyzer เท่านั้น: **ไม่มี** MT5 connection / order / account / terminal control /
  EX5 execution — ในโค้ด Web ไม่มีโค้ดกลุ่มนี้อยู่เลย
- Upload backtest:
  - จำกัด extension: `.csv .html .htm .txt` เท่านั้น (ชื่อไฟล์ถูก strip path + ตรวจซ้ำ)
  - จำกัดขนาด 8MB (ค่าเริ่มต้น, ปรับด้วย env `WEB_MAX_UPLOAD_MB`) → เกินคือ 413
  - เขียนลง temp file → parse ด้วย parser ของ Core (text parsing เท่านั้น) → ลบทันที — **ไม่ execute ไฟล์**
  - malformed file → parser ของ Core ทนทาน (คืน fields เป็น None → UI แสดง N/A) ไม่ crash
- ไม่มี shell command / eval / exec จาก user input ใน backend
- Static file serving: จำกัด root ที่ `web/frontend/`, ป้องกัน path traversal (normalize + prefix check), ไม่มี directory listing
- Headers: `X-Content-Type-Options: nosniff` ทุก response, API ไม่ cache (`Cache-Control: no-store`)
- Frontend แสดงข้อมูลจาก upload ผ่าน DOM textContent (escape อัตโนมัติ) — ไม่ inject HTML จากไฟล์ผู้ใช้
- ไม่มี login/payment/ads/social/live-trading (ตามสเปก UX — ไม่เพิ่ม scope)

## 6. โครงสร้างไฟล์

```
SNIPER-CashFlow-Analyzer/
├── core/                    # เดิม — ห้ามแก้ (Source of Truth)
├── desktop/                 # เดิม — ห้ามแก้
├── data/                    # เดิม (Web อ่าน model_versions/assumption_overrides อย่างเดียว)
├── tests/                   # เดิม 157 tests (run_tests.py ยังรวม tests/web/ ด้วย)
├── web/
│   ├── backend/
│   │   ├── app.py           # WSGI application + router + static server
│   │   ├── api.py           # /api/* handlers — เรียก core อย่างเดียว
│   │   ├── parsers.py       # request parsing/validation + multipart upload parser
│   │   └── run_server.py    # entry point (threaded WSGI server, env-configurable)
│   ├── frontend/
│   │   ├── index.html       # SPA shell
│   │   ├── app.js           # hash router + 8 pages + assumptions display
│   │   └── style.css        # responsive (desktop + mobile)
│   └── deploy/
│       └── Dockerfile       # optional container deploy
├── tests/web/               # web tests (parity/API/HTTP/upload security)
├── start_web.bat            # เปิดเว็บ local ในคลิกเดียว
├── WEB_ARCHITECTURE.md      # (ไฟล์นี้)
├── WEB_STATUS.md            # สถานะ/ผล test จริง
└── DEPLOYMENT.md            # คู่มือ deploy
```

## 7. Local Development (Windows)

```bat
cd SNIPER-CashFlow-Analyzer
start_web.bat                # หรือ: python web\backend\run_server.py
:: → http://127.0.0.1:8765
```

```bat
python run_tests.py          # desktop tests + web tests ทั้งหมด
python -m unittest discover -s tests/web -p "test_web_*.py" -v   # เฉพาะ web
```

Environment variables (ทุกตัวมี default สำหรับ local):
`WEB_HOST` (default `127.0.0.1`), `WEB_PORT` (default `8765`), `WEB_MAX_UPLOAD_MB` (default `8`)

## 8. Deployment (สรุป — รายละเอียดใน DEPLOYMENT.md)

- แอปเป็น WSGI standard → deploy กับ WSGI server ใดก็ได้:
  - **waitress** (แนะนำ, cross-platform): `pip install waitress` แล้ว
    `waitress-serve --host=0.0.0.0 --port=$PORT web.backend.app:application`
  - **Docker**: `web/deploy/Dockerfile` (python:3.12-slim, รับ `PORT` env)
- ไม่มีค่า hard-code สำหรับ production: host/port/ขนาด upload รับจาก environment ทั้งหมด
- ไม่มี secrets ในโค้ด — ไม่จำเป็น (แอปไม่มี login/DB/external service)
- รองรับการขยายภายหลังเป็น account/user ได้: API stateless (ทุก request ส่ง input ครบ),
  envelope response เป็นมาตรฐานเดียว, ไม่มี global mutable state ใน backend

## 9. Assumptions / ข้อจำกัดที่แสดงต่อผู้ใช้ทุกหน้า

- ทุกหน้าที่แสดงผลการคำนวณมี banner: **"Simulation Model — not verified internal EA formula"**
- ทุกผลคำนวณแสดง assumption chips ที่คลิกดูรายละเอียด/สถานะได้ (4 สถานะตามระบบเดิม)
- หน้า Assumptions แสดง registry ครบทุก ID
- ค่าที่ไม่มีข้อมูลจริงแสดง `N/A` (เช่น backtest field ที่ parse ไม่พบ)
- ไม่ใช้คำ "ดีที่สุด/ปลอดภัยที่สุด/กำไรแน่นอน" และไม่มี ranking/score/winner ใน Set Builder
  (ผลลัพธ์เรียงตามลำดับสร้าง ผู้ใช้กรองเองด้วย filter)
