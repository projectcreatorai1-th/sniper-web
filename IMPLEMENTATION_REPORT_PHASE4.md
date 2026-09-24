# IMPLEMENTATION REPORT — PHASE 4

> วันที่: 2026-09-24 · SNIPER CashFlow Analyzer · Timeline Simulator + Desktop Evidence
> Baseline (freeze ก่อนเริ่ม): Desktop 333/333 · Web 115/115 · Integration 18/18 · GUI smoke 11/11

---

## Baseline

หยุดก่อนแก้และรันทุกชุดจริง — เขียวทั้งหมด

## Architecture Changes

ไม่รื้อ — เพิ่ม `core/timeline_simulation.py` เป็น orchestration layer ใหม่เหนือ `core/calculations` (SSOT) โดยตรง · worst-case timeline เป็น **visualization layer** เรียก engine เดิม (pins ไม่เปลี่ยน)

## Files Added

| ไฟล์ | เนื้อหา |
|---|---|
| `core/timeline_simulation.py` | TimelineSimulation (READY/RUNNING/COMPLETE/INCOMPLETE/ERROR) · PriceBar (bid/ask/spread = UNKNOWN ถ้าไม่มี ไม่ fabricate) · `generate_scenario()` 9 presets (NORMAL_UP/DOWN/RANGE/LONG_*/SHARP_REVERSAL/V_SHAPE/GAP_*) · TimelineEventEngine (walks price series → CYCLE_START/ENTRY/GRID/PARTIAL/BASKET_CLOSE/EMERGENCY/CYCLE_END + equity/margin/exposure/DD) · `worst_case_timeline()` (view บน SSOT) · `compare_model_simulation()` (Observed/Model/Simulation — MODEL_ONLY เมื่อไม่มี observed) · SimulationTrace + build_trace · immutability (model_version snapshot ณ สร้าง) |
| `web/backend/timeline_api.py` | list_scenarios · run_simulation · worst_case · export (JSON/CSV/HTML) · observation_picker · validate_observation_link (REJECT ถ้า id ไม่มีจริง) |
| `desktop/pages/evidence.py` | Desktop Evidence page จริง — Import Myfxbook / View detail / Link to Assumption / Link Observation (picker) / Confirm link / Unlink / Conflicts display / Candidate reject — ใช้ core registries เดียวกับ Web (ไม่มี store แยก) |
| `tests/test_timeline_simulation.py` | 32 tests (price series / scenarios / event engine / worst-case SSOT pins / trace / immutability / model-vs-simulation / performance 1k-100k) |
| `tests/web/test_web_timeline.py` | 10 tests (endpoints / SSOT pins ผ่าน API / export 3 ฟอร์แมต / picker validate / method gates) |
| `tools/patch_frontend_timeline.py` | สคริปต์ใส่หน้า Timeline (dev tool) |
| `EVIDENCE_SUFFICIENCY_REVIEW.md` | สรุปสถานะทุกกฎ → VERIFIED 3 / PARTIAL 1 / MODEL 10 / UNKNOWN 1 · **ยังไม่พอสำหรับ OUR EA** |

## Files Modified

| ไฟล์ | การเปลี่ยน |
|---|---|
| `desktop/app.py` | +EvidencePage (11→12 หน้า) |
| `web/backend/app.py` | routing `/api/timeline/*` + `/api/observation-picker*` + แก้ local import shadow |
| `web/frontend/app.js` | +หน้า "Timeline" (Scenario Builder + events + trace + export) + ปุ่ม "ดู Timeline" ในหน้า Worst Case |
| `PROJECT_STATUS.md` | +หัวข้อ 19 Phase 4 |

## Timeline Engine

- **Price Series**: PriceBar (mid/bid/ask/spread) — ถ้ามีเฉพาะราคาเดียว bid/ask/spread = None (UNKNOWN) · ห้าม fabricate spread
- **Input Modes**: OBSERVED_SERIES / SYNTHETIC_SERIES / SCENARIO — synthetic ติด label เสมอ + ไม่เข้า Evidence Registry (ไม่มี code path ใดเชื่อม)
- **Event Engine**: walks bars → ตรวจ basket close → partial → emergency → grid add · ทุก event มี `assumption_ids` + `label="MODEL ASSUMPTION"` · costs (commission/swap/spread/net_pnl) = None (UNKNOWN)
- **Margin/Exposure**: ทุก event มี equity/margin/free_margin/margin_level/exposure/drawdown จาก core.calculations

## Scenario Engine

9 presets ครบตามสเปก + Scenario Builder บน Web (start_price/bars/step/side/capital) · ทุก scenario = SYNTHETIC / TEST DATA

## Worst Case Integration

`worst_case_timeline()` เรียก `simulate_worst_case()` เดิม (SSOT) แล้วแปลงเป็น events — **test ยืนยัน pins เดิม (11/1.95/−3255/651%) ผ่าน API ไม่เปลี่ยน** · ใน Web GUI มีปุ่ม "ดู Timeline ของ Worst Case" ในหน้า Worst Case

## Evidence Desktop GUI

12 หน้าแล้ว (เพิ่ม Evidence) · อ่านจาก ExternalEvidenceStore / EvidenceLinkStore / ModelCandidateStore / AssumptionRegistry — **core เดียวกับ Web** (ไม่มี store แยก) · Actions: Import / View / Link Assumption / Link Observation (picker) / Confirm / Unlink / Conflicts display / Candidate reject · Observation picker ตรวจ session และ event index จริง (REJECT ถ้าไม่มี)

## Observation Picker

Web: `POST /api/observation-picker` (list sessions + events) + `POST /api/observation-picker/validate` (REJECT ถ้า session/event ไม่มีจริง — ไม่สร้าง reference ปลอม) · Desktop: Combobox เลือก session + Entry ใส่ event index พร้อม validate

## Traceability

`SimulationTrace`: simulation_id · model_version · assumption_ids · evidence_ids · parameter_snapshot · environment_profile · created_at · input_mode · synthetic — ครบตามสเปก · **Immutability**: simulation เก่าอ้าง model version เก่าตลอดไป (test ยืนยัน SM-001 → SM-002 → sim1 ยัง SM-001)

## Export

JSON (traceability ครบ: simulation + trace + model_vs_simulation) · CSV (event table) · HTML (report + SYNTHETIC banner + MODEL ASSUMPTION labels)

## Performance Test

| Events | เวลาจริง | ผ่าน? |
|---|---|---|
| 1,000 bars | <0.01s | ✓ (<5s) |
| 10,000 bars | ~0.05s | ✓ (<30s) |
| 100,000 bars | ~0.15s | ✓ (<120s) |

(เครื่องนี้: Python 3.12 · core.calculations เร็วมากเพราะ pure arithmetic)

## Tests Added

**+42** (desktop 32 · web 10) → รวม **365 desktop · 125 web · GUI 12 pages**

## Tests Passed (รันจริงหลังเสร็จ)

```
Desktop/Core : 365/365 PASS (0 failed/skipped/errors)
Web          : 125/125 PASS (0 failed/skipped/errors)
Integration  : 18/18 PASS
GUI smoke    : 12/12 PASS
Regression pins : ไม่เปลี่ยน (ยืนยันผ่าน worst-case timeline API)
```

## Regression

Baseline ครบ · ไม่ลด tests · ไม่เปลี่ยน pins · ไม่เปลี่ยนสูตร

## Remaining Gaps

(1) ยังไม่มี MT5 observation จริง (EVIDENCE_SUFFICIENCY_REVIEW ระบุชัด) (2) observation → evidence → model navigation ยังไม่มี visual chain บน Web (3) Timeline output ยังเป็นตาราง (ไม่มี price chart — สเปกบอกไม่ต้องสร้าง chart engine ใหม่) (4) synthetic price generator ยังง่าย (ไม่มี volatility model)

## Recommendation

**ต้องมีข้อมูล MT5 จริงก่อน OUR EA** — ระบบ infrastructure ครบทุกชั้นแล้ว (import → compare → candidate → confirm → model version → simulate → timeline) ขาดเพียงข้อมูลจริงจาก MT5 ซึ่งผู้ใช้ต้อง:
1. Export deals/backtest จาก MT5 Strategy Tester → import ผ่านหน้า Observation
2. หรือบันทึก manual observation ตาม Controlled Test Plans A–F
3. หรือให้ URL Myfxbook บัญชีจริง (แต่ยังโดน 403)

---

## คำรับรอง

```
Observed ≠ Synthetic        ✓ (แยกโดย input_mode + synthetic flag + label)
Synthetic ≠ Evidence        ✓ (ไม่มี code path ใดเก็บ synthetic เข้า Evidence Registry)
Model ≠ Verified Behavior   ✓ (ทุก event ติด MODEL ASSUMPTION · comparator ไม่เขียน VERIFIED)
Simulation ≠ Live Trading   ✓ (ไม่มี order/MT5/order ใด ๆ)
No EX5 modification/decompilation ✓
No fake evidence            ✓ (fixtures เฉพาะใน tests)
```
