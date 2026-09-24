# AUDIT REPORT — SNIPER CashFlow (Analyzer)

> วันที่ตรวจ: 2026-09-24 · ประเภท: **AUDIT ONLY** (ไม่แก้โค้ด/ไม่ refactor/ไม่เพิ่ม feature ใด ๆ)
> วิธีตรวจ: อ่านไฟล์จริงทุกส่วน + grep หาสูตรซ้ำ/คุณภาพโค้ด + รัน test suites จริง (ตัวเลขทั้งหมดมาจากการรันปี 2026-09-24)
> หมายเหตุชื่อ: โปรเจกต์เพิ่งเปลี่ยนชื่อแสดงผลเป็น "SNIPER CashFlow" (ฝั่งเว็บ+เอกสาร+หัวรายงาน) — ตัวโปรแกรม Desktop ยังใช้ชื่อเดิม "SNIPER CashFlow Analyzer" ตามกฎห้ามแต้ Desktop

---

## A. Executive Summary

โปรเจกต์นี้**ทำงานได้จริงครบทั้ง 2 แพลตฟอร์ม** (Desktop tkinter 11 หน้า + เว็บที่ deploy ออนไลน์แล้ว) โดยใช้ Calculation Core ชุดเดียวกัน (`core/`) เป็น Source of Truth — ตรวจแล้ว**ไม่พบสูตรซ้ำ (DUPLICATE CALCULATION LOGIC) แม้แต่จุดเดียว** และมี automated tests 250 ตัวผ่านหมด (157 Desktop + 93 Web) รวม parity tests ที่พิสูจน์ว่าเว็บกับ Desktop คำนวณตรงกันเป๊ะ

จุดอ่อนหลักเทียบกับสถาปัตยกรรมที่กำหนด: (1) **ค่า OBSERVED DEFAULT ของ EmergencyDistanceFromCycleUSD = 90.0 จาก installation video ไม่มีอยู่ในระบบ** ขณะที่ default ในโค้ด (50.0) คือค่าเดียวกับ preset $500 — เป็นการรวมสองแนวคิดที่ต้องแยกกัน (2) พารามิเตอร์ #21 ถูกตั้งชื่อ `AccumTargetUSD` ใน source แต่**ไม่มีหลักฐานใน repo** ยืนยันว่าชื่อนี้ตรงกับแถว "ใส่ 0 = ปิดใช้งาน" ของคู่มือ (3) ไม่มีระบบ Environment Profile / Evidence Registry แบบมีโครงสร้าง / Myfxbook (4) ไฟล์ `.ex5` ไม่ได้อยู่ใน repo และไม่มี hash บันทึกไว้ (5) core เป็นแบบ flat ไม่ได้แบ่งเป็น domain/calculations/simulation/verification ตามโครงที่กำหนด — แต่การแบ่งชั้น (core ไม่ import GUI, GUI/web เรียก core) ถูกต้องครบ

---

## B. Current Architecture

### โครงสร้างจริง (99 ไฟล์ ไม่รวม cache/.git)

```
SNIPER-CashFlow-Analyzer/
├── core/                    17 โมดูล pure-Python (GUI-free) — Source of Truth
│   ├── calculations.py      สูตรทั้งหมด (จุดเดียว)
│   ├── config.py            EAConfig 27 params + presets / schema SNIPER_V1_68_CONFIG
│   ├── symbol_profile.py    SymbolProfile + AccountSettings + builtin profiles
│   ├── model_rules.py       SimulationModelRules + ModelVersionStore (SM-### versioning)
│   ├── validation.py        validation กลาง (ERROR/WARNING/INFO)
│   ├── grid.py  worst_case.py  basket.py  risk.py  setbuilder.py   (orchestration)
│   ├── backtest_io.py  backtest_analysis.py                            (import+analyze)
│   ├── mt5_adapters.py      4 adapters + BehaviorRecord + 10 event types
│   ├── model_vs_observed.py compare 6 ด้าน + rule fitting (เสนอเท่านั้น)
│   ├── assumptions.py       AssumptionRegistry 23 รายการ 4 สถานะ + overrides
│   ├── sessions.py          TestSession/SessionStore
│   └── report.py            ReportBundle + export JSON/CSV/HTML
├── desktop/                 tkinter GUI: app.py + app_state.py + theme.py + pages/ 11 หน้า
├── web/                     backend (WSGI stdlib: app/api/parsers/run_server) + frontend (SPA)
├── tests/                   14 ไฟล์ 157 tests + tests/web 3 ไฟล์ 93 tests
├── data/                    model_versions.json (ไฟล์เดียว — ยังไม่มี overrides/sets/sessions จริง)
├── tools/                   สคริปต์ dev/verify (runtime_check, rename_app ฯลฯ)
├── assets/icon.ico          ไอคอนเดียว
└── เอกสาร                   PROJECT_STATUS / WEB_STATUS / WEB_ARCHITECTURE / DEPLOYMENT / README
```

**Entry/Run/Test จริง:** `python run_app.py` (Desktop) · `start_web.bat`/`python web/backend/run_server.py` → http://127.0.0.1:8765 · ออนไลน์ https://sniper-web.onrender.com · Tests: `python run_tests.py` (157), `python run_web_tests.py` (93), `python integration_check.py` (18), `smoke_core.py`, `smoke_gui.py` (11 หน้า) — ตรวจจากไฟล์ ไม่มี build system/dependency ภานอก (stdlib ล้วน, requirements.txt มีไว้เพื่อ PaaS เท่านั้น)

### เทียบกับสถาปัตยกรรมที่กำหนด

| ส่วนที่กำหนด | สถานะ | รายละเอียด |
|---|---|---|
| core/domain (config/symbol/broker/account/environment/cycle/position/event) | **ต่าง/ขาด** | config✓ symbol✓ account✓ broker(ใน symbol_profile+validation)✓ — แต่อยู่รวมกันเป็นไฟล์ flat; **environment/cycle/position ไม่มีเป็น entity**; event มีเฉพาะ BehaviorRecord ฝั่ง observed |
| core/calculations (lot/grid/pnl/margin/drawdown/exposure) | **ตรง (ต่างตำแหน่ง)** | มีครบทุกสูตรใน `calculations.py` ไฟล์เดียว ไม่แยกเป็นโมดูลย่อย |
| core/simulation (grid_simulator/worst_case/basket/lifecycle) | **ตรง 3/4** | grid.py✓ worst_case.py✓ basket.py✓ — **lifecycle (cycle start→…→close) ไม่มี** จำลองเป็น snapshot ตาม depth |
| core/verification (observed/model/comparator/evidence) | **ตรงบางส่วน** | model_vs_observed.py = comparator+observed รวมกัน; **evidence entity ไม่มี** |
| core/assumptions (registry/evidence/versions) | **ตรง 2/3** | registry✓ versions✓ (ModelVersionStore) — evidence ไม่มีแยก |
| core/io (json/csv/mt5_report/myfxbook/sessions) | **ตรง 4/5** | json✓ csv✓ mt5_report✓ sessions✓ — **myfxbook ไม่มี** |
| desktop/ tests/ | **ตรง** | ✓ (และมีเกิน: web/ + parity tests) |

**สรุป:** ไม่มีสิ่งที่ "ผิดตำแหน่ง" หรือ "ซ้ำ" เชิงโครงสร้าง — ทุกอย่างอยู่ใน core ที่ GUI-free; ไม่มี dependency ภายนอกที่ไม่ควรมี (zero third-party); core ไม่ import desktop/web (ทิศทาง dependency ถูก) · พบไฟล์ strays: `nul` (artifact จาก redirect ใน shell — รายงานตามจริง ไม่ลบตามกฎ)

---

## C. Existing Features (Implementation Audit)

| Module | มีแล้ว | ทำงานจริง | Partial | Placeholder | ยังไม่มี | หมายเหตุ (ไฟล์/หลักฐาน) |
|---|---|---|---|---|---|---|
| EA Configuration | ✅ | ✅ | | | | config.py EAConfig 27 params + schema versioned |
| Parameter Model | ✅ | ✅ | | | | to_dict/from_dict + parameter_meta (ลำดับ=คู่มือ) |
| Presets | ✅ | ✅ | | | | builtin_presets: Default/$500/$3000 (config.py:140-166) |
| Grid Calculator | ✅ | ✅ | | | | grid.py build_grid_table + หน้า GUI/web |
| Lot Calculator | ✅ | ✅ | | | | calculations.py lot_for_level/lots_for_levels |
| Basket Calculator | ✅ | ✅ | | | | basket.py simulate_basket |
| Partial Close | ✅ | ✅ | | | | calculations.py partial_* + basket.py |
| Risk Calculator | ✅ | ✅ | | | | risk.py build_risk_summary + flags (threshold แก้ได้) |
| Margin Calculator | ✅ | ✅ | | | | calculations.py margin_used |
| Drawdown Calculator | ✅ | ✅ | | | | drawdown_percent + DrawdownEpisode (backtest_analysis) |
| Worst Case Simulator | ✅ | ✅ | | | | worst_case.py 3 scenarios × moves |
| Backtest Import | ✅ | ✅ | | | | backtest_io.py (csv/html/txt tolerant) |
| Backtest Analyzer | ✅ | ✅ | | | | backtest_analysis.py (grid depth/lot/episodes/streak) |
| Set Builder | ✅ | ✅ | | | | setbuilder.py build/evaluate/filter (ไม่มี ranking) |
| Set Comparison | ✅ | ✅ | | | | SetStore + desktop/pages/compare.py |
| Behavior Verification | ✅ | ✅ | | | | desktop/pages/behavior.py + sessions |
| Assumption Registry | ✅ | ✅ | | | | assumptions.py — 23 รายการ 4 สถานะ + override persist |
| Evidence Registry | | | ⚠️ Partial | | | เป็นเพียงฟิลด์ source/evidence (ข้อความ) บน assumption + report_files ใน session — **ไม่มี Evidence entity (ID/Type/Confidence)** |
| MT5 Test Data Pipeline | ✅ | ✅ | | | | mt5_adapters.py 4/4 adapters |
| Model vs Observed | ✅ | ✅ | | | | model_vs_observed.py — 6 checks MATCH/MISMATCH/UNKNOWN |
| Test Session | ✅ | ✅ | | | | sessions.py (JSON/ไฟล์, schema versioned) |
| External Evidence Import (Myfxbook ฯลฯ) | | | | | ❌ | ไม่พบ myfxbook ใด ๆ ทั้งโปรเจกต์ |
| Environment Profile | | | ⚠️ Partial | | | มีเฉพาะ SymbolProfile+AccountSettings (symbol spec/account) — ไม่มี Platform/Broker/AccountType/Timeframe เป็น record |
| Import / Export | ✅ | ✅ | | | | ProjectData JSON (SNIPER_PROJECT_V1) + sets export/import |
| Report Generator | ✅ | ✅ | | | | report.py JSON/CSV/HTML (HTML พิมพ์ PDF ได้) |
| Desktop GUI | ✅ | ✅ | | | | 11 หน้า (smoke ผ่านจริง) + toolbar 6 action |
| Settings (GUI) | ✅ | ✅ | | | | แก้ registry/rules/profile/thresholds ได้ |
| Validation | ✅ | ✅ | | | | validation.py กลาง (ดู M. ด้านล่าง) |
| Tests | ✅ | ✅ | | | | 250 automated + 18 integration + 2 smoke |
| Web/API (เกินสเปกเดิม) | ✅ | ✅ | | | | 11 endpoints + SPA + parity 21 checks + deploy จริง |

**สรุป:** ไม่มี Placeholder/Mock ปลอมแม้แต่จุดเดียว — `_draw_placeholder` ใน desktop/pages/backtest.py:50 คือข้อความ empty-state จริง ("No balance curve available…") ไม่ใช่ข้อมูลปลอม

---

## D. Missing Features

1. **Evidence Registry เชิงโครงสร้าง** — Evidence ID/Source/Type/Version/ObservedValue/Claim/Status/Confidence/Notes
2. **External Evidence / Myfxbook import** — ไม่มีแนวคิด/โค้ดเลย
3. **Environment Profile** — Platform/Broker/AccountType/Symbol/Timeframe เป็น observed record (XM Global/Hedge/GOLDmicro/M15 ไม่ถูกเก็บที่ใด)
4. **OBSERVED DEFAULT 90.0** ของ EmergencyDistanceFromCycleUSD (ดู G)
5. **Cycle lifecycle simulation** (start→adds→partial→close/emergency→restart เป็น timeline)
6. **Check: Cycle start/end** ใน Model-vs-Observed (ปัจจุบัน 6/8 ด้าน)
7. Assumption entries สำหรับหัวข้อที่ยังไม่มี (13 หัวข้อ — ดู H)
8. **.ex5 hash/integrity record** — ไฟล์ไม่อยู่ใน repo และไม่มี hash อ้างอิง (ดู O)
9. Tick value/tick size/tick-bar-timer/gap/slip page ทางการเงินใน symbol profile (มี tick_size แล้วแต่ไม่มี tick_value)

---

## E. Duplicate Logic (SSOT Audit)

**ผล: ไม่พบ DUPLICATE CALCULATION LOGIC** — ตรวจด้วย grep จริงทั้งโปรเจกต์:

| สูตร | จุดที่ "คำนวณ" จริง | จุดอื่นที่พบชื่อสูตร | สรุป |
|---|---|---|---|
| Lot = BaseLot × Multiplier^(n-1) | `core/calculations.py:69` **จุดเดียว** | risk.py (เทียบ threshold), validation.py (ตรวจค่า), dashboard.py (แสดงค่า), setbuilder/compare (ส่งค่าเข้า cfg → core คำนวณต่อ) | ไม่ซ้ำ — ทุกจุดเรียก/แสดง ไม่คำนวณเอง |
| `**` (ยกกำลัง) ทั้งโปรเจกต์ | calculations.py:69 | model_vs_observed.py:311,313 — **curve-fitting ข้อมูล observed** (least-squares หา multiplier ที่"เหมาะกับข้อมูลจริง"เพื่อเสนอ rule) | ไม่ใช่สูตร EA ซ้ำ — เป็นการวิเคราะห์ observed data (ระบุไว้ชัดใน docstring "NEVER changes the model") |
| Margin = lot×cs×price/lev×rate | `calculations.py:166` จุดเดียว | `desktop/pages/settings.py:63` — ปรากฏเป็น**ข้อความช่วยเหลือ** ("Margin model: lots × contract × price / leverage × rate") | ซ้ำเชิง"เอกสาร"เท่านั้น (display text) — ไม่มีการคำนวณ |
| P/L, exposure, drawdown, margin level | calculations.py จุดเดียว | — | ไม่ซ้ำ |
| Web frontend (JS) | ไม่มีสูตร | มี test guard-rail บังคับ (`test_web_api.py` ห้าม Math.pow/**/Math.log ใน app.js) | ไม่ซ้ำ + มี enforcement |
| Validation | `validation.py` กลาง | `web/backend/parsers.py` ตรวจเชิงโครงสร้าง (ชนิด/ขอบเขต/unknown key) ก่อนส่งเข้า core validate | ไม่ใช่สูตรซ้ำ — เป็น API input guard บาง ๆ |

สถานะเป้าหมาย `ONE CORE CALCULATION → Desktop/Web/Reports` **เป็นจริงแล้วในปัจจุบัน** (Desktop GUI/web backend/report ทั้งหมดเรียก `core.*` และมี parity tests 250 ตัวยืนยัน)

---

## F. Formula Audit

| Formula (ไฟล์:บรรทัด) | Source | Status |
|---|---|---|
| Lot = BaseLot × LotMultiplier^(level−1) (calculations.py:69) | โมเดลจำลอง (LOT_FORMULA_ASSUMPTION_001) | **MODEL — NOT VERIFIED INTERNAL EA FORMULA** ✓ ระบบระบุถูกต้องและไม่เคยเรียกว่า "EA จริง" |
| Lot normalize → round ตาม lot step (calculations.py:43) | โมเดล | MODEL |
| Grid entry = start ∓ (n−1)×GridStep (calculations.py:104) | GRID_TRIGGER/GRID_DIRECTION_ASSUMPTION_001 | MODEL |
| levels = floor(move/step)+1 (calculations.py:122) | โมเดล | MODEL |
| P/L = diff × lot × contract_size (calculations.py:137) | PL_CONVERSION_ASSUMPTION_001 (ไม่รวม spread/commission/swap) | MODEL |
| Exposure = lot × cs × price (calculations.py:155) | EXPOSURE_ASSUMPTION_001 | MODEL |
| Margin = lot × cs × price / leverage × margin_rate (calculations.py:160) | MARGIN_ASSUMPTION_001 | MODEL |
| DD% = |min(PL,0)| / capital ×100 (calculations.py:169) | โมเดล | MODEL |
| Margin level % = equity/margin×100 (calculations.py:176) | โมเดล | MODEL |
| เด้งกลับถึง target = (target−PL)/sensitivity (calculations.py:186) | โมเดล | MODEL |
| Partial volume/realized = % pro-rata (calculations.py:207-215) | PARTIAL_CLOSE_ASSUMPTION_001 | MODEL |
| GridStepUSD = ระยะราคาระหว่างไม้ | คู่มือผู้ขาย (GRID_DISTANCE_DOC_001) | VERIFIED (จากเอกสาร) |
| Basket close เมื่อกำไรรวมถึง BasketCloseAllUSD | คู่มือ (BASKET_CLOSE_DOC_001) | VERIFIED (จากเอกสาร) |
| Partial ครั้งเดียว/รอบเมื่อ OnlyOnce=true | คู่มือ (PARTIAL_ONCE_DOC_001) | VERIFIED (จากเอกสาร) |
| เวลาทั้งหมดเป็นเวลาไทย ICT | คู่มือ (THAI_TIME_DOC_001) | VERIFIED (จากเอกสาร) |
| Emergency เกิดเมื่อราคาเกินระยะจากกรอบเทรด | คู่มือ (EMERGENCY_DOC_001) + กรอบอ้างอิงเป็นโมเดล (EMERGENCY_FRAME_ASSUMPTION_001) | VERIFIED(เงื่อนไข) + MODEL(กรอบ) |

**OBSERVED สูตร: ยังไม่มี** (สถานะ OBSERVED_FROM_TESTING มีในระบบแต่ยังไม่มีรายการใดใช้ — ตรงตามจริงเพราะยังไม่มีหลักฐานทดสอบถูกบันทึก)

---

## G. Parameter Audit

### 27/27 พารามิเตอร์มีครบ (config.py) — จุดที่ต้องรายงานเป็นพิเศษ:

| # (ตามลิสต์ที่กำหนด) | ในโปรเจกต์ | หลักฐานใน source | ปัญหา |
|---|---|---|---|
| 1 Symbol | `TradeSymbol` | config.py:32 + **มี UNKNOWN entry ครบ: SYMBOL_INPUT_NAME_UNKNOWN_001** | — (ทำถูกแล้ว) |
| 6 UseMartingale | `UsePositionSizeOptimization` | config.py:39 + USEMARTINGALE_NAMING_NOTE_001 (VERIFIED ว่าเป็นชื่อเดียวกัน) | — (documented) |
| **21 UNKNOWN ("ใส่ 0 = ปิดใช้งาน")** | **`AccumTargetUSD`** | **config.py:59 + parameter_meta บรรทัด 122 — ชื่อนี้เป็นชื่อที่มีอยู่ใน source ณ ตำแหน่ง #21 พอดี** | ⚠️ **ไม่มีหลักฐานใน repo** (คู่มือ PDF/ข้อความ "ใส่ 0 = ปิดใช้งาน" ไม่ได้อยู่ในโปรเจกต์) ยืนยันว่าชื่อ AccumTargetUSD ตรงกับแถวนั้นของคู่มือไม่ได้ และ**ไม่มี assumption/UNKNOWN entry ครอบคลุมการตั้งชื่อนี้** |

### ค่าพารามิเตอร์ (Value Audit)

| ชุดค่า | สถานะ | ที่มา |
|---|---|---|
| Default | ✅ มี — EAConfig defaults | config.py (อ้างคู่มือ PDF) |
| Recommended $500 | ✅ มี — "Seller preset - Capital $500" | config.py _preset_500 |
| Recommended $3000 | ✅ มี — "Seller preset - Capital $3000" (step 4.8/lot 0.18/mult 1.08/basket 8.88/trigger 1.0/Fri 08:00) | config.py _preset_3000 |
| User-defined | ✅ รองรับ — แก้ได้ทุกตัว + save/load project JSON + SetStore | GUI/web |
| **Observed from installation video** | ❌ **ไม่มีในระบบ** | — |

### ⚠️ ปัญหาสำคัญ: EmergencyDistanceFromCycleUSD

- ในโค้ดมีค่าเดียว: **default = 50.0** (config.py:55) และ **preset $500 = 50.0** (preset ใช้ defaults)
- ข้อมูล OBSERVED จาก installation video ว่า **default จริง = 90.0 ไม่ถูกบันทึกที่ใดในโปรเจกต์** (grep `90.0` ทั้ง repo ไม่พบในบริบทนี้)
- **รายงานตามที่โจทย์กำหนด: ปัจจุบันระบบมีเพียงค่าเดียว (50.0) ซึ่งเป็นค่า preset** ส่วน OBSERVED DEFAULT 90.0 หายไป — สองแนวคิดที่ต้องแยก (`OBSERVED DEFAULT = 90.0` / `RECOMMENDED PRESET = 50.0`) ถูกยุบเป็นค่าเดียวโดยปริยาย → **ไม่ควรปล่อยไว้แบบนี้ในรอบ implementation ถัดไป**

---

## H. Assumption Audit

ระบบแยก 4 สถานะได้จริง: `VERIFIED_FROM_DOCUMENTATION / OBSERVED_FROM_TESTING / MODEL_ASSUMPTION / UNKNOWN` (assumptions.py:23-26) + registry 23 รายการ + override พร้อม evidence persist

ความครอบคลุมตามลิสต์ที่กำหนด (27 หัวข้อ):

| หัวข้อ | สถานะ | Assumption ID |
|---|---|---|
| Grid trigger | ✅ | GRID_TRIGGER_ASSUMPTION_001 |
| Lot rounding | ✅ | LOT_NORMALIZATION_ASSUMPTION_001 |
| **Cycle definition** | ❌ MISSING | — (ไม่มีนิยาม "รอบ" เป็น assumption) |
| Basket scope | ✅ | BASKET_SCOPE_ASSUMPTION_001 |
| Basket P/L accounting | ✅ (ผ่าน BASKET_SCOPE + PL_CONVERSION) | — |
| Partial close scope | ✅ | PARTIAL_CLOSE_ASSUMPTION_001 |
| Main side definition | ⚠️ Partial | TRAILING_LOGIC_ASSUMPTION_001 แตะผิวเผิน |
| Emergency reference | ✅ | EMERGENCY_FRAME_ASSUMPTION_001 (+EMERGENCY_DOC_001) |
| **Daily target accounting** | ❌ MISSING | — |
| **Friday behavior** | ❌ MISSING | (มีเฉพาะเวลา THAI_TIME) |
| **Monday behavior** | ❌ MISSING | — |
| Maximum grid | ✅ | MAX_GRID_DEPTH_UNKNOWN_001 |
| **Magic number** | ❌ MISSING | — |
| **Order execution** | ❌ MISSING | — |
| **Bid/Ask behavior** | ❌ MISSING | — |
| **Tick/bar/timer behavior** | ❌ MISSING | — |
| **Gap behavior** | ❌ MISSING | — |
| Commission | ✅ (ระบุว่าไม่รวม) | PL_CONVERSION_ASSUMPTION_001 |
| Swap | ✅ (ระบุว่าไม่รวม) | PL_CONVERSION_ASSUMPTION_001 |
| **Slippage** | ❌ MISSING | — |
| Spread | ✅ (ระบุว่าไม่รวม) | PL_CONVERSION_ASSUMPTION_001 |
| Broker margin | ✅ | MARGIN_ASSUMPTION_001 (hedged/tiered ระบุไว้) |
| Contract size | ✅ | XAUUSD_CONTRACT_ASSUMPTION_001 |
| Tick size | ⚠️ ใช้ใน validation (EXTREME_SMALL_STEP) แต่ไม่มี assumption entry | — |
| **Tick value** | ❌ MISSING | — |
| Volume min/max/step | ✅ | LOT_STEP_BOUNDARY_ASSUMPTION_001 |
| Both-sides-at-start | ✅ | BOTH_SIDES_OPEN_AT_START_ASSUMPTION_001 |

**นับได้: ✅ 14 · Partial 2 · MISSING 11** (นอกเหนือจากนี้ยังมี entry เสริม: TRAILING, USEMARTINGALE_NAMING, THAI_TIME, EA_BEHAVIOR_NOT_VERIFIED)

---

## I. Evidence Audit

- **สิ่งที่มีจริง:** ฟิลด์ `source` (ข้อความอ้างอิง เช่น "Manual p.4 sections 8-9") + ฟิลด์ `evidence` บนทุก assumption; `set_status()` บันทึก evidence พร้อม override ลง `data/assumptions_overrides.json`; TestSession เก็บ `report_files` + `observed_events`
- **สิ่งที่ขาด:** ไม่มี Evidence entity แบบมีโครงสร้าง (Evidence ID / Source / Type / Version / Observed Value / Claim / Status / Confidence / Notes)
- แหล่งหลักฐานที่รองรับโดยพฤตินัย: EA Documentation ✅ (baseline registry) · Parameter Guide ✅ (ผ่าน source strings) · MT5 CSV ✅ · MT5 HTML Report ✅ · MT5 Journal ✅ (LogAdapter) · Manual Observation ✅ (ManualAdapter+sessions) · **Preset Image ⚠️ (อ้างถึงในคอมเมนต์เท่านั้น ไม่มีไฟล์/record) · Installation Video ❌ · Myfxbook ❌**
- ✅ หลักปลอดภัยถูกต้อง: ไม่มีกลไกใด "เชื่อ" external evidence เป็นสูตร EA อัตโนมัติ (ไม่มีตัวเชื่อมด้วยซ้ำ ในรอบนี้)

---

## J. Environment Audit

- **ไม่มี Environment Profile** เป็น concept — สิ่งที่ใกล้เคียง: `SymbolProfile` (name/contract_size/tick_size/lot_min/max/step/digits/reference_price) + `AccountSettings` (leverage/margin_rate/currency) = ครอบคลุมเฉพาะ symbol specification + account เลขศาสตร์
- **Environment ที่ observe ไว้ (MT5 / XM Global / Hedge / GOLDmicro / M15) ไม่ถูกเก็บในระบบแม้แต่จุดเดียว** (grep ทั้ง repo ไม่พบ) → ตามกฎต้องระบุว่าเป็น `OBSERVED TEST ENVIRONMENT` ที่**หายไป** ไม่ใช่ข้อกำหนด universal — ปัจจุบันระบบก็ไม่ได้ hard-code broker/symbol เป็นกฎทั่วไปอยู่แล้ว (default XAUUSD ระบุชัดว่าเป็น "editable starting point" + มี assumption entry) ✓
- ไม่มีการเก็บ account number ในโครงสร้างข้อมูลใด ✓

---

## K. MT5 Pipeline Audit (ตรวจจาก mt5_adapters.py จริง)

- **Adapters 4/4 ตามที่กำหนด:** CSVAdapter (header aliases) · TesterReportAdapter (ผ่าน parse_backtest_file) · LogAdapter (keyword rules ลำดับความสำคัญ) · ManualAdapter + factory `load_adapter` ✓
- **Event schema: 16/16 fields ตรงตามลิสต์ที่กำหนด** (timestamp/symbol/event/side/ticket/grid_level/lot/price/balance/equity/margin/free_margin/floating_pl/basket_pl/position_count/total_lots/drawdown) **+ source + note = 19 ช่อง** (mt5_adapters.py:44-71)
- **Events 10/10:** NEW_CYCLE, OPEN_POSITION, ADD_GRID, PARTIAL_CLOSE, BASKET_CLOSE, EMERGENCY, FRIDAY_STOP, DAILY_TARGET, RESUME, UNKNOWN ✓
- หมายเหตุความซื่อสัตย์: TesterReportAdapter สร้าง events จาก deals แบบ derived (ระบุใน note ทุก record ว่า derived) — ไม่อ้างว่าเป็น log จริงของ EA ✓

---

## L. Model vs Observed Audit

- มีระบบเปรียบเทียบจริง: `compare_behavior()` 6 checks — Grid spacing ✅ · Lot progression ✅ · Grid level sequence ✅ · Basket close ✅ · Partial close ✅ · Position count/total lots ✅ → ผล **MATCH / MISMATCH / UNKNOWN** ✓
- **ขาด: Cycle start/end check** (8 ด้านที่กำหนด มี 6)
- ✅ กฎสำคัญครบ: ห้าม auto-change — `suggest_lot_rule_from_observed()` เสนออย่างเดียว ("This NEVER changes the model"); การเปลี่ยนเกิดได้ผ่าน `ModelVersionStore.apply_new_version()` เมื่อผู้ใช้ยืนยันเท่านั้น + บันทึกเป็น version ใหม่ (SM-###) พร้อม timestamp/changes และมี regression tests คุมพฤติกรรมนี้ (tests/test_model_vs_observed.py 13 tests)

---

## M. GUI Audit (Desktop ตรวจจากไฟล์จริง + smoke รันจริง)

| หน้า | มีจริง | ใช้งานจริง | คำนวณจริง | เชื่อม Core | Mock/Placeholder/Broken |
|---|---|---|---|---|---|
| Dashboard | ✅ | ✅ | ✅ (risk summary) | ✅ validation+risk | — |
| EA Settings | ✅ | ✅ | ✅ (validate) | ✅ config+validation | — |
| Grid Calculator | ✅ | ✅ | ✅ | ✅ grid+basket | — |
| Worst Case | ✅ | ✅ | ✅ | ✅ worst_case | — |
| Risk | ✅ | ✅ | ✅ | ✅ risk | — |
| Backtest | ✅ | ✅ | ✅ (import+analyze) | ✅ backtest_io/analysis | — (empty-state curve = ข้อความจริง ไม่ใช่ mock) |
| Set Builder | ✅ | ✅ | ✅ | ✅ setbuilder | — |
| Compare | ✅ | ✅ | ✅ | ✅ setbuilder/config | — |
| Behavior Verification | ✅ | ✅ | ✅ | ✅ sessions+model_vs_observed | — |
| Reports | ✅ | ✅ | ✅ | ✅ report+ทุก calculator | — |
| Settings | ✅ | ✅ | ✅ (เขียนจริง) | ✅ assumptions+model_rules+symbol_profile | — |

- Toolbar: **New / Open / Save / Import / Export / Reset ครบ 6 ตัว เชื่อม handler จริง** (desktop/app.py:82-84)
- Smoke test จริง: 11/11 หน้า ไม่มี crash (`smoke_gui.py` = "GUI SMOKE OK")
- เว็บ (นอกเหนือขอบเขตเดิมแต่รายงานให้ครบ): 9 หน้า + คู่มือ + โหมดการ์ดมือถือ — ทดสอบ browser จริง + parity แล้ว (WEB_STATUS.md)

---

## N. Validation Audit

`core/validation.py` เป็น centralized validation ตัวเดียว (GUI/web เรียกผ่านมันทั้งหมด) — ครอบคลุมทุกข้อที่กำหนด:

| กฎ | มี | รหัสในโค้ด |
|---|---|---|
| Capital > 0 / ทุนไม่พอ | ✅ | CAPITAL_POSITIVE · INSUFFICIENT_CAPITAL |
| GridStep > 0 | ✅ | GRID_STEP_POSITIVE |
| BaseLot > 0 | ✅ | BASELOT_POSITIVE |
| Multiplier > 0 | ✅ | MULTIPLIER_POSITIVE |
| Basket target >= 0 | ✅ | BASKET_TARGET_NON_NEGATIVE |
| Partial % 0–100 | ✅ | PARTIAL_PERCENT_RANGE |
| Lot ต่ำกว่าขั้นต่ำโบรกเกอร์ | ✅ | BASELOT_BELOW_MIN |
| Lot เกินขั้นสูงสุด | ✅ | BASELOT_ABOVE_MAX |
| Volume step (ไม่ตรง step) | ✅ | BASELOT_NOT_ON_STEP |
| Extreme parameters | ✅ | EXTREME_MULTIPLIER · EXTREME_SMALL_STEP · MULTIPLIER_BELOW_ONE |
| Invalid input (ชนิด/เวลา) | ✅ | TIME_FORMAT + type coercion + web structural guard |
| Broker constraints | ✅ | LEVERAGE_POSITIVE · CONTRACT_SIZE_POSITIVE · LOT_STEP_POSITIVE |

จุด validate ซ้ำ: ไม่มี (web มีเพียง input guard บาง ๆ ก่อนส่งต่อ — ไม่ใช่ validation ธุรกิจซ้ำ)

---

## O. Test Audit (รันจริงวันที่ 2026-09-24)

| ชุด | Total | Passed | Failed | Skipped | Errors |
|---|---|---|---|---|---|
| Desktop (`run_tests.py`, 14 ไฟล์) | **157** | **157** | 0 | 0 | 0 |
| Web (`run_web_tests.py`, 3 ไฟล์) | **93** | **93** | 0 | 0 | 0 |
| Integration workflow | 18 checks | 18 | 0 | 0 | 0 |
| smoke_core / smoke_gui | OK / 11 หน้า | — | 0 | 0 | 0 |

- ความครอบคลุมตามลิสต์ที่กำหนด: default config ✅ · lot ✅ · grid ✅ · cumulative ✅ · basket ✅ · partial ✅ · worst case ✅ · DD ✅ · margin ✅ · validation ✅ · import/export ✅ · preset ✅ · assumption registry ✅ · regression pins ✅ · (เกิน) web parity + upload security + JS guard-rails
- **Coverage tool: ไม่มี** (โปรเจกต์ไม่ใช้ dependency ภายนอก) — ระบุตามจริง
- ไม่ได้แก้ test ใด ๆ เพื่อให้ผ่าน (audit only)

---

## P. EX5 Integrity

- `find *.ex5` ทั้งโปรเจกต์: **ไม่พบไฟล์** → ไฟล์ `SNIPER CashFlow V 1.68.ex5` ไม่ได้อยู่ใน repo (ผู้ใช้เก็บแยกในเครื่อง MT5)
- **ไม่มี hash (SHA-256/MD5) ของ .ex5 ถูกบันทึกที่ใด** (grep ทั้งโปรเจกต์)
- ด้านความปลอดภัย: โค้ดทั้งโปรเจกต์**ไม่มีการ decompile/modify/อ้างอิงไบนารี .ex5 ใด ๆ** (ไม่มีเส้นทางโค้ดที่แตะไฟล์นี้เลย) ✓ — แต่**ไม่สามารถพิสูจน์ integrity ของตัวไฟล์ได้**เพราะไม่มีตัวต้นฉบับ/hash ในระบบ → แนะนำ (ไว้รอบ implementation): บันทึก SHA-256 + ขนาดไฟล์เป็น metadata อย่างเดียว (อ่านค่าได้ ห้ามแตะเนื้อไฟล์)

---

## Q. File / Code Quality

- **TODO/FIXME/mock/fake: ไม่พบ** (คำว่า `todo` ที่พบใน web/backend/parsers.py:51-61 เป็น**ชื่อตัวแปร** ใน loop อ่าน body ไม่ใช่หมายเหตุค้างงาน)
- **"placeholder":** พบ 2 กลุ่ม — (1) attribute `placeholder=` ของ HTML input ในเว็บ (ข้อความช่วยเหลือ ปกติ) (2) `_draw_placeholder` = empty-state message จริง ไม่ใช่ fake data
- **Hard-coded result: ไม่พบ** — ค่าทั้งหมดมาจาก calculation จริง (มี regression pins ใน test เท่านั้น ซึ่งเป็นหน้าที่ของ test)
- **Dead code/unused module: ไม่พบ** ใน core/desktop (ทุกโมดูลถูกเรียกใช้/มี test); โฟลเดอร์ `tools/` เป็น dev-scripts โดยเจตนา
- **Inconsistent naming เล็กน้อย:** โปรเจกต์ใช้ชื่อใหม่ "SNIPER CashFlow" บนเว็บ/เอกสาร แต่ Desktop GUI ยังเป็น "SNIPER CashFlow Analyzer" (ตามกฎห้ามแตะ Desktop — รอคำสั่ง) · ไฟล์ `nul` หลุดเข้ามาใน root (artifact ของ shell redirect — ไม่ลบตามกฎ audit)
- **Duplicated model/config: ไม่พบ** (EAConfig ตัวเดียว, presets อ้างตำแหน่งเดียว)
- **Circular dependency: ไม่มี** — `validation.py` import `calculations` แบบ deferred ในฟังก์ชัน (มีคอมเมนต์อธิบาย) เพื่อกัน cycle ตอนโหลดโมดูล; core ไม่ import desktop/web ทั้งสิ้น

---

## R. REQUIRED ARCHITECTURE GAP REPORT (CURRENT → REQUIRED → GAP → PRIORITY)

| # | CURRENT | REQUIRED | GAP | PRIORITY |
|---|---|---|---|---|
| 1 | EmergencyDistance มีค่าเดียว 50.0 (=ค่า preset) | OBSERVED DEFAULT 90.0 แยกจาก RECOMMENDED PRESET 50.0 | ค่า observed 90.0 ไม่ถูกบันทึก/แยกไว้ | **P0** |
| 2 | .ex5 ไม่อยู่ใน repo + ไม่มี hash | บันทึก hash/size เพื่อพิสูจน์ integrity | ไม่มี record ใด | **P0** |
| 3 | #21 ชื่อ AccumTargetUSD ไม่มีหลักฐาน/assumption ครอบ | ชื่อ unknown ต้องมี evidence trail หรือ UNKNOWN entry | ไม่มีทั้งสอง | **P1** |
| 4 | จำลองแบบ snapshot ตาม depth | cycle lifecycle (start→adds→partial→close/emergency→resume) | ไม่มี entity/ตัวจำลอง timeline | **P1** |
| 5 | assumption 23 รายการ | ครอบ 27 หัวข้อที่กำหนด | ขาด 11 หัวข้อ (H) | **P1-P2** |
| 6 | evidence = ข้อความบน assumption | Evidence entity (ID/Type/Version/ObservedValue/Claim/Confidence) | ไม่มีโครงสร้าง | **P2** |
| 7 | ไม่มี Environment Profile | Platform/Broker/AccountType/Symbol/TF เป็น OBSERVED record (XM/Hedge/GOLDmicro/M15) | ไม่มี | **P2** |
| 8 | Model-vs-Observed 6 checks | 8 checks รวม cycle start/end | ขาด 2 | **P2** |
| 9 | io มี json/csv/mt5_report/sessions | เพิ่ม myfxbook | ไม่มี | **P2** |
| 10 | core flat (17 ไฟล์) | แบ่ง domain/calculations/simulation/verification/assumptions/io | ต่างโครงสร้าง (แต่ layering/SSOT ถูกแล้ว) | **P4** (พลิกใหญ่ ควรทำเมื่อเสถียร) |
| 11 | GUI 11 หน้าครบตามของเดิม | หน้า Environment/Evidence (เมื่อมี feature ข้อ 6-7) | ยังไม่มีของให้แสดง | **P3** |

## S. Recommended Next Implementation Order (เสนอเท่านั้น — ยังไม่ทำ)

1. **P0:** เพิ่มการบันทึก OBSERVED DEFAULT `EmergencyDistanceFromCycleUSD = 90.0` (จาก installation video) แยกจาก preset 50.0 + evidence record ประกอบ
2. **P0:** บันทึก SHA-256 + ขนาดของ `SNIPER CashFlow V 1.68.ex5` (metadata เท่านั้น)
3. **P1:** สร้าง UNKNOWN/assumption entry ให้ parameter #21 + ผูก evidence ก่อนยืนยันชื่อ AccumTargetUSD
4. **P1:** Cycle lifecycle entity + ตัวจำลอง timeline + check "cycle start/end" ใน Model-vs-Observed
5. **P2:** Evidence Registry (entity มีโครงสร้าง) → รองรับ Installation Video/Preset Image เป็น source type
6. **P2:** Environment Profile (OBSERVED TEST ENVIRONMENT) — ไม่ hard-code เป็นกฎ
7. **P2:** เติม assumption 11 หัวข้อที่ขาด (ค่าเริ่ม = UNKNOWN)
8. **P2:** io/myfxbook (external evidence import แบบ OBSERVED แยกจาก MODEL ชัดเจน)
9. **P3-P4:** หน้า GUI ใหม่ตาม feature ข้างบน → ค่อยพิจารณารื้อ core เป็นโครง domain/… เมื่อทุกอย่างนิ่ง (มี 250 tests เป็น safety net)

---

*รายงานนี้สร้างโดยการตรวจไฟล์จริงเท่านั้น — ไม่มีการแก้ไขโค้ด/ไฟล์ใด ๆ นอกจากไฟล์รายงานนี้*
