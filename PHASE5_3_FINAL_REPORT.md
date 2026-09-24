# PHASE 5.3 FINAL REPORT — OWNER CONFIRMATION + EVIDENCE FREEZE

**ดำเนินการตามคำตัดสินของเจ้าของโปรเจกต์ (PROJECT_OWNER, 2026-09-24) ทุกขั้นตอน — หยุดพร้อมเข้าสู่ Phase 6**

---

## 1. Confirmed Candidates (7)

| Candidate | Rule | หลักฐาน | ผลการยืนยัน |
|---|---|---|---|
| MC-001 | Lot floor ladder `floor(0.10×1.10^(n-1)/0.01)×0.01` | E012, E028 | ACCEPTED — SSOT เดิม (round) = INVALID |
| MC-002 | Grid spacing ≈ 5 USD | E013 | ACCEPTED — เก็บ distribution + tolerance (ไม่ยกเป็น 5.0000) |
| MC-003 | BUY adds DOWN / SELL adds UP | E014 | ACCEPTED |
| MC-004 | Both-sides initial exposure | E015 | ACCEPTED — คง 99.4% + exceptions |
| MC-007 | Normal resume ≤ 2s | E018 | ACCEPTED — restart recovery แยกเป็นคนละ rule |
| MC-008 | Base lot = 0.10 | E015 | ACCEPTED |
| MC-009 | PARTIAL_EXISTS (deal-level) | E025 | ACCEPTED — เฉพาะ EXISTS; TRIGGER/VOLUME=UNKNOWN, LEVEL=PARTIAL คงเดิม |

## 2. Rejected / Superseded

- **AccumulatorTargetUSD = 1.68 (per basket) → REJECTED AS V1.68 BEHAVIOR**
  (E027: violations 90.70% บน 860 ตะกร้า — ตามคำตัดสินเจ้าของ; ห้ามสร้าง 1.00 เป็น verified)
- MC-005 → **SUPERSEDED** → MC-009 (เก็บไว้ในประวัติ ไม่ลบ)

## 3. Partial Candidates (คง CANDIDATE/PARTIAL)

- MC-006 Basket trigger: ยืนยันเฉพาะ "domain ≈ +$1" · **1.68 REJECTED** · ชุด hypotheses
  ที่ยัง compatible ({GROSS≥1.00, lots×0.50, lots×0.85}) คงไว้ใน registry
- Grid Trigger Semantics = PARTIAL (H_PREV_ENTRY กับ H_EXTREME ยังแยกไม่ได้)
- Partial Level Rule = PARTIAL (FIFO-feasible 390 / ambiguous 102)

## 4. Unknown Candidates (คง UNKNOWN)

Partial Trigger · Partial Volume Rule · **Emergency Mechanism** (0 events — ห้ามตีความว่า "ไม่มี") ·
**Restart Recovery** (เก็บ `TEST_R_RESTART_RECOVERY` spec ไว้ทำ controlled test ในอนาคต)

## 5. SSOT Diff

```diff
- core/calculations.py :: normalize_lot
- steps = round(raw_lot / profile.lot_step)            # round-to-nearest
+ steps = math.floor(raw_lot / profile.lot_step + 1e-9) # FLOOR (MC-001)
```

- ค้นหาทั้ง repository: **ไม่พบ duplicate formula** — lot computation ทั้งหมดไหลผ่าน
  `core/calculations.py` จุดเดียว (ยืนยันด้วย test ใหม่ `test_ssot_consistency.py`)
- Assumption Registry (persisted overrides): `LOT_FORMULA_ASSUMPTION_001`,
  `LOT_NORMALIZATION_ASSUMPTION_001`, `GRID_DIRECTION_ASSUMPTION_001`,
  `BOTH_SIDES_OPEN_AT_START_ASSUMPTION_001` → MODEL_ASSUMPTION → **OBSERVED_FROM_TESTING**
- Regression pins ที่อัปเดตตามค่า floor (13 จุด core + 10 จุด web — ตรวจ arithmetic ทุกตัว):
  L5 0.15→**0.14** · L7 0.18→**0.17** · L10 0.24→**0.23** · preset-3000 L3 0.21→**0.20** ·
  worst-case-50-both: lots 1.95→**1.91**, floating −3255→**−3200**, DD 651%→**640%** ·
  basket L5 total 0.61→**0.60**, price-move 9.0439→**9.1947** · cumulative L5 0.61→**0.60**
- **ไม่มี test ถูกลบหรือ downgrade** — `test_rounds_to_step` เปลี่ยนชื่อเป็น
  `test_floors_to_step` พร้อม comment อ้าง MC-001 (semantics เปลี่ยนตามการยืนยัน)

> หมายเหตุการกู้คืน: ระหว่างแก้ SSOT เครื่องดิสก์เต็ม (0 bytes) ทำใฟล์ calculations.py
> เสียหายชั่วคราว — กู้คืนจาก git HEAD (ไม่มีข้อมูลสูญหาย: ไฟล์ไม่เคยถูกแก้ก่อนหน้า)
> และเคลียร์พื้นที่ 11.8 GB (pytest cache + pip cache) — ตรวจซ้ำหลังกู้คืน: L5=0.15 ตรงต้นฉบับ

## 6. ผล Regression

| Suite | ผล |
|---|---|
| Core + Forensics + SSOT-consistency (ใหม่ 4 tests) | **391/391 OK** |
| Web (รวม live-server HTTP goldens) | **125/125 OK** |
| Integration / GUI smoke | ครอบคลุมโดย web live-server suite (ชุดแยกไม่มีใน repo นี้) |
| **รวม** | **516 executions · 0 FAIL · 0 SKIP (เพิ่มใหม่ 26: forensics 22 + SSOT 4)** |

## 7. Evidence Model Hash

| Artifact | SHA-256 (ตัวอย่าง 20 หลักแรก) |
|---|---|
| V1.68-EVIDENCE-MODEL-v1.0-draft.json (เก็บไว้ ไม่แตะ) | `2C38DD61B6F714120F585` |
| **V1.68-EVIDENCE-MODEL-v1.0.json (FROZEN)** | **`124F08984284E880F268`** — ตรวจ match กับ .sha256.txt |
| core/calculations.py (หลังแก้ floor) | ฝังใน freeze JSON |
| ไฟล์ข้อมูล 4 บัญชี | ฝังใน freeze JSON (dataset_hashes) |

หมายเหตุความซื่อตรง: รอบ promote แรกพบบั๊ก gate-evaluation (FAIL จาก substring
"not implemented" ชนกับคำว่า implemented) — แก้เป็น explicit flag แล้ว promote ใหม่
ใน Phase เดียวกัน; v1.0 ที่ใช้จริงคือ hash 124F08… นี้

## 8. Evidence Gate Result — **PASS**

```
VERIFIED (8) : Lot Formula (floor) · Base Lot · Grid Spacing · Grid Direction
               Both-Sides · Contract Size · Partial EXISTS · Normal Resume
PARTIAL  (3) : Grid Trigger · Basket Trigger · Partial Level Rule
UNKNOWN  (4) : Partial Trigger · Partial Volume Rule · Emergency · Restart Recovery
REJECTED (1) : AccumulatorTargetUSD=1.68 per basket
unknown ที่ถูก implement เป็น V1.68 behavior: ไม่มี
critical verified rule ที่ conflict กับ evidence: ไม่มี
```

`data/phase5_3_gate.json` + audit trail เต็มใน `data/phase5_3_confirmation_audit.json`
(reviewer = PROJECT_OWNER ทุกรายการ)

## 9. Phase 6 Prerequisites (พร้อมทั้งหมด)

1. ✅ Evidence Model **v1.0 FROZEN** — Phase 6 ต้องอ้างอิง model version นี้ทุก rule
2. ✅ SSOT floor ใช้งานจริง + ทดสอบความสอดคล้องกับข้อมูลจริง (4,451 checks)
3. ✅ TRACEABILITY_MATRIX.csv (16 rules → candidate → evidence → source → confirmation)
4. ⚠️ Phase 6 ต้อง **ปล่อย UNKNOWN ไว้เป็น UNKNOWN** (emit MODEL_UNCERTAINTY)
   โดยเฉพาะ: Emergency (ใช้ doc 90.0 เป็น OUR-EA policy ได้แต่ห้ามอ้างเป็น V1.68),
   Restart Recovery, Partial Trigger/Volume
5. ⚠️ Basket/Grid trigger ที่เป็น PARTIAL: implementation ต้อง configurable + ระบุ
   hypothesis ที่เลือก + flag ว่าไม่ใช่ V1.68-verified

**สถานะ: Phase 5 ปิดสมบูรณ์ · Evidence Gate PASS · หยุดตามคำสั่ง — รอคำสั่ง Phase 6**
