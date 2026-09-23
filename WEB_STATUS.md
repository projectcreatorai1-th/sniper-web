# WEB STATUS — SNIPER CashFlow Analyzer (Web Version)

> อัปเดต: 2026-09-23 · สถานะ: **ใช้งานได้จริง (Working)** — ไม่มี mock/placeholder/fake result/TODO ค้างงาน
> Core เดิม (`core/`) **ไม่ถูกแก้แม้แต่บรรทัดเดียว** — Desktop tests ผ่าน 157/157 เหมือนเดิม

---

## 1. สิ่งที่สร้างจริง

| ส่วน | ไฟล์ | รายละเอียด |
|---|---|---|
| Backend (WSGI, stdlib ล้วน) | `web/backend/app.py` | WSGI application + router + static server + error handling |
| | `web/backend/api.py` | /api/* ทั้งหมด — เรียก `core/*` อย่างเดียว ไม่มีสูตรในตัว |
| | `web/backend/parsers.py` | request validation + multipart parser (drain-then-reject) |
| | `web/backend/run_server.py` | entry point (threaded WSGI server, env-configurable) |
| Frontend (no build step) | `web/frontend/index.html` | SPA shell |
| | `web/frontend/app.js` | hash router + 9 หน้า + assumptions display (ไม่มีสูตรคำนวณ) |
| | `web/frontend/style.css` | responsive desktop + mobile |
| Tests | `tests/web/` (3 ไฟล์ + webhelpers) | parity/API/HTTP/upload security |
| Runner/เอกสาร | `start_web.bat`, `stop_web.bat`, `create_web_shortcuts.py`, `run_web_tests.py`, `WEB_ARCHITECTURE.md`, `DEPLOYMENT.md`, `web/deploy/Dockerfile` | |
| Verification tools | `tools/runtime_check.py`, `tools/make_check_payloads.py` | smoke test 21 ข้อกับ server จริง |

## 2. Routes / Pages (SPA hash routing)

| Route | หน้า | ฟีเจอร์หลัก |
|---|---|---|
| `#/home` | Dashboard | คำอธิบาย, Simulation Model disclaimer, ปุ่มเริ่มใช้ Calculator, flow 6 ขั้น |
| `#/settings` | EA Settings | พารามิเตอร์ 27 ตัว 1:1 (แบ่งกลุ่ม, ขั้นสูงซ่อนใน expandable), preset Default/$500/$3000, Capital, Symbol Profile + Account (ขั้นสูง), Validate แสดง warning จริง |
| `#/grid` | Grid Calculator | BUY/SELL, levels (preset + custom 1–500), GridStep/BaseLot/Multiplier, start price (ขั้นสูง), ตาราง Level/Lot/CumLot/ระยะ/Floating P/L/Margin/AvgEntry + สรุปรวม + Basket/Partial panel |
| `#/worst-case` | Worst Case Simulator | movement chips 10–100 + กำหนดเอง (เลือกหลายค่า), 3 scenarios, Emergency note, Margin Level %, คำเตือน N/A ไม่เดา |
| `#/risk` | Risk Dashboard | metrics ครบ + Risk Flags, threshold ผู้ใช้แก้ได้ทั้ง 7 ตัว (ค่าเริ่มต้นจาก Core) |
| `#/set-builder` | Set Builder | กรอก list ค่า (เช่น GridStep `5.0, 8.0` × Multiplier `1.08, 1.10, 1.20`), ผลลัพธ์ทุก combination เรียงตามลำดับสร้าง **ไม่มี ranking/score/winner**, filter DD/Margin/Levels/MaxLot ผู้ใช้กำหนด, คลิกแถวดูคำเตือนจริง |
| `#/backtest` | Backtest Analyzer | upload CSV/HTML/TXT (จำกัดชนิด/ขนาด), สรุป Net Profit/PF/Max DD + equity curve (SVG), grid depth/max lot/worst loss period, ข้อมูลไม่มี = N/A |
| `#/reports` | รายงาน | เลือกส่วน (grid/worst/risk/basket/แนบ backtest) + รูปแบบ JSON/CSV/HTML — HTML เปิดใน browser ได้/พิมพ์เป็น PDF ได้ |
| `#/assumptions` | Assumption Registry | ทุก ID พร้อมสถานะ 4 แบบ (อ่านจาก registry เดียวกับ Desktop) |

ทุกหน้าที่แสดงผลคำนวณ: banner **"Simulation Model — not verified internal EA formula"** + assumption chips คลิกดูรายละเอียด/สถานะได้

## 3. API (ใช้งานจริงทั้งหมด — validate input ก่อนคำนวณทุกตัว)

| Endpoint | สถานะ |
|---|---|
| `GET /api/health` | ✅ ใช้งานได้ |
| `GET /api/config` | ✅ defaults 27 params + presets + profiles + thresholds + model rules + move presets |
| `GET /api/assumptions` | ✅ registry 23 รายการ + 4 สถานะ |
| `POST /api/validate` | ✅ issues ERROR/WARNING/INFO จาก core validation จริง |
| `POST /api/grid/calculate` | ✅ ตาราง grid + validation warnings + assumptions |
| `POST /api/worst-case/simulate` | ✅ หลาย movement × 3 scenarios |
| `POST /api/risk/calculate` | ✅ summary + flags + thresholds ผู้ใช้ตั้งได้ |
| `POST /api/basket/simulate` | ✅ basket close / partial close |
| `POST /api/set-builder/generate` | ✅ combinations + metrics + filters (จำกัด 300 ชุด/ครั้ง) |
| `POST /api/backtest/analyze` | ✅ multipart upload + parse + analyze (parse parity กับ core) |
| `POST /api/report` | ✅ JSON/CSV/HTML (HTML self-contained พิมพ์เป็น PDF ได้) |

## 4. จำนวน Tests และผล (รันจริงทั้งหมด)

| ชุด | จำนวน | ผลล่าสุด |
|---|---|---|
| Desktop/Core (`python run_tests.py`) | 157 | **ผ่าน 157 / ตก 0** (เท่ากับก่อนทำ Web — Core ไม่เปลี่ยน) |
| Web (`python run_web_tests.py`) | 93 | **ผ่าน 93 / ตก 0** (รันซ้ำ 12 รอบติด เสถียรทั้ง 12) |
| — `test_web_parity.py` | 25 | parity ทุกหน้า + golden regression pins ผ่าน API |
| — `test_web_api.py` | 38 | envelope/malformed/config/assumptions/report formats/frontend guard-rails |
| — `test_web_http.py` | 30 | HTTP จริง + upload CSV/HTML/TXT + security (413/400/traversal) |
| Runtime smoke (`tools/runtime_check.py`) | 21 checks | **ผ่าน 21/21** กับ server จริง |
| Integration Desktop (`integration_check.py`) | 18 checks | ผ่าน 18/18 |
| Browser smoke (จริงผ่าน browser automation) | 9 หน้า + responsive | ผ่านทั้งหมด (คลิก/คำนวณจริง เห็นผลลัพธ์จริง) |

## 5. ผล Parity Desktop/Core vs Web/API (exact equality — ไม่ใช้ tolerance)

การเทียบทำสองชั้น: **in-process (WSGI)** และ **ผ่าน HTTP จริง** — input ชุดเดียวกัน เทียบ dict เป๊ะ

| Case | ผล |
|---|---|
| Grid 5/11 levels BUY+SELL (BaseLot 0.1, Step 5, Mult 1.1) | ✅ ตรงกัน 100% |
| Grid golden lots `[0.1, 0.11, 0.12, 0.13, 0.15, … 0.24]`, cum `[0.1, 0.21, 0.33, 0.46, 0.61]` | ✅ ผ่าน API ตรง pin ของ `test_regression.py` |
| Worst case $50 × 3 scenarios, ทุน $500 | ✅ ตรงกันทุก scenario |
| Golden BOTH_SIDES $50 = 11 levels / 1.95 lots / floating −$3,255 / DD 651% | ✅ ผ่านทั้ง in-process, HTTP จริง และ browser |
| Preset $500 และ $3000 (grid 11 + worst $50 + risk + validate) | ✅ ตรงกันทุก endpoint (pin preset $3000 lots `[0.18, 0.19, 0.21]` ผ่าน) |
| Basket close / partial close (default + custom percent/OnlyOnce) | ✅ ตรงกัน (pin move-to-target 9.04393443 / partial 0.3 lot / realized $1.0) |
| Broker constraints (BaseLot<min, >max, ไม่ตรง step, leverage 0, เวลาผิด, ทุนไม่พอ) | ✅ issues จริงจาก core ตรงกันเป๊ะ; ERROR ทำให้ endpoint คำนวณปฏิเสธ (400) |
| Risk calculation (default + custom thresholds) | ✅ ตรงกัน รวม honesty flags ที่มีเสมอ |
| Set Builder (GridStep 5/8 × Mult 1.08/1.10/1.20 + filters) | ✅ metrics ทุกชุดตรงกับ `evaluate_set` + filter behavior ตรง |
| Report JSON ทั้ง bundle (config/grid/worst/risk/basket/assumptions/warnings) | ✅ เท่ากับ `ReportBundle.to_dict()` ของ Core (ยกเว้น timestamp `generated`) |
| Backtest upload CSV | ✅ summary เท่ากับ `parse_backtest_file` ของ Core บนไฟล์เดียวกัน (parse parity) |
| Live parity spot-check (server จริง) | ✅ 21/21 รวมข้อ "API grid rows == core build_grid_table rows" |

## 6. วิธีเปิดเว็บ (ใช้งานได้จริง — ทดสอบแล้ว)

**วิธีที่ง่ายที่สุด — Desktop shortcuts (สร้างครั้งเดียว):**

```bat
python create_web_shortcuts.py
```

จะได้ 2 ไอคอนบน Desktop:
- **SNIPER Web - Start** → สตาร์ทเซิร์ฟเวอร์ (ถ้ายังไม่รัน) แล้วเปิด browser ที่ `http://127.0.0.1:8765` อัตโนมัติ — เซิร์ฟเวอร์รันในหน้าต่าง console ที่ย่อไว้
- **SNIPER Web - Stop** → ปิดเซิร์ฟเวอร์ (ตาม PID file ที่ `web/backend/web_server.pid` หรือค้นจาก port ถ้าไม่มี PID file)

**หรือรันจากไฟล์ .bat ในโฟลเดอร์โปรเจกต์:** `start_web.bat` / `stop_web.bat` (พฤติกรรมเดียวกัน) · หรือรันเซิร์ฟเวอร์ในหน้าต่าง console เดียวกัน (Ctrl+C เพื่อหยุด): `python web\backend\run_server.py`

Demo flow ที่ทดสองจริงใน browser: หน้าแรก → Start Calculator → เลือก preset "Seller preset - Capital $500" → ใส่ Capital 500 → บันทึกและตรวจสอบ (แสดง WARNING PARTIAL_NEVER_FIRES + INFO EMERGENCY_OFF จริง) → Grid Calculator → Calculate (11 ชั้น) → Worst Case → Simulate (12 สถานการณ์) → Risk → Calculate (flags ครบ) — จบในไม่กี่คลิก

## 7. วิธี deploy (สรุป — ละเอียดใน `DEPLOYMENT.md`)

- WSGI มาตรฐาน: `waitress-serve --host=0.0.0.0 --port=$PORT web.backend.app:application` หรือ Docker (`web/deploy/Dockerfile`) หรือ PaaS ด้วย start command `python web/backend/run_server.py`
- ทุกค่า (host/port/upload limit) รับจาก environment ไม่มี hard-code สำหรับ production / ไม่มี secrets
- ตรวจหลัง deploy: `python tools/runtime_check.py https://<host>` (21 checks)

## 8. Known Limitations (ระบุตรงไปตรงมา)

1. **Backend ตัวเริ่มต้นเป็น stdlib threaded server** — เหมาะกับ demo/ทีมเล็ก ถ้า traffic สูงให้ใช้ waitress/gunicorn ตาม DEPLOYMENT.md
2. **Web อ่าน Assumption Registry / Model Rules อย่างเดียว** (จาก `data/` เดียวกับ Desktop) — การเปลี่ยนสถานะ/สมมติฐานทำใน Desktop เพื่อกันผู้ใช้หลายคนเขียนทับกัน; หน้า Behavior Verification / Set Comparison / Test Session ยังเป็นของ Desktop ตามสเปก MVP
3. **Set Builder จำกัด 300 combinations ต่อครั้ง** และ JSON body จำกัด 2MB (กัน abuse; แจ้งเตือนชัดเจนเมื่อเกิน)
4. **Backtest parser** เข้าใจรูปแบบ MT5 มาตรฐาน (deals export/strategy tester report/TXT) — ฟิลด์ที่หาไม่เจอแสดง N/A ตามนโยบายไม่เดา ไม่ใช่ความผิดพลาด
5. **ไม่มี login/บัญชี/ประวัติผู้ใช้** — state ของผู้ใช้เก็บใน localStorage ของเบราว์เซอร์ตัวเอง (ตามสเปก UX: ไม่เพิ่ม scope)

## 9. สิ่งที่ยัง Unknown (สืบทอดจากระบบเดิม — แสดงเป็น Unknown/N/A เสมอ)

- จำนวนชั้น Grid สูงสุดภายใน EX5 (`MAX_GRID_DEPTH_UNKNOWN_001`)
- ตรรกะภายใน EX5 ทั้งหมด (`EA_BEHAVIOR_NOT_VERIFIED_001`) — เว็บเป็น Simulation Model ไม่ใช่สูตรภายในที่ยืนยันจาก EX5
- ชื่อ input จริงของพารามิเตอร์ #1 (`SYMBOL_INPUT_NAME_UNKNOWN_001`)
- spread/commission/swap จริงของโบรกเกอร์ (`PL_CONVERSION_ASSUMPTION_001` ไม่รวมค่าใช้จ่ายเหล่านี้)
- สถานะ OBSERVED_FROM_TESTING ยังไม่มีรายการใน registry กลาง (ยังไม่มีหลักฐานที่บันทึกผ่าน Desktop)

## 10. ยืนยันข้อกำหนด (Definition of Done)

✅ เว็บเปิดได้จริง (runtime 21/21) · Calculator/Grid/Worst Case/Risk/Set Builder/Backtest Upload/Report/API ใช้ได้จริง · Desktop tests 157/157 ยังผ่าน · parity ผ่านครบทุก case · ไม่มี mock/placeholder/TODO ค้างงาน/fake result · ไม่มีสูตรซ้ำใน frontend (มี test guard-rail กันด้วย) · ไม่มี auto-trading/MT5 · assumptions + Unknown แสดงถูกต้อง · มี WEB_STATUS.md / WEB_ARCHITECTURE.md / คำสั่ง run local / deployment guide
