# PHASE 5.1 REPORT — MT5 Report Forensic Validation (Deal-level)

**สร้างจากการรันโค้ดจากข้อมูลจริงทั้งหมด — ไม่มีการ fake / ไม่มีการสร้างข้อมูลปลอม**

- วันที่วิเคราะห์: 2026-09-24
- แหล่งข้อมูล: MT5 Trade History export (xlsx) จาก 4 บัญชี XM Global **real** (Hedge, USD)
- ผู้วิเคราะห์: `tools/phase5_1_forensic.py` (v3), `tools/phase5_1_register.py`
- ผลลัพธ์ดิบ: `data/phase5_1_forensic.json`, evidence `data/evidence.json` (E011–E024), candidates `data/model_candidates.json` (MC-001–MC-007)

---

## 1. การค้นพบสำคัญเกี่ยวกับแหล่งข้อมูล

ไฟล์ xlsx ที่ MT5 export ออกมา มี **5 ตารางในไฟล์เดียว** (ไม่ใช่แค่ Position History):

| ตาราง | เนื้อหา |
|---|---|
| Positions | ประวัติตำแหน่ง (open/close/P/L) |
| Orders | ทุก order — ประเภท market, สถานะ filled, volume ที่ขอ/ที่ fill, **comment "CashFlow Buy/Sell"** |
| **Deals** | **ทุก deal ระดับ in/out** — volume, price, profit, **balance ไหล**, comment ที่ entry |
| Open Positions | ตะกร้าที่ค้างอยู่ตอน export |
| Results | สรุปบัญชี (net profit, PF ฯลฯ) |

> ก่อนหน้านี้สคริปต์ parse ผิด (อ่านทับเข้าตาราง Orders) ทำให้ตัวเลขรอบก่อนเพี้ยน —
> รอบนี้แยกตารางเรียบร้อย ตัวเลขทั้งหมดด้านล่างมาจากข้อมูลสะอาด

## 2. แหล่งข้อมูล + Integrity

| บัญชี | Server | Positions | Orders/Deals | เปิดค้าง | SHA-256 (16) |
|---|---|---|---|---|---|
| 335504856 | XMGlobal-MT5 9 | 806 | 1,648 | 4 | B2BD8004E670… |
| 391629843 | XMGlobal-MT5 14 | 2,450 | 5,050 | 21 | C8888D7BAC1E… |
| 411173797 | XMGlobal-MT5 16 | 1,099 | 2,239 | 4 | 417F73981035… |
| 440192945 | XMGlobal-MT5 19 | 808 | 1,656 | 4 | DA61F581A51C… |
| **รวม** | | **5,163** | **10,593** | 33 | |

Integrity: order ทั้งหมดเป็น market / filled 100% / partial fill = 0 /
volume in≈out (ต่างกันเท่า volume ที่ยังค้าง) — ข้อมูลสมบูรณ์ใช้วิเคราะห์ได้

## 3. ผลการตรวจ 11 กฎ (862 complete cycles)

| # | กฎ | ผล | ตัวเลข | Evidence |
|---|---|---|---|---|
| 1 | **Lot formula** | **VERIFIED (floor!)** | `Lot(n)=floor(0.1×1.1^(n-1)/0.01)×0.01` = **99.77%** (3,419/3,427) เทียบกับ round-half-up 82.90% | E012 |
| 2 | Grid spacing ≈ 5 USD | VERIFIED | n=3,426 | median 5.09 | P5 4.72 | P95 5.98 | 85.2% ∈ [4.5,5.5] | E013 |
| 3 | BUY ลง / SELL ขึ้น | VERIFIED | BUY ลง 1,732/1,732 = **100.00%** · SELL ขึ้น 1,692/1,695 = 99.82% | E014 |
| 4 | เปิดคู่ BUY+SELL 0.1 | VERIFIED | 857/862 = 99.4% · lot แรก = 0.1 ถึง 99.8% · คู่แรก 72% ลงตารางวินาทีเดียวกัน | E015 |
| 5 | **Basket close trigger** | **VERIFIED (≈ คงที่ $1.0–1.1)** | winners: P5 +1.03 · P25 +1.10 · median +1.14 · แพ้จริงแค่ 7 ตะกร้า (แพ้สูงสุด −0.24 = เหตุการณ์ spread) | E016 |
| 6 | **Partial close** | **ยืนยันมีจริง** | 255 solo out-deal bursts กลาง cycle · ปิดระดับเก่าสุดก่อน (0.10–0.19) · P/L มัธยฐาน +0.24 · จบ cycle ด้วย burst เดียว 860 ≈ 862 cycles | E017 |
| 7 | Resume ทันที | VERIFIED | ≤2s: 132/132, 401/406, 190/190, 134/134 | E018 |
| 8 | Contract size | VERIFIED | median **1.0000** (n=5,083, stdev 0.0091) | E019 |
| 9 | EA provenance | VERIFIED | in-deals มี comment CashFlow **5,184/5,184 = 100%** · out-deal 0/5,609 · ไม่มี pending order | E020 |
| 10 | Emergency | **ไม่พบใน production** | 0/862 · grid ลึกสุด 32 ระดับ 20.07 lots 28.1 ชม. ยังปิดที่กำไร +21.80 | E021 |
| 11 | Restart recovery | หลักฐาน 1 เหตุการณ์ | หยุด 7.45 ชม. → กลับมาเปิด cycle ใหม่ที่ lot 0.1 ปกติ | E022 |

### 3.1 การค้นพบใหม่ 3 ข้อที่กระทบโมเดลปัจจุบัน

**(A) โหมดปัดเศษของ Lot คือ FLOOR ไม่ใช่ round-half-up — 99.77%**

| Level | SSOT ปัจจุบัน (round) | ของจริง (floor) |
|---|---|---|
| 5 | 0.15 | **0.14** |
| 7 | 0.18 | **0.17** |
| 10 | 0.24 | **0.23** |
| 12 | 0.29 | **0.28** |

SSOT `core/calculations.py lot_for_level` ขัดแย้งกับพฤติกรรมจริงที่ level เหล่านี้
→ สร้าง MC-001 (CANDIDATE) ไว้รอการ confirm — **ยังไม่แก้ SSOT จนกว่าจะอนุมัติ**

**(B) ตัวปิดตะกร้าเป็นเงิน USD คงที่ ≈ $1.0 ไม่ใช่ $1.68 และไม่ scale ตาม lot**

- ไม่มี cluster รอบ 1.68 เลย (ใกล้ 1.4–2.0 แค่ ~4%)
- อัตราส่วน gross/lots ลดลงตามความลึก (lvl3 = 2.24 → lvl8 = 1.05) → ไม่ใช่ per-lot
- ตะกร้าลึกปิดเกินเป้ามาก (lvl9 median 2.10, lvl10 3.20) เพราะ P/L วิ่งเร็ว
- → **ขัดแย้งกับ candidate AccumTargetUSD=1.68** ต้อง resolve ก่อน confirm MC-006

**(C) Partial close มีจริงและปิด "ระดับเก่าสุด" ก่อน** — สอดคล้องกับเอกสาร
(partial_realized ใน basket simulation) แต่ **สูตร threshold ยังไม่รู้**
(hypothesis: ~1.68 ต่อ lot ที่ปิด — partial P/L median +0.24 กับ volume ~0.12–0.14 พอดี แต่ยังไม่พิสูจน์)

### 3.2 หลักฐานเสริม

- **E023 การเปลี่ยนพารามิเตอร์กลางทาง**: 391629843 วันที่ 23–24 Sep ลำดับ lot
  0.12→0.14→0.15→0.17 และ 0.18→0.30 ไม่เข้าสูตรไหน (ผิดแค่ 8/3,427 = 0.23%)
  → น่าจะมีการเปลี่ยน BaseLot/Multiplier ระหว่างรัน = ยืนยันว่า lot progression
  เป็น parameter-driven
- **E024 Determinism**: 4 บัญชี เปิด/ปิดตะกร้าเดียวกันวินาทีเดียวกันซ้ำ ๆ
  (8 จุดตรงทั้ง 4 บัญชี, เช่น close burst 2026.09.16 21:19:52 พร้อมกันทุกบัญชี)
  → logic เข้าเป็นสัญญาณ deterministic ไม่มีสุ่ม
- **ความเสี่ยงที่เห็นจริง**: grid 32 ระดับ = 20.07 lots บนทอง ~4,300
  (notional ~$86k) บัญชีที่รอดระยะ 28 ชม. — ใช้ปรับ worst-case ใน Phase ถัดไป

## 4. Evidence Gate Recheck

| กฎวิกฤต (ต้องผ่านก่อน Phase 6) | ก่อน 5.1 | หลัง 5.1 | เหลืออะไร |
|---|---|---|---|
| Lot formula | PARTIAL 20% (ข้อมูลปนเปื้อน) | **DIRECT evidence 99.77% (floor)** | รอ confirm MC-001 + แก้ SSOT rounding |
| Grid spacing 5.0 | VERIFIED (คร่าว) | VERIFIED (สะอาด n=3,426) | รอ confirm MC-002 |
| Grid direction | VERIFIED | VERIFIED (BUY 100.00%) | รอ confirm MC-003 |
| Both sides + base lot | OBSERVED 36%→97% | **VERIFIED 99.4/99.8%** | รอ confirm MC-004 |
| Basket P/L trigger | INCONCLUSIVE | **VERIFIED ≈ $1.0–1.1 คงที่** | resolve ขัดแย้ง 1.68 → confirm MC-006 |
| Partial close | INCONCLUSIVE | **ยืนยันมีจริง + รูปแบบ** | สูตร threshold ยัง UNKNOWN → MC-005 |
| Emergency | INCONCLUSIVE | **ไม่เกิดเลยใน production** | ค่า threshold ยังอิง E007/E008 (90/50) |
| Restart recovery | UNKNOWN | หลักฐาน 1 เหตุการณ์ (LOW) | ต้องการ controlled test |

**สถานะ Gate: ยัง NOT PASSED — แต่เหตุผลเปลี่ยนแล้ว**
- ก่อนหน้า: บล็อกเพราะ "หลักฐานไม่พอ/ไม่ชัด"
- ตอนนี้: หลักฐาน 6/8 กฎวิกฤตถึงระดับ DIRECT แล้ว **ค้างที่ขั้นตอน human review เท่านั้น**
  (ตามข้อห้าม "ห้าม auto-confirm Candidate")

## 5. Blockers ที่เหลือ (เรียงตามลำดับ)

1. **Human review MC-001 … MC-007** — เจ้าของโปรเจกต์ตรวจและ confirm ผ่านหน้า
   Evidence → Model Candidates (หรือสั่งให้ confirm เป็นรายตัวใน session ถัดไป)
2. **Resolve AccumTargetUSD**: เอกสาร candidate 1.68 vs สังเกตจริง ≈ 1.0–1.1 —
   ตัดสินว่า 1.68 มาจาก preset อื่นหรือค่าผิด แล้วอัปเดต E016/MC-006
3. **แก้ SSOT rounding** (หลัง MC-001 ผ่าน): `lot_for_level` เปลี่ยนเป็น floor
   + รัน regression tests (ค่า pinned บางตัวจะเปลี่ยน: L5 0.15→0.14 ฯลฯ)
4. **Emergency**: ยังไม่เคยเห็นใน production — ปล่อยเป็น DOCUMENTED/OBSERVED_FROM_TESTING
   (90.0) หรือหา controlled test ถ้าต้องการ VERIFIED
5. **Partial-close threshold**: วิเคราะห์ต่อจาก deal data ที่มีแล้วได้ (ไม่ต้องข้อมูลใหม่)
   แต่ต้องระบุสูตรก่อนใช้ใน OUR EA

## 6. ข้อจำกัดของการวิเคราะห์นี้

- ข้อมูลเป็น real production (ไม่ใช่ controlled test) — พารามิเตอร์ระหว่างทาง
  อาจเปลี่ยนโดยเจ้าของบัญชี (เห็นได้จาก E023) จึงอ้าง "พฤติกรรมที่สังเกตได้ในหน้าต่างข้อมูล"
  ไม่ใช่ "ค่า default ของ EA ทุกเวอร์ชัน"
- cycle#0 ของแต่ละบัญชีตัดขาดจากหน้าต่างรายงาน → ตัดออกจากสถิติ
- ไม่มีข้อมูล floating P/L ระหว่างทาง (ต้อง inference จากราคา) → ไม่คำนวณ
  worst floating drawdown ในรายงานนี้
- ตามข้อกำหนด: ไม่ decompile .ex5, ไม่ส่ง order, ไม่ auto-confirm

## 7. สิ่งที่ลงทะเบียนแล้วในระบบ

- Evidence: E011–E024 (OBSERVED, MT5_CSV) ใน `data/evidence.json`
- Model Candidates: MC-001–MC-007 (สถานะ CANDIDATE ทั้งหมด) ใน `data/model_candidates.json`
- ชุดทดสอบ 365 tests: **ผ่านทั้งหมด** (หลังลงทะเบียน evidence)
