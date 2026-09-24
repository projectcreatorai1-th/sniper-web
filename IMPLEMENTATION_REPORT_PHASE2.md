# IMPLEMENTATION REPORT — PHASE 2

> วันที่: 2026-09-24 · SNIPER CashFlow Analyzer · MT5 Behavior Verification + Cycle Timeline
> ทำต่อจาก Phase 1 (baseline: Desktop 228/228 · Web 99/99 · Integration 18/18 · GUI smoke 11/11 — ถูก freeze ก่อนเริ่มและยังเขียวทุกตัวหลังจบ)

---

## Baseline (freeze ก่อนเริ่ม — รันจริง)

```
Desktop/Core : 228/228 OK      Web : 99/99 OK
Integration  : 18/18 OK        GUI smoke : 11/11 OK
```

## Changes (สรุป)

เพิ่มระบบนำเข้าข้อมูล MT5 จริง → ตรวจพฤติกรรม EA V1.68 เทียบ Simulation Model (OBSERVED vs MODEL vs UNKNOWN) พร้อม traceable evidence ทุกจุด — โดยไม่แตะสูตร/preset/พารามิเตอร์เดิม และไม่มีการเทรดใด ๆ

## Files Added

| ไฟล์ | เนื้อหา |
|---|---|
| `core/observation.py` | ObservationSession (+Store, schema versioned) · ImportResult + CSV import พร้อม mapping layer/รายงานครบ (rows_read/imported/rejected/unknown_columns/mapping_used/warnings) · Controlled Test Plans A–F |
| `core/behavior_comparators.py` | Comparators 6 ตัว + BehaviorCheckResult (check_id/observed/model/difference/status/evidence_ids/assumption_ids/notes) + สถานะ 5 ระดับ |
| `core/behavior_report.py` | BEHAVIOR_VERIFICATION_REPORT ครบ 15 sections + traceability |
| `web/backend/observation_api.py` | handlers สำหรับ observation endpoints (เรียก core ล้วน) |
| `tests/test_observation.py` | 16 tests (session/store/import/mapping/duplicates/test plans) |
| `tests/test_behavior_comparators.py` | 24 tests (grid/lot/buysell/basket/partial/emergency/aggregate) |
| `tests/test_behavior_report.py` | 12 tests (15 sections + timeline + traceability + 90/50) |
| `tests/web/test_web_observation.py` | 6 tests (endpoints end-to-end + security) |
| `tools/patch_frontend_observation.py` | สคริปต์ใส่หน้า Observation (dev tool) |

## Files Modified

| ไฟล์ | การเปลี่ยน |
|---|---|
| `core/mt5_adapters.py` | Canonical event: +commission/swap/spread (None=UNKNOWN) +confidence/evidence_ids; CSV aliases + commission/swap/spread (ตารางเดียวร่วมกับ importer); LogAdapter + รูปแบบ EA init/removal/error → EVENT_UNKNOWN พร้อม note (ห้ามเดา event) |
| `core/cycle.py` | + `build_cycle_timeline`/`build_cycle_timelines` (COMPLETE/INCOMPLETE + missing list — ไม่เติม event ที่ไม่มี) |
| `core/model_rules.py` | ModelVersionEntry + based_on_evidence/previous_version/confirmed_by; **apply_new_version ปฏิเสธถ้าไม่มี confirmed_by** |
| `desktop/pages/behavior.py` | ส่ง confirmed_by/based_on_evidence จาก confirmation dialog จริงที่มีอยู่ (ไม่เปลี่ยน UX) |
| `web/backend/app.py` | routing แบบ path-param สำหรับ `/api/observation-sessions/*` + `/api/test-plans` (method gates ตรวจก่อนอ่าน body) |
| `web/frontend/app.js` | หน้า "Observation" (สร้าง session/import/events/comparison/timeline/ดาวน์โหลดรายงาน) + เมนู |
| `tests/test_setbuilder.py` | version test ส่ง confirmed_by + assertions ฟิลด์ใหม่ + **test ใหม่: ไม่ยืนยัน = ปฏิเสธ** (เข้มขึ้น ไม่ใช่อ่อนลง) |
| `PROJECT_STATUS.md` | +หัวข้อ 17 Phase 2 |

## Tests Added

**Desktop/Core: +58** (observation 16 · comparators 24 · report+timeline 12 · versioning +6 รวมในชุด) → **286/286**
**Web: +6** → **105/105**

## Test Results (รันจริงหลังเสร็จ)

```
Desktop/Core : 286/286 PASS (0 failed/skipped/errors)
Web          : 105/105 PASS (0 failed/skipped/errors)
Integration  : 18/18 PASS
GUI smoke    : 11/11 PASS
Regression pins : 0.15 / 1.85 / 11 / 1.95 / −3255 / 651% — ไม่เปลี่ยนแม้แต่ตัวเดียว
Browser จริง : หน้า Observation สร้าง session จริงผ่าน UI + Events panel แสดงผลจริง
```

การแก้ test เดิม 2 จุด (ระบุตามจริง): (1) `test_model_vs_observed` pin 6→10 checks จาก Phase 1 (2) `test_setbuilder` version test ปรับให้ส่ง confirmed_by และเพิ่ม test ปฏิเสธ — ทั้งคู่เป็นผลของ requirement ใหม่โดยตรง และ **assertions เข้มขึ้น ไม่มีการปิด/ลด**

## Import Results (ตัวอย่างจริงจาก test fixture)

CSV 4 แถว → rows_read 4 · rows_imported 4 · rows_rejected 0 · commission/swap แยกครบ (-0.20/-0.05) · แถวไม่มี timestamp = rejected พร้อม warning · คอลัมน์แปลก = unknown_columns · duplicate = skipped พร้อม warning · mapping ผู้ใช้ทับ alias ได้ (timestamp→T ฯลฯ) · import ที่ได้ 0 events = API ปฏิเสธ (EMPTY_IMPORT)

## Behavior Verification Results (ตัวอย่างจาก fixtures ที่ทดสอบจริง)

- Grid: exact spacing MATCH / ผิด 8.0 = MISMATCH / ไม่มีราคา = INSUFFICIENT_DATA / **gap 2 ชั้น = UNKNOWN** (ห้ามเดา)
- Lot: exact MATCH / diff ภายใน step = MATCH (rounding) / บางระดับ = PARTIAL_MATCH / ทั้งหมด = MISMATCH / ไม่มีข้อมูล = INSUFFICIENT_DATA
- Buy/Sell: both-at-start สอดคล้อง = MATCH (ระบุ "NOT an EA rule claim") / ฝั่งเดียว vs config = MISMATCH / scope = UNKNOWN
- Basket: target ±0.5 / **price vs commission vs swap vs net แยกชัด** — ไม่มีค่าใช้จ่าย = UNKNOWN (ไม่สมมติ basket P/L = price P/L)
- Partial: trigger/pct ตรวจได้เมื่อมี before/after · scope = UNKNOWN จนกว่าจะมีหลักฐาน (ไม่เลือก interpretation เอง)
- Emergency: **แสดง OBSERVED 90.0 (E007) และ PRESET 50.0 (E008) แยกเสมอ** · ระยะจริง ≈90 ขณะ config=50 → MISMATCH + "no auto-correction" · ≈50 → MATCH · ขาด reference → UNKNOWN

## Cycle Timeline

COMPLETE เมื่อครบ start+entry+terminal+timestamps · ขาด = INCOMPLETE พร้อมรายับ "missing" (terminal event/timestamps ฯลฯ) · emergency cycle → EMERGENCY_CLOSED · resume → new cycle · **ไม่เติม event ที่ไม่มีหลักฐาน** (test ยืนยัน)

## Model Versions

apply โดยไม่มี confirmed_by = ValueError · version ใหม่เก็บ based_on_evidence/previous_version/confirmed_by · historical version ไม่ถูก overwrite (SM-001 → SM-002 …) · GUI ใช้ dialog ยืนยันเดิมส่ง confirmed_by จริง

## Evidence / Assumptions

ทุก check แนบ assumption_ids (เช่น GRID_TRIGGER_ASSUMPTION_001, PRICE_GAP_ASSUMPTION_001) และ evidence_ids (E007/E008/session:OBS-xxx) — ตรวจกลับได้ทั้งใน comparison และ report (ส่วน Evidence/Assumptions) · ไม่มี UNKNOWN ถูกเปลี่ยนเป็น VERIFIED ด้วย confidence

## Unknowns (ยังอยู่ตามจริง)

Gap หลายชั้น · bid/ask · tick-bar-timer · magic number · order execution · commission/swap/spread จริง (ถ้า source ไม่มี) · partial scope · basket scope · PARAM #21 · EX5 internal ทั้งหมด

## Remaining Gaps

(1) Myfxbook importer จริง (ยังเป็น interface) (2) Desktop GUI ยังไม่มีหน้า Observation แบบเต็ม (ใช้ Web UI — desktop behavior page เดิมยังทำงานเหมือนเดิม) (3) ยังไม่มี timeline simulator เชิงราคา-เวลา (4) per-position lot tracking สำหรับ partial scope ที่ละเอียดกว่านี้

## Regression

Baseline ทั้งหมดยังเขียว + pins เหมือนเดิม (ดู Test Results) · ไม่มีสูตรเปลี่ยน · ไม่มี preset/parameter เปลี่ยน

## Next Phase (แนะนำ)

1. Myfxbook/external importer จริง (แยก EXTERNAL OBSERVED EVIDENCE) 2. Desktop GUI หน้า Observation/Evidence 3. ต่อ observation sessions เข้า Model versioning flow (review evidence → confirm rule) 4. timeline simulator แบบราคา-เวลา 5. เมื่อ stable → ออกแบบ OUR EA Strategy Engine แยกตามแผน

---

## คำรับรอง (ตามข้อกำหนด)

```
No EX5 modification            ✓
No EX5 decompilation           ✓
No live trading                ✓ (ไม่มี order/MT5 connection ใด ๆ — READ/IMPORT/ANALYZE/SIMULATE/VERIFY เท่านั้น)
No fake observations           ✓ (ไม่มีข้อมูล MT5 ปลอมใด ๆ — ทุกอย่างมาจาก import/session จริง; fixtures มีเฉพาะใน tests)
No automatic model correction  ✓ (confirmed_by gate + tests)
No duplicate calculation engine ✓ (model values มาจาก core.calculations/config เท่านั้น)
No formula changed without evidence ✓ (ไม่มีสูตรเปลี่ยนเลยในรอบนี้)
```

## ACCEPTANCE CRITERIA — ผลตรวจ (27/27)

- [x] ObservationSession exists · [x] Canonical MT5 Event Model exists (+cost fields, None≠0)
- [x] All 4 adapters feed canonical model · [x] CSV import works (mapping + reporting)
- [x] Journal/log import works where format permits (init/removal/error → UNKNOWN ไม่เดา)
- [x] Unknown data remains UNKNOWN · [x] Grid comparator · [x] Lot comparator · [x] Buy/Sell comparator
- [x] Basket comparator (cost separation) · [x] Partial comparator · [x] Emergency comparator (90/50 แยกพร้อม source)
- [x] Cycle timeline works · [x] 5 สถานะ MATCH/PARTIAL/MISMATCH/UNKNOWN/INSUFFICIENT_DATA
- [x] Evidence traceability · [x] Assumption traceability · [x] Model versions preserved (+ confirmation required)
- [x] No automatic model correction · [x] No duplicate calculation logic · [x] No fake MT5 data
- [x] No live trading · [x] Existing regression green · [x] New tests pass
- [x] Behavior Verification Report works (15 sections) · [x] PROJECT_STATUS.md updated
