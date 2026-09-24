# PROJECT STATUS — SNIPER CashFlow Analyzer

> อัปเดต: 2026-09-23 · App v1.0.0 · สถานะ: **ใช้งานได้จริง (Working)** — ไม่มี mock/placeholder/TODO ใน logic

---

## 1. สิ่งที่ทำเสร็จ (ครบทั้ง 15 Module)

| Module | ความสำเร็จ | ไฟล์หลัก |
|---|---|---|
| M1 EA Config | พารามิเตอร์ครบ 27 ตัว (รวมช่อง Symbol ที่ชื่อ input ไม่เป็นที่รับรู้), preset $500/$3000 (ยืนยันจากอินโฟกราฟิกจริง), validation, save/load/export/import JSON | `core/config.py`, `desktop/pages/ea_settings.py` |
| M2 Grid Calculator | ตาราง Level/Distance/Lot/CumLot/Exposure/Floating P/L/Margin/AvgEntry, รองรับ depth 1–500 (5/10/20/30/50/100 + custom) | `core/grid.py`, `desktop/pages/grid_calculator.py` |
| M3 Worst Case | ตลาดวิ่งทางเดียว preset 10/20/30/50/75/100 + custom, 3 สถานการณ์ (BUY/SELL/BOTH), emergency note | `core/worst_case.py`, `desktop/pages/worst_case.py` |
| M4 Basket/Partial | จำลอง BasketCloseAllUSD, PartialTrigger/Percent/OnlyOnce, ระยะราคาที่ต้องเด้งกลับ, สลังที่เหลือหลัง partial | `core/basket.py` (แสดงผลในหน้า Grid Calculator) |
| M5 Risk Dashboard | สรุปครบทุก metric ตามสเปก + Risk Flags 6+ แบบ โดย threshold ผู้ใช้ตั้งเองได้ทั้งหมด | `core/risk.py`, `desktop/pages/risk.py` |
| M6 Backtest Import | CSV (tab/comma, UTF-16 ทนทาน), HTML (parse ทั้ง summary + deals table), TXT — ข้อมูลไหนไม่มีแสดง N/A | `core/backtest_io.py` |
| M7 Backtest Analyzer | grid depth (buy/sell/รวม), lot stats, worst drawdown episode, longest recovery, losing streak, equity curve | `core/backtest_analysis.py`, `desktop/pages/backtest.py` |
| M8 Set Builder | สร้าง combinations จาก list ค่า, filter ตามข้อจำเป็นจำกัด (DD/Grid/Lot/Margin), ไม่มีการจัดอันดับ "ดีที่สุด" | `core/setbuilder.py`, `desktop/pages/set_builder.py` |
| M9 Set Comparison | ตารางรวมทุก set + Save/Duplicate/Delete/Export/Import/Load | `core/setbuilder.py (SetStore)`, `desktop/pages/compare.py` |
| M10 Behavior Verification | บันทึกข้อมูลจริง (manual/import) เทียบ Simulation Model → MATCH/MISMATCH/UNKNOWN | `core/model_vs_observed.py`, `desktop/pages/behavior.py` |
| M11 Assumption Registry | ระบบกลาง 20 assumption IDs, 4 สถานะ, เปลี่ยนสถานะพร้อมหลักฐาน (persist), ทุกผลคำนวณแนบ assumption IDs | `core/assumptions.py`, `desktop/pages/settings.py` |
| M12 Export/Report | JSON + CSV + HTML (พิมพ์เป็น PDF จาก browser ได้ — ไม่เพิ่ม dependency) | `core/report.py`, `desktop/pages/reports.py` |
| M13 MT5 Data Pipeline | Adapter interface: CSVAdapter / TesterReportAdapter / LogAdapter / ManualAdapter → BehaviorRecord schema เดียว 17 ฟิลด์, Event types 10 แบบ | `core/mt5_adapters.py` |
| M14 Model vs Observed | ตรวจ 6 หมวด (spacing/lot/level/basket/partial/count), แนะนำ lot rule จาก observation (log-linear fit), "Apply Observed Rule" สร้าง model version ใหม่เมื่อผู้ใช้ยืนยันเท่านั้น | `core/model_vs_observed.py`, `core/model_rules.py` |
| M15 Test Session | Session แยกไฟล์ JSON ต่อ session (ID/version/broker/balance/events/comparison), New/Load/Delete | `core/sessions.py` |

**GUI (Windows Desktop, tkinter):** 11 หน้าครบตามสเปก — Dashboard, EA Settings, Grid Calculator, Worst Case, Risk, Backtest, Set Builder, Compare, Behavior Verification, Reports, Settings + toolbar New/Open/Save/Import/Export/Reset + status bar แสดง model version

**สถาปัตยกรรม:** Core (`core/`) ไม่ import tkinter เลย — GUI อยู่ใน `desktop/` เรียก Core อย่างเดียว ทุกสูตรอยู่ใน `core/calculations.py` จุดเดียว (ตรวจด้วย grep แล้วว่าไม่มีสูตรซ้ำนอกไฟล์นี้)

---

## 2. สิ่งที่ทดสอบแล้ว

- **Unit + integration tests: 157 tests / ผ่าน 157 / ตก 0** (`python run_tests.py`)
  - ครอบคลุม: default config, lot/grid/cumulative/basket/partial/worst-case/DD/margin calculation, validation ทุกกฎ, import/export round-trip ทุกชนิด, presets, assumption registry + persistence, adapters 4 ตัว, model-vs-observed, sessions, set builder/store, report exports
- **Regression tests** (`tests/test_regression.py`): pin ค่าตัวอย่าง BaseLot 0.1 / Multiplier 1.1 / GridStep 5 / XAUUSD cs=100 / ทุน $500 — เช่น lot sequence `[0.1, 0.11, 0.12, 0.13, 0.15]`, worst case $50 BOTH_SIDES = 11 levels / 1.95 lots / floating −$3,255 / DD 651% — ถ้าค่าเปลี่ยนโดยไม่ตั้งใจ test จะตกทันที
- **Integration end-to-end** (`python integration_check.py`): 18/18 ผ่าน — workflow จริงตั้งแต่เปิดโปรเจกต์ → คำนวณ → import backtest → สร้าง session → เทียบ model → export รายงาน → set builder → assumption evidence
- **GUI smoke test** (`python smoke_gui.py`): สร้างหน้าต่าง วนทุก 11 หน้า ไม่มี crash
- **ความสอดคล้องของการคำนวณ:** ตรวจว่า Grid Calculator / Worst Case / Risk ให้ตัวเลขชุดเดียวกันจาก core เดียวกัน (integration check ข้อ 2)

---

## 3. จำนวน tests

| ชุด | จำนวน | ผล |
|---|---|---|
| Unit/Integration (`tests/`, 14 ไฟล์) | 157 | ผ่าน 157 / ตก 0 |
| End-to-end workflow | 18 checks | ผ่าน 18 |
| GUI smoke | 11 หน้า | ผ่าน |

---

## 4. สิ่งที่เป็น Verified (จากเอกสารผู้ขาย — ไม่ใช่การรับประกัน)

- ค่า default พารามิเตอร์ทั้ง 27 ตัว (คู่มือ PDF 13 หน้า)
- Preset ทุน $500 / $3000 (ยืนยันซ้ำกับภาพอินโฟกราฟิกจริงทั้ง 2 ภาพ)
- GridStepUSD = ระยะราคา (หน่วยดอลลาร์ของสินทัพย์) ระหว่างออเดอร์
- Basket Close: ปิดทั้งหมดเมื่อกำไรรวมสุทธิถึง BasketCloseAllUSD
- Partial close ครั้งเดียวต่อรอบเมื่อ OnlyOnce=true
- Emergency: trigger ตามระยะราคาจากกรอบเทรด / เวลาทั้งหมดเป็นเวลาไทย ICT
- UseMartingale (ภาพ) = UsePositionSizeOptimization (PDF)

## 5. สิ่งที่เป็น Assumption (โมเดลจำลอง — สถานะ MODEL_ASSUMPTION)

สมบูรณ์ใน **Assumption Registry** (`core/assumptions.py`, ดูได้/แก้สถานะได้ในหน้า Settings):
- `LOT_FORMULA_ASSUMPTION_001` — lot = BaseLot × Multiplier^(level−1), normalize ตาม lot step
- `GRID_TRIGGER_ASSUMPTION_001` — วัดระยะจากราคาออเดอร์ล่าสุด
- `GRID_DIRECTION_ASSUMPTION_001` — เพิ่มไม้เฉพาะทิศตรงข้าม (averaging)
- `BOTH_SIDES_OPEN_AT_START_ASSUMPTION_001` — เปิด level 1 ทั้งสองฝั่งตอนเริ่มรอบ
- `BASKET_SCOPE_ASSUMPTION_001` — basket รวมสองฝั่งเป็นชุดเดียว (สลับ PER_SIDE ได้ใน model rules)
- `PARTIAL_CLOSE_ASSUMPTION_001` — ปิด % ของ volume รวมแบบ pro-rata
- `PL_CONVERSION_ASSUMPTION_001` — P/L = Δราคา × lot × contract size (ไม่รวม spread/commission/swap)
- `XAUUSD_CONTRACT_ASSUMPTION_001` — contract 100 oz (0.1 lot ≈ $10 ต่อ $1 — อ้างอิงรายงาน)
- `MARGIN_ASSUMPTION_001` — margin = lot × cs × ราคา / leverage × margin_rate
- `EMERGENCY_FRAME_ASSUMPTION_001` — กรอบเทรด = ช่วงราคาตั้งแต่เริ่มรอบถึงไม้ล่าสุด

## 6. สิ่งที่ยัง Unknown (ระบุชัด ไม่เดา)

- จำนวนชั้น Grid สูงสุดภายใน EX5 (`MAX_GRID_DEPTH_UNKNOWN_001`)
- ตรรกะภายใน EX5 ทั้งหมด (`EA_BEHAVIOR_NOT_VERIFIED_001`) — ต้องใช้ Behavior Verification สะสมหลักฐานแทนการ decompile (ซึ่งห้ามทำ)
- ชื่อ input จริงของพารามิเตอร์ #1 (`SYMBOL_INPUT_NAME_UNKNOWN_001`)
- ล็อกบัญชี/โบรกเกอร์/วันหมดอายุในไฟล์ปิด, magic number, spread/commission จริงของโบรกเกอร์

---

## 7. วิธีรันโปรแกรม

```bat
cd SNIPER-CashFlow-Analyzer
python run_app.py        # เปิดโปรแกรม (ต้องมี Python 3.10+ บน Windows — ใช้ stdlib ล้วน ไม่ต้อง install อะไร)

python run_tests.py          # รัน tests ทั้งหมด (157)
python integration_check.py  # รัน end-to-end workflow check (18)
python smoke_gui.py          # ตรวจ GUI ทุกหน้าแบบไม่เปิดหน้าต่างค้าง
```

ข้อมูลผู้ใช้เก็บใน `data/` — `sets.json`, `model_versions.json`, `assumptions_overrides.json`, `sessions/*.json`

## 8. วิธีนำ Core ไปทำ Web Version ภายหลัง

`core/` เป็น pure Python ไม่ผูก GUI:
1. สร้าง backend (FastAPI/Flask ก็ได้) import `core` ตรง ๆ
2. เรียกฟังก์ชันเดิม: `build_grid_table()`, `simulate_worst_case()`, `build_risk_summary()`, `simulate_basket()`, `parse_backtest_file()`, `compare_behavior()` ฯลฯ — ทุกฟังก์ชันคืน structured result ที่มี `to_dict()` + assumption IDs พร้อม serialize เป็น JSON แล้ว
3. config/project/report เป็น JSON versioned (`SNIPER_V1_68_CONFIG`, `SNIPER_PROJECT_V1`, `SNIPER_REPORT_V1`) — Web ใช้ schema เดียวกันได้ทันที
4. Logic คำนวณห้ามเขียนใหม่ — ถ้าต้องการภาษาอื่น (JS) ให้ยึด `tests/test_regression.py` เป็น golden values เพื่อพิสูจน์ว่าผลตรงกัน

## 9. ข้อจำกัดที่ระบุไว้ตามสเปก

- โปรแกรมนี้เป็น **Analyzer / Calculator / Simulator เท่านั้น** — ไม่มีคำสั่งซื้อขายจริง ไม่แก้บัญชี MT5 ไม่ควบคุม EA
- ไม่อ้างว่า simulation = ผล backtest จริง / ไม่รับประกันกำไร / ไม่จัดอันดับ set ว่า "ดีที่สุด-ปลอดภัยที่สุด"
- ไม่ decompile/แก้ไข `.ex5` และไม่เดาสูตรที่พิสูจน์ไม่ได้ — ทุกจุว่างระบุ UNKNOWN/ASSUMPTION พร้อมระบบรองรับการแก้ไข (Symbol Profile / Risk Thresholds / Model Rules / Assumption Registry แก้ได้ทั้งหมดโดยไม่แก้โค้ด)

---

## 16. PHASE 1 IMPLEMENTATION (2026-09-24) — Evidence / Environment / Cycle Foundation

เพิ่มบน baseline เดิมโดย **ไม่แตะสูตร/preset/พารามิเตอร์เดิมใด ๆ** (ตัวเลข Calculator ทุกตัวเหมือนเดิม — พิสูจน์ด้วย regression pins)

**สิ่งที่เพิ่ม:**

| ของ | ไฟล์ | สรุป |
|---|---|---|
| Evidence Registry | `core/evidence.py` | ระเบียนหลักฐาน E001–E010 (สถานะ DOCUMENTED/OBSERVED/MODEL/UNKNOWN) + `ExternalEvidence` interface (Myfxbook = INTERFACE READY ห้าม fake data) |
| Environment Profile | `core/environment.py` | `EnvironmentProfile` + `BrokerProfile` + OBSERVED TEST ENVIRONMENT (MT5/XM Global/Hedge/GOLDmicro/M15) — ไม่มี field account number โดยเจตนา |
| Parameter Facts | `core/param_facts.py` | แยก EA DEFAULT / RECOMMENDED PRESET / OBSERVED VALUE / USER VALUE — **Emergency 90.0 (observed) แยกจาก 50.0 (preset)** + PARAM_21 = UNKNOWN, `AccumTargetUSD` = UNVERIFIED CANDIDATE |
| EX5 Integrity | `core/ex5_integrity.py` | สถานะปัจจุบัน `SOURCE_FILE_NOT_PRESENT` + historical SHA-256/MD5 เก็บเป็น `RECORDED_EXTERNAL_BASELINE` — hash คำนวณจากไฟล์จริงเท่านั้น ไม่ decompile/modify |
| Cycle Lifecycle | `core/cycle.py` | `Cycle` (OPEN/CLOSED/EMERGENCY_CLOSED/UNKNOWN) + builder จาก observed records + model snapshot จาก core.calculations — ติด label MODEL |
| Assumption completion | `core/assumptions.py` | +16 entries (tick value/size, contract size, volume step, gap, slippage, spread, commission, swap, magic number, order execution, bid/ask, tick-bar-timer, broker margin, cycle start/end rules) — ทั้งหมด UNKNOWN/MODEL ไม่มี VERIFIED ปลอม + ฟิลด์ใหม่ category/confidence/affected_modules/created/updated |
| Cycle verification | `core/model_vs_observed.py` | comparator 6 → **10 checks** (+ cycle start, cycle end, emergency close, resume/new cycle) — ยังไม่ auto-correct และไม่เปลี่ยนสูตรจาก observation |
| Symbol spec | `core/symbol_profile.py` | ฟิลด์ optional ใหม่ (tick_value/currency/quote/base) ค่าที่ไม่รู้ = None (UNKNOWN) |
| Web/API | `web/backend` | GET `/api/evidence` `/api/environment` `/api/parameters` `/api/ex5-integrity` + `/api/assumptions` แสดงฟิลด์ใหม่ — ทุก endpoint เรียก core ล้วน |
| เอกสารจาก source เดียว | `tools/generate_registry_docs.py` | สร้าง `ASSUMPTION_REGISTRY.md` `EVIDENCE_REGISTRY.md` `ENVIRONMENT_PROFILE.md` จาก core เสมอ (ห้ามแก้มือ) |

**ผล tests:** Desktop/Core **228/228** (157 เดิม + 71 ใหม่) · Web **99/99** (93 เดิม + 6 ใหม่) · Integration 18/18 · GUI smoke 11/11 · ไม่มี skipped/errors
รายละเอียดเต็ม: `IMPLEMENTATION_REPORT_PHASE1.md` · ผลตรวจก่อนหน้า: `AUDIT_REPORT.md`

---

## 17. PHASE 2 IMPLEMENTATION (2026-09-24) — MT5 Behavior Verification + Cycle Timeline

เปลี่ยนจาก Cycle Snapshot → ระบบนำเข้าข้อมูล MT5 จริงและตรวจพฤติกรรม EA เทียบ Simulation Model อย่างเป็นระบบ (ยังไม่มี trading ทุกรูปแบบ)

| ของ | ไฟล์ | สรุป |
|---|---|---|
| ObservationSession | `core/observation.py` | session นำเข้าข้อมูลจริง (แยกจาก simulation state) + `ObservationSessionStore` (JSON/versioned) + **ImportResult** (rows_read/imported/rejected/unknown_columns/mapping_used/warnings) + mapping layer ทับ adapter เดิม (alias table เดียว ไม่ normalize ซ้ำ) + Controlled Test Plans A–F |
| Canonical Event | `core/mt5_adapters.py` | BehaviorRecord +commission/swap/spread (None=UNKNOWN ไม่ใช่ 0) +confidence/evidence_ids + LogAdapter ขยาย (EA init/removal/error → UNKNOWN พร้อม note ไม่เดา event) |
| Comparators | `core/behavior_comparators.py` | **6 ตัว**: Grid (8 ด้าน) / Lot (per-level + rounding + volume step) / Buy-Sell / Basket (แยก price/commission/swap/net) / Partial (scope ไม่เดา) / Emergency (แสดง 90.0 E007 และ 50.0 E008 แยกเสมอ) — สถานะ MATCH/PARTIAL_MATCH/MISMATCH/UNKNOWN/INSUFFICIENT_DATA + observed/model/difference/evidence/assumption ครบ |
| Cycle Timeline | `core/cycle.py` | timeline ต่อ cycle (event_sequence/timestamp/positions/lots/pl/equity/margin/dd) + COMPLETE/**INCOMPLETE** (ไม่เติม event ที่ไม่มีหลักฐาน) |
| Report | `core/behavior_report.py` | BEHAVIOR_VERIFICATION_REPORT 15 sections + traceability (evidence/assumption ids) + test plans |
| Model versioning | `core/model_rules.py` | entry +based_on_evidence/previous_version/confirmed_by — **apply โดยไม่มี human confirmation = ถูกปฏิเสธ** (GUI ส่ง confirmation จาก dialog จริง) |
| Web/API | `web/backend/observation_api.py` + `app.py` | POST `/api/observation-sessions` · POST `/{id}/import` · GET `/{id}` `/events` `/comparison` `/timeline` `/report` + GET `/api/test-plans` (import 0 events = ปฏิเสธ) |
| Web GUI | `web/frontend/app.js` | หน้า "Observation": สร้าง session → import → Events/Comparison/Timeline → ดาวน์โหลดรายงาน JSON (ทดสอบในเบราว์เซอร์จริง) |

**ผล tests:** Desktop/Core **286/286** (228→+58) · Web **105/105** (99→+6) · Integration 18/18 · GUI smoke 11/11 · regression pins ไม่เปลี่ยน
หลักคงไว้: ไม่ใช้ performance ยืนยันสูตร · ไม่ auto-correct model (ยืนยันคนเท่านั้น + version ใหม่เสมอ) · ไม่มี fake MT5 data · ไม่มี trading
รายละเอียด: `IMPLEMENTATION_REPORT_PHASE2.md`

---

## 18. PHASE 3 IMPLEMENTATION (2026-09-24) — External Evidence + Myfxbook Verification

| ของ | ไฟล์ | สรุป |
|---|---|---|
| External Evidence v2 | `core/external_evidence.py` | model ครบทุกฟิลด์ตามสเปก + EvidenceSnapshot (content/metrics hash, append-only) + EvidenceLink (supports/contradicts/context_for + human confirm) + conflict detection + SUPERSEDED + quality DIRECT/INDIRECT/CONTEXTUAL/UNKNOWN + **INDIRECT gate: ห้าม myfxbook "supports" สูตร** |
| Myfxbook Importer | `core/myfxbook.py` | URL→fetch/parse/validate→canonical→registry+snapshot · URL normalization (เก็บ original ครบ) · duplicate=เพิ่ม snapshot · เนื้อหาเปลี่ยน=SUPERSEDED+record ใหม่ · IMPORT_FAILED พร้อมเหตุผลจริง (ไม่มี fake fallback) · environment comparison (MATCH/PARTIAL/MISMATCH/UNKNOWN รายฟิลด์) |
| Model Candidates | `core/model_candidates.py` | CANDIDATE/ACCEPTED/REJECTED/SUPERSEDED · accept ต้องมี reviewer + **conflict-free** · accept→ModelVersion ใหม่ (based_on_evidence + confirmed_by) ผ่าน gate เดิม |
| Report | `core/external_report.py` | EXTERNAL_EVIDENCE_REPORT 11 sections + disclaimer "External performance data does not prove internal EA formulas." |
| Web/API | `web/backend/evidence_api.py` + `app.py` | 10 endpoints (external/myfxbook import/{id}/snapshots/link/confirm/unlink/conflicts/report + model-candidates CRUD+confirm/reject) |
| GUI | `web/frontend/app.js` | หน้า "Evidence": import URL → รายการ → รายละเอียด (metrics/snapshots/env-match/links) → confirm → Model Candidates (Accept/Reject มี confirmation) — ทดสอบในเบราว์เซอร์จริง |

**Myfxbook Access Result (จริง):** `IMPORT BLOCKED` — myfxbook.com ตอบ HTTP 403 แก่ probe และยังไม่มี source URL จริงใน Evidence Registry (importer พร้อมใช้ ทดสอบด้วย fixtures 30 กรณี — ไม่มีข้อมูลปลอมใน production)
**ผล tests:** Desktop/Core **333/333** (286→+47) · Web **115/115** (105→+10) · Integration 18/18 · GUI smoke 11/11
รายละเอียด: `IMPLEMENTATION_REPORT_PHASE3.md`
