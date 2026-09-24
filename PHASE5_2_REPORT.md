# PHASE 5.2 REPORT — FORENSIC ENGINES + HUMAN CONFIRMATION PACKET

**รันจากข้อมูลจริงทั้งหมด — ไม่มี auto-confirm / ไม่มี synthetic ปนกับ evidence / UNKNOWN ยังเป็น UNKNOWN**

- วันที่: 2026-09-24
- รันโดย: `tools/phase5_2_run.py` + `core/forensics/` (8 โมดูลใหม่)
- ผลลัพธ์: `data/phase5_2_forensics.json`, `data/phase5_2_confirmation_packet.json`,
  `data/evidence_model/V1.68-EVIDENCE-MODEL-v1.0-draft.json`
- Tests: **387/387 ผ่าน** (365 เดิม + 22 ใหม่ใน `tests/forensics/`)

---

## 1. โครงสร้างใหม่ `core/forensics/`

| โมดูล | หน้าที่ | มาตรา Master Command |
|---|---|---|
| `mt5_report.py` | parse 5 ตารางจาก xlsx + SHA-256 | §1 |
| `cycle_reconstruction.py` | immutable Cycle + confidence + flags | §5 |
| `lot_engine.py` | floor ladder configurable + broker constraints | §3 |
| `grid_trigger.py` | anchor hypothesis replay | §4 |
| `partial_close.py` | deal-level partial reconstruction + 4 separated statuses | §6 |
| `basket_forensics.py` | basket records + trigger hypothesis replay | §7 |
| `emergency_forensics.py` | anomaly scan | §8 |
| `recovery.py` | pause scan + TEST_R_RESTART_RECOVERY spec | §9 |

## 2. ผล forensic (แก้/เพิ่มจาก Phase 5.1)

### §3 Lot Engine — **100.00% บน clean cycles**
- L1–L50 ladder สอดคล้อง 50/50; level 1–32 คือที่ "observed จริง"
  (4,451/4,451 = **100.00%** บน 812 HIGH-confidence cycles)
- 8 mismatches เดิมอยู่ใน cycles ที่ flag `ANOMALOUS_LOTS` กักไว้เองแล้ว
- ทดสอบ: floating-point, floor, volume step, min/max volume, precision — ผ่านหมด
- **SSOT เดิม (round) ยังไม่แก้** — รอ MC-001 ผ่านการ confirm (ตามกฎ)

### §4 Grid Trigger Semantics — **PARTIAL**
- H_PREV_ENTRY กับ H_EXTREME **แยกไม่ได้** (ค่าเหมือนกันทุกตัว: p5 4.73, med 5.09, p95 5.90, band 93.4%)
  เพราะใน averaging-down รอบก่อนหน้า = จุดสุดโต่งเสมอ
- H_AVG_PRICE ถูกปฏิเสธ (median 7.48)
- → semantics = **PARTIAL** (แยกสอง hypothesis นี้ต้องใช้ controlled test) — **E026**

### §5 Cycle Reconstruction
- 866 cycles: **812 HIGH / 48 MEDIUM / 6 LOW** confidence
- flags: DEEP_GRID 40, NEGATIVE_CLOSE 8, ANOMALOUS_LOTS 5, UNPAIRED_START 5, MULTI_BURST_END 3
- LOW-confidence cycles ห้ามใช้เป็น hard evidence (implement ใน engine แล้ว)

### §6 Partial Close — **ค้นพบกลไกที่แท้จริง (แก้ความเข้าใจเดิม)**
- **Partial close เป็นระดับ deal ในตำแหน่งเดียวกัน (intra-position)**:
  out-deal ที่จับคู่กับ position row ไม่ได้ = การปิดบางส่วน
  (ตาราง Positions แสดงเฉพาะ volume คงเหลือ จึงมองไม่เห็นใน Phase 5.1)
- **492 เหตุการณ์** (64/282/74/72 ตามบัญชี) — **PARTIAL_EXISTS = VERIFIED**
- กำไรต่อเหตุการณ์: **median +1.06** (53% อยู่ใน [0.7, 1.3]) — ระดับเดียวกับ basket trigger!
- attribution: 390 FIFO-feasible / 102 ambiguous
- แยกสถานะ: TRIGGER=**UNKNOWN** · VOLUME_RULE=**UNKNOWN** · LEVEL_RULE=**PARTIAL**
- ลงทะเบียน **E025** + candidate **MC-009** (แก้คำอธิบาย MC-005 — ให้ reviewer ตัดสิน)

### §7 Basket Trigger Replay — **1.68 ถูกปฏิเสธเด็ดขาด**
| Hypothesis | Violations | ข้อสรุป |
|---|---|---|
| gross ≥ $1.00 | **3.14%** | ✅ compatible (fit ดีสุด MAE 0.994) |
| gross ≥ $1.10 | 24.88% | ❌ |
| gross ≥ $1.68 (doc) | **90.70%** | ❌ **ปฏิเสธ** |
| net ≥ $1.00 | 6.98% | ❌ ขอบ |
| lots × 0.50 | 0.70% | ✅ compatible (แต่ MAE หลวม 1.587) |
| lots × 0.85 | 1.51% | ✅ compatible (MAE 1.318) |
| lots × 1.68 | 25.23% | ❌ |

→ BasketAmount=OBSERVED · BasketTrigger=**PARTIAL** (3 hypotheses ยังร่วมกันได้) — **E027**
การปฏิเสธ 1.68 นี้ **แก้ conflict ที่ค้างจากเอกสาร** ไปทางเดียว

### §8 Emergency — **UNKNOWN**
- 0 emergency close; 1 SEQUENCE_INTERRUPTION (พัก 7.45 ชม. — ตรงกับ E022)
- ห้าม implement จาก assumption → สถานะ UNKNOWN คงอยู่

### §9 Restart — **UNKNOWN** + สเปกทดสอบ
- พบ 4 พัก (>60s); 1 กรณีกลับมาด้วย base-lot ใหม่
- สร้าง `TEST_R_RESTART_RECOVERY` spec ครบ (preconditions/steps/acceptance) — ยังไม่ claim verified

## 3. Confirmation Packet (Phase 5.2)

`data/phase5_2_confirmation_packet.json` — ครบทุก field ตาม Master Command:
`candidate_id, evidence_refs, sample_size, accounts, confidence, exceptions,
alternative_explanations, previous_status, new_status, confirmation_record`

Candidates ทั้งหมด: **MC-001 … MC-009** — ทุกตัว `new_status = PENDING_HUMAN_REVIEW`
`confirmation_record.reviewer = null` (รอเจ้าของโปรเจกต์)

## 4. Evidence Gate

| เกณฑ์ | สถานะ |
|---|---|
| Evidence quality (6/8 กฎวิกฤต = DIRECT) | ✅ PASS |
| Conflict resolution (1.68 vs ~1.0) | ✅ ทิศทางชัด (1.68 ถูกปฏิเสธ 90.7%) |
| Human confirmation ของ candidates | ❌ **0/9 confirmed** |
| **รวม** | **BLOCKED — ค้าง human review เท่านั้น** |

Freeze สร้างเป็น **v1.0-draft** (ระบุ DRAFT + เหตุผลชัด) — ห้ามยกระดับเป็น v1.0
จนกว่า gate ผ่าน

## 5. BLOCKER (ตามรูปแบบ Master Command §30)

- **BLOCKER**: Phase 6 (Behavioral Model implementation) ห้ามเริ่ม — Evidence Gate = BLOCKED
- **CAUSE**: candidates ทั้ง 9 ยังไม่มี human confirmation (กฎห้าม auto-confirm)
- **EVIDENCE**: `data/phase5_2_confirmation_packet.json` (ครบ field), E011–E028
- **REQUIRED TEST**: ไม่ต้องเทสเพิ่ม — ต้องการ **การตัดสินใจของเจ้าของโปรเจกต์**
- **ACCEPTANCE CRITERIA**: ผู้เจ้าของ review และยืนยัน/ปฏิเสธ MC-001…MC-009
  (ยอมรับอย่างน้อย: MC-001 lot floor, MC-002 grid spacing, MC-003 direction,
  MC-004 both sides, MC-008 base lot, MC-006/MC-009 basket+partial)
  → หลัง confirm: แก้ SSOT rounding + freeze v1.0 + เริ่ม Phase 6 ได้ทันที

## 6. สรุปสิ่งที่ทำ/ไม่ทำ

✅ ทำ: forensic engines 8 โมดูล + 22 tests + E025–E028 + MC-008/MC-009 +
confirmation packet + freeze draft + รายงานนี้
❌ ไม่ทำ (ตามกฎ): auto-confirm · แก้ SSOT rounding · เริ่ม Phase 6 ·
แก้/ลบ evidence เดิม · ใช้ synthetic เป็น evidence
