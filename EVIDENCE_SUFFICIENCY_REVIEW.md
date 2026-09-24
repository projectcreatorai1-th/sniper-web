# EVIDENCE SUFFICIENCY REVIEW — SNIPER CashFlow V1.68

> วันที่ประเมิน: 2026-09-24 · หลัง Phase 4 เสร็จสมบูรณ์
> คำถาม: **หลักฐานเพียงพอแล้วหรือยังสำหรับ OUR EA Strategy Engine?**

---

## สรุปแต่ละกฎ

| กฎ | สถานะ | Assumption ID | Evidence | Observation | Simulation | หมายเหตุ |
|---|---|---|---|---|---|---|
| **Lot Formula** | **MODEL ONLY** | LOT_FORMULA_ASSUMPTION_001 | — (ไม่มี E-id ใด supports) | — (ไม่มี MT5 ข้อมูลจริง) | ✓ (simulator ใช้สูตรนี้) | สูตร BaseLot×Mult^(n-1) เป็นสมมติฐานของโมเดลเท่านั้น ไม่มี MT5 observation ยืนยัน |
| **Grid Trigger** | **MODEL ONLY** | GRID_TRIGGER_ASSUMPTION_001 | — | — | ✓ | จุดอ้างอิง "จากไม้ล่าสุด" ยังไม่มี MT5 data ยืนยัน |
| **Grid Direction** | **MODEL ONLY** | GRID_DIRECTION_ASSUMPTION_001 | — | — | ✓ | "เพิ่มเฉพาะทิศตรงข้าม" — ไม่มี observation |
| **Buy/Sell Relationship** | **MODEL ONLY** | BOTH_SIDES_OPEN_AT_START_ASSUMPTION_001 | — | — | ✓ | ไม่มี MT5 data ยืนยันว่าเปิดสองฝั่งพร้อมกันจริง |
| **Basket Scope** | **MODEL ONLY** | BASKET_SCOPE_ASSUMPTION_001 | BASKET_CLOSE_DOC_001 (VERIFIED: กลไกการปิดมีในคู่มือ) | — | ✓ | คู่มือระบุว่า "ปิดทั้งหมดเมื่อกำไรรวมถึงเป้า" แต่ scope (รวมสองฝั่ง/แยกฝั่ง) ยังเป็น MODEL |
| **Basket P/L** | **MODEL ONLY** | PL_CONVERSION_ASSUMPTION_001 | — | — | ✓ | P/L = Δราคา×lot×cs ไม่รวม spread/commission/swap |
| **Partial Close Scope** | **MODEL ONLY** | PARTIAL_CLOSE_ASSUMPTION_001 | PARTIAL_ONCE_DOC_001 (VERIFIED: ครั้งเดียว/รอบ) | — | ✓ | pro-rata % เป็น MODEL — ไม่มี MT5 observation ยืนยันวิธีที่ EA ใช้จริง |
| **Emergency Reference** | **MODEL ONLY** | EMERGENCY_FRAME_ASSUMPTION_001 | EMERGENCY_DOC_001 (VERIFIED: เงื่อนไขจากคู่มือ) | — | ✓ | "กรอบเทรด = ราคาเริ่ม→ไม้ล่าสุด" เป็น MODEL |
| **Emergency Distance** | **PARTIALLY VERIFIED** | EMERGENCY_DOC_001 + param_facts | E007 (90.0 OBSERVED) + E008 (50.0 DOCUMENTED) | — | ✓ | มี 2 ค่าจาก 2 แหล่ง (video vs preset) — ยังไม่กระจ่างว่าค่าใดคือ internal default จริง |
| **Cycle Start** | **MODEL ONLY** | CYCLE_START_RULE_ASSUMPTION_001 | — | — | ✓ | กติกา "เริ่มเมื่อไม้แรกเปิด" เป็น MODEL |
| **Cycle End** | **MODEL ONLY** | CYCLE_END_RULE_ASSUMPTION_001 | — | — | ✓ | กติกา "จบเมื่อ terminal event" เป็น MODEL |
| **Resume Behavior** | **UNKNOWN** | — | — | — | — | ไม่มีข้อมูลเลยว่า EA ทำอะไรหลัง basket close/emergency/resume |
| **Margin Model** | **MODEL ONLY** | MARGIN_ASSUMPTION_001 | — | — | ✓ | margin = lot×cs×price/leverage×rate เป็นสูตร MODEL |

---

## สรุป

| สถานะ | จำนวน | รายการ |
|---|---|---|
| **VERIFIED** (จากเอกสาร) | 3 | GridStepUSD ระยะราคา · Basket close กลไก · Partial ครั้งเดียว/รอบ |
| **PARTIALLY VERIFIED** | 1 | Emergency Distance (มี observed 90 + documented 50 — ยังไม่ชี้ขาด) |
| **MODEL ONLY** | 10 | Lot formula · Grid trigger/direction · Buy/Sell · Basket scope · Basket P/L · Partial scope · Emergency reference · Cycle start/end · Margin model |
| **UNKNOWN** | 1 | Resume behavior (ไม่มีข้อมูลใด) |

---

## คำตอบ: หลักฐานเพียงพอหรือยัง?

**ยังไม่เพียงพอ** สำหรับ OUR EA Strategy Engine เพราะ:

1. **ไม่มี MT5 Observation จริงเลย** — ระบบมี infrastructure ครบ (import/comparator/candidate/versioning) แต่ยังไม่มีข้อมูล MT5 จริงถูก import เข้ามาแม้แต่ชุดเดียว (0 observation sessions ที่มี events จริง)
2. **สูตรหลักทั้งหมดยังเป็น MODEL** — โดยเฉพาะ Lot Formula ซึ่งเป็นหัวใจของ martingale/grid ยังไม่มี MT5 data ยืนยันแม้แต่ระดับเดียว
3. **Resume/Restart behavior ไม่มีข้อมูลเลย** — ไม่รู้ว่า EA ทำอะไรหลังปิดรอบ

## สิ่งที่ต้องทำก่อน OUR EA

### ขั้นต่ำ (ต้องมี):
1. **Import MT5 backtest/deals อย่างน้อย 1 ชุด** ผ่านหน้า Observation → จะยืนยัน/หักล้าง Lot formula + Grid spacing + Direction ทันที
2. **บันทึก manual observation อย่างน้อย 1 รอบ** (TEST A–F) เพื่อยืนยัน Basket close + Partial close + Cycle end

### แนะนำเพิ่มเติม:
3. ถ้ามี Myfxbook บัญชีจริง → import เป็น INDIRECT evidence (context/cross-check)
4. เก็บ observation หลายรอบ (10+ cycles) เพื่อ statistical confidence

---

## คำแนะนำ

> **ทำ Timeline Simulator เพิ่มเติม** (Phase 4 มีแล้ว) แล้ว **ใช้มันเป็นฐาน** เทียบกับ MT5 observation จริงที่จะ import ภายหลัง — ระบบทั้งหมดพร้อมทำงานแล้ว ขาดเพียงข้อมูลจริงจาก MT5

> **ห้ามสร้าง OUR EA** จนกว่า Lot Formula จะถูกยืนยัน (หรือหักล้างพร้อมแทนที่ด้วยสูตรที่ถูกต้อง) จาก MT5 observation จริงอย่างน้อย 1 ชุด

---

*รายงานนี้สร้างจาก Assumption Registry + Evidence Registry + Observation Sessions + Model Candidates ที่มีอยู่จริงในระบบ ณ วันที่ 2026-09-24*
