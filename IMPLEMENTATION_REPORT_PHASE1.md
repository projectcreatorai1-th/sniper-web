# IMPLEMENTATION REPORT — PHASE 1

> วันที่: 2026-09-24 · SNIPER CashFlow Analyzer · Evidence + Environment + Cycle Foundation
> ทำต่อจาก baseline เดิมโดยตรง (ไม่สร้างโปรเจกต์ใหม่) — เอกสารอ้างอิง: `AUDIT_REPORT.md`

---

## Changes made (สรุป)

เพิ่ม foundation 5 ด้านจาก gap ระดับ P0/P1 ของ audit **โดยไม่แตะสูตร ไม่เปลี่ยน preset ไม่เปลี่ยนพารามิเตอร์เดิม ไม่รื้อ architecture** — ตัวเลข Calculator ทุกตัวคงเดิม (ยืนยันด้วย regression pins ท้ายรายงาน)

## Files changed (แก้)

| ไฟล์ | การเปลี่ยน |
|---|---|
| `core/assumptions.py` | เพิ่มฟิลด์ `category/confidence/affected_modules/created_at/updated_at` (optional, legacy ใช้ได้เหมือนเดิม) + **16 entries ใหม่** (สถานะ UNKNOWN 14 / MODEL 2 — ไม่มี VERIFIED ปลอม) |
| `core/model_vs_observed.py` | comparator 6 → **10 checks**: + Cycle start / Cycle end / Emergency close / Resume-new cycle (MATCH/MISMATCH/UNKNOWN, ไม่ auto-correct) |
| `core/symbol_profile.py` | ฟิลด์ optional ใหม่ `tick_value/currency/quote_currency/base_currency` (default None = UNKNOWN) — ค่าเดิมทั้งหมดไม่เปลี่ยน |
| `web/backend/api.py` | `/api/assumptions` แสดงฟิลด์ใหม่ + เพิ่ม 4 GET endpoints (เรียก core ล้วน) |
| `web/backend/app.py` | ลงทะเบียน route `/api/evidence` `/api/environment` `/api/parameters` `/api/ex5-integrity` |
| `tests/test_assumptions.py` | +5 tests (Phase 1 completion) |
| `tests/test_model_vs_observed.py` | pin จำนวน checks 6→10 (ผลของการขยาย comparator ตามสเปก มิใช่การลดการตรวจ — เพิ่ม assertion ชื่อ check ใหม่ครบ 4 ตัว) |
| `integration_check.py` | pin 6→10 ด้วยเหตุผลเดียวกัน (มีคอมเมนต์กำกับ) |
| `PROJECT_STATUS.md` | +หัวข้อ 16 Phase 1 |

## Files added (สร้างใหม่)

| ไฟล์ | เนื้อหา |
|---|---|
| `core/evidence.py` | EvidenceRegistry (CRUD + persistence `data/evidence.json`) + seeds E001–E010 + สถานะ DOCUMENTED/OBSERVED/MODEL/UNKNOWN + 9 source types + `ExternalEvidence` (Myfxbook = INTERFACE READY) |
| `core/environment.py` | `EnvironmentProfile` + `BrokerProfile` + `observed_test_environment()` (OBSERVED TEST ENVIRONMENT — ไม่มี field account number โดยเจตนา) |
| `core/param_facts.py` | `ParameterFact`/`ParameterValueRecord` — PARAM_18 (Emergency: 90.0 OBSERVED / 50.0 RECOMMENDED / 50.0 EA DEFAULT-MODEL แยกกันชัด) + PARAM_21 (UNKNOWN, AccumTargetUSD = UNVERIFIED CANDIDATE) |
| `core/ex5_integrity.py` | คำนวณ SHA-256/MD5 **จากไฟล์จริงเท่านั้น** + สถานะ (ปัจจุบัน `SOURCE_FILE_NOT_PRESENT`) + historical baseline เก็บแยกเป็น `RECORDED_EXTERNAL_BASELINE` |
| `core/cycle.py` | `Cycle` + สถานะ OPEN/CLOSED/EMERGENCY_CLOSED/UNKNOWN + `build_cycles_from_records()` (observed) + `model_cycle()` (เรียก core.calculations เท่านั้น) + rules ติด label MODEL |
| `tests/test_evidence.py` | 15 tests |
| `tests/test_environment.py` | 11 tests |
| `tests/test_param_facts.py` | 9 tests |
| `tests/test_ex5_integrity.py` | 10 tests |
| `tests/test_cycle.py` | 21 tests |
| `tests/web/test_web_registry.py` | 6 tests (endpoints ใหม่ผ่าน WSGI จริง) |
| `tools/generate_registry_docs.py` | เรนเดอร์เอกสารจาก core (single source) |
| `ASSUMPTION_REGISTRY.md` `EVIDENCE_REGISTRY.md` `ENVIRONMENT_PROFILE.md` | เอกสารที่ generate อัตโนมัติ (ห้ามแก้มือ) |

## Tests added

**Desktop/Core: +71** (evidence 15 · environment 11 · param_facts 9 · ex5 10 · cycle 21 · assumptions+5) → รวม **228**
**Web: +6** (registry endpoints) → รวม **99**

## Test Results (รันจริงหลัง implementation เสร็จสมบูรณ์)

| ชุด | ผล |
|---|---|
| Desktop/Core (`run_tests.py`) | **228/228 PASS** — 0 failed / 0 skipped / 0 errors |
| Web (`run_web_tests.py`) | **99/99 PASS** — 0 failed / 0 skipped / 0 errors |
| Integration | **18/18 PASS** |
| GUI smoke | **11/11 หน้า PASS** |
| Core smoke | PASS |
| Baseline เปรียบเทียบ | 157→228 และ 93→99 (เพิ่มล้วน ไม่มีตัวเดิมถูกลบ/ปิด) |

## Evidence added

E001 (EA version 1.68, DOCUMENTED) · E002–E006 (MT5 / XM Global / Hedge / GOLDmicro / M15, OBSERVED จาก installation video, ระบุ "not proof of internal EA logic") · **E007 (Emergency observed default = 90.0, OBSERVED)** · **E008 ($500 recommended = 50.0, DOCUMENTED)** · E009 ($3000 as-supplied/unverified) · E010 (EX5 SHA-256/MD5 historical baseline)

## Assumptions added (16)

UNKNOWN 14: TICK_VALUE · TICK_SIZE · VOLUME_STEP · PRICE_GAP (gap over multiple grid levels) · SLIPPAGE · SPREAD · COMMISSION · SWAP · MAGIC_NUMBER · ORDER_EXECUTION · BID_ASK · TICK_BAR_TIMER · BROKER_MARGIN · (CONTRACT_SIZE เป็น MODEL เพราะเป็นนิยามโมเดลที่ configurable)
MODEL 2: CYCLE_START_RULE · CYCLE_END_RULE (ติดข้อความ "MODEL — NOT VERIFIED INTERNAL EA BEHAVIOR")
ทุกรายการมี ID/Title/Category/Status/Description/Source/Confidence/Created-Updated ✓ · **ไม่มีรายการใดถูกตั้งเป็น VERIFIED โดยไม่มีหลักฐาน** (มี test บังคับ)

## Environment support

`EnvironmentProfile` ครบ fields ที่กำหนด + บันทึก OBSERVED TEST ENVIRONMENT (MT5/XM Global/Hedge/GOLDmicro/M15/EA 1.68) · ระบุชัดว่า M15/XM/GOLDmicro **ไม่ใช่ข้อกำหนด universal** · **ไม่มี account number field** + leverage เป็น user-settable · `BrokerProfile` แยกต่างหาก (ค่าที่ไม่รู้ = UNKNOWN ไม่ปลอม)

## Cycle support

`Cycle` model ครบ fields (cycle_id/start-end time/symbol/direction/prices/lots/levels/profits/status/events) · สถานะ 4 แบบ · builder แยก observed (`build_cycles_from_records`) กับ model (`model_cycle` — เรียก `core.calculations.build_side_positions` เท่านั้น) · กติกา start/end ติด label MODEL · partial ไม่ปิดรอบ · cycle ที่ถูกแทนที่โดยไม่มี terminal event = UNKNOWN (ไม่เดา)

## EX5 integrity status

**`SOURCE_FILE_NOT_PRESENT`** — ไฟล์ `SNIPER CashFlow V 1.68.ex5` ไม่อยู่ใน workspace → ไม่สร้างไฟล์ปลอม ไม่ fabricate hash (มี test บังคับ) · historical SHA-256 `31E5…CE37` + MD5 `3972…750A` เก็บเป็น `RECORDED_EXTERNAL_BASELINE` · เมื่อมีไฟล์จริง (`SNIPER_EX5_PATH` หรือวางใน project) ระบบจะคำนวณจากไฟล์และเทียบ → INTEGRITY MATCH / MISMATCH (มี test ครบทั้ง 3 กรณี)

## Parameter #21

`PARAM_21`: Status = **UNKNOWN**, Candidate Internal Name = `AccumTargetUSD` (**UNVERIFIED CANDIDATE**), Evidence = NONE (ไม่มีรายการ E ใดอ้างถึง) · ไม่เปลี่ยนชื่อในโค้ด · UI/API/เอกสารแสดงเป็น "UNKNOWN PARAMETER #21" เท่านั้น (มี test บังคับว่า candidate ไม่กลายเป็น VERIFIED)

## Regression Result

Golden pins **ไม่เปลี่ยนแม้แต่ตัวเดียว** (รันจริงหลังเสร็จ): lots ชั้น 5 = 0.15 · cumulative 11 ชั้น = 1.85 · Worst case $50 BOTH = 11 levels / 1.95 lots / −3,255.00 / DD 651% — ตรงกับ `tests/test_regression.py` เป๊ะ · `EAConfig` default EmergencyDistance ยังเป็น 50.0 และ preset $500/$3000 ไม่ถูกแตะ (มี test guard)

## Remaining Unknowns (ยังไม่เดา — ตามจริง)

Parameter #21 ตัวตน · ค่า tick value/tick size/commission/swap/spread จริงของโบรกเกอร์ที่สังเกต · พฤติกรรม gap หลายชั้น / bid-ask / tick-bar-timer / magic number / order execution · EX5 internal ทั้งหมด · hash ปัจจุบันของไฟล์จริง (ยังไม่มีไฟล์)

## Remaining Gaps

(1) External evidence importer จริง (Myfxbook) — ตอนนี้มีเฉพาะ interface (2) Desktop GUI ยังไม่มีหน้าแสดง Evidence/Environment (เลือกเปิดเผยผ่าน Web API ก่อน — ไม่สร้างหน้า mock ตามกฎ) (3) cycle lifecycle เป็น snapshot/builder ยังไม่ใช่ timeline simulator เต็มรูปแบบ (4) evidence ยังไม่ถูก auto-link เข้า assumption entries รายตัว (ทำ manual ผ่าน evidence_ids)

## Next Recommended Phase

1. Desktop GUI: หน้า Evidence/Environment/EX5 (อ่านจาก core จริง) 2. Myfxbook importer จริง (แยก OBSERVED EXTERNAL DATA ออกจาก MODEL เสมอ) 3. Cycle timeline simulation + ผูก cycle เข้า Worst Case 4. เชื่อม evidence_ids ↔ assumption set_status อัตโนมัติ (ยังต้องมี human confirm)

## คำรับรองตามข้อกำหนด

```
No .ex5 modification          ✓ (ไม่มีโค้ดใดแตะไฟล์; hash คำนวณแบบอ่านเท่านั้น)
No .ex5 decompilation         ✓
No duplicate calculation engine ✓ (cycle/param facts ไม่มีสูตร; model_cycle เรียก calculations.py)
No fake data                  ✓ (ทุก UNKNOWN แสดงเป็น UNKNOWN; มี tests บังคับ)
No mock implementation        ✓
No automatic model correction ✓ (comparator เพิ่มเฉพาะการ "ตรวจ" — และยังห้าม apply โดยไม่ยืนยัน)
No live trading functionality ✓
```

## ACCEPTANCE CRITERIA — ผลตรวจ

- [x] 90.0 observed stored separately from 50.0 preset (PARAM_18 สาม records + E007/E008 + tests)
- [x] Emergency value source traceable ("Installation Video — วิธีติดตั้ง EA SNIPER.mp4" + note)
- [x] EX5 historical SHA-256/MD5 record exists (E010 + ex5_integrity)
- [x] Missing EX5 does not create fake file (test_no_fake_file_created)
- [x] Parameter #21 remains UNKNOWN
- [x] AccumTargetUSD not incorrectly marked VERIFIED (test บังคับ)
- [x] 11 missing assumptions registered (+5 เพิ่มเติม = 16)
- [x] EnvironmentProfile exists
- [x] observed MT5/XM/Hedge/GOLDmicro/M15 stored (OBSERVED TEST ENVIRONMENT)
- [x] SymbolProfile exists (ขยาย optional fields โดยค่าเดิมไม่เปลี่ยน)
- [x] BrokerProfile exists
- [x] Cycle lifecycle model exists
- [x] Cycle verification exists (10 checks ครอบคลุม 8 หัวข้อที่กำหนด)
- [x] EvidenceRegistry exists
- [x] ExternalEvidence model/interface exists (INTERFACE READY)
- [x] No duplicate calculation logic
- [x] Existing tests remain green (157→228, 93→99 — เพิ่มล้วน)
- [x] New tests pass
- [x] PROJECT_STATUS.md updated
- [x] Implementation report created (ไฟล์นี้)
