# PHASE 6 BASELINE REPORT (GATE-6.1)

ตรวจก่อน implementation — 2026-09-25 · repository `SNIPER-CashFlow-Analyzer` @ `main` (tree clean)

## Boundary / Integrity (PASS)

- git root = `C:/Users/BANK/.zcode/workspace/default/SNIPER-CashFlow-Analyzer` ✅
- Frozen model hash `124F08984284E880F268C3…` ✅ match sidecar
- SSOT `core/calculations.py` hash `0E1A81FE063310D4…` ✅ match freeze record
- Baseline tests: 391/391 core+forensics+SSOT · 125/125 web (ยังผ่านอยู่ ณ commit `241d499`)

## Existing Modules (Analyzer — READ-ONLY สำหรับ Phase 6)

| กลุ่ม | ไฟล์ | LOC | บทบาท |
|---|---|---|---|
| core/ | 31 | 7,604 | SSOT formulas, registries, sim views (calculations/evidence/cycle/basket/risk/worst_case/timeline/…) |
| core/forensics/ | 9 | 1,216 | Phase 5 forensic engines (mt5_report, cycle_reconstruction, lot/grid/partial/basket/emergency/recovery) |
| web/backend/ | 8 | 1,905 | Analyzer HTTP API |
| tools/ | 23 | 4,028 | Phase scripts (read-only history) |
| tests/ + web + forensics | 38 | ~6,000 | 391+125 tests |

## Existing Execution / Risk / Simulators

- **ไม่มี execution code จริง**: ไม่มี order/dispatch/adapter ใด (ค้น `trade(` = 0 ไฟล์) —
  Analyzer เป็น **view/simulation เชิงคำนวณล้วน** (worst_case/timeline เป็น pure functions)
- **risk**: `core/risk.py` = risk *summary ของ grid view (ไม่ใช่ guard), `core/setbuilder.py` = set ประเมินค่า
- **config**: `core/config.py` = EAConfig (analyzer preset) — OUR EA จะมี config schema ของตัวเอง (§34)
- **UI**: SPA `web/frontend/app.js` (hash routing) — Phase 6 เพิ่มหน้าแยกที่ `web/frontend/our_ea/` + registration เท่านั้น

## Duplicate / Conflicting Logic Scan

- **สูตร lot**: มี 2 จุดโดยตั้งใจ — SSOT `core/calculations.py` (floor, แก้แล้ว Phase 5.3) และ
  `core/forensics/lot_engine.py` (forensic verification) — ทั้งคู่ผูกกันด้วย
  `tests/forensics/test_ssot_consistency.py` (L1–L50 เท่ากันเป๊ะ)
  → OUR EA จะมี lot engine ของตัวเองใน `core/our_ea/lot_engine.py` **ห้าม import ทั้งสอง**
  และต้องผ่าน equivalence test เช่นเดียวกัน (§18)
- **cycle/basket logic**: `core/cycle.py`, `core/basket.py` = Analyzer model view;
  `core/forensics/cycle_reconstruction.py` = forensic — OUR EA สร้างใหม่แยกอิสระ
- ไม่พบ conflicting formula อื่น (Phase 5.3 ตรวจ duplicate แล้ว)

## สิ่งที่ต้องสร้างใหม่ทั้งหมด (ไม่มีอยู่เดิม)

execution abstraction · state machine · event system · idempotency · persistence ·
recovery · broker constraints · risk guard (policy) · replay engine · simulation
engine · failure injection · config schema · observability · OUR EA UI ·
paper/demo adapters · live lock

## GATE-6.1 BASELINE: **PASS**
