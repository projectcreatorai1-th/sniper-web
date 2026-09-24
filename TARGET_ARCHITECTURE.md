# TARGET ARCHITECTURE (เสนอ — ยังไม่ implement)
*ออกแบบจากข้อเท็จจริงใน FULL_SYSTEM_AUDIT_REPORT.md เท่านั้น*

## PHASE O — การจัดวาง 14 องค์ประกอบ

| # | องค์ประกอบ | การจัดการ | เหตุผลจาก audit |
|---|---|---|---|
| 1 | Analyzer (forensics/cycle/basket views) | **KEEP SEPARATE** (อยู่หลัง read-only boundary เดิม) | Phase F: 0-violation ต้องคงไว้ |
| 2 | Evidence (frozen model + registries) | **KEEP SEPARATE + ISOLATE เพิ่ม** (read-only mount ใน shell) | ผู้เขียนมีจุดเดียว (freeze ประวัติศาสตร์) — อย่าเพิ่ม writer |
| 3 | OUR EA strategy core | **KEEP SEPARATE** (ไม่ merge กับ A) | OPTION 3 ถูกหักล้างด้วยหลักฐาน |
| 4 | Runtime (hosting ของ B) | **ADD — runtime service ใหม่** (`core/our_ea/runtime_service.py` ตามสไตล์ปัจจุบัน): thread/process ถือ StrategyCore + ModeController + EventLog, เสียบกับ web shell | ช่องว่างที่ทำให้ UI ดูของไม่ได้/drift |
| 5 | MT5 Adapter | **ADD (แยก layer ใหม่)**: wrapper รอไลบรารี MetaTrader5 + credential จาก environment; เสียบ ExecutionAdapter และ feed | ปัจจุบัน MISSING ตัวจริง (ENV_BLOCKED) |
| 6 | Data Capture | **MERGE เข้า runtime service** (data_pipeline มีอยู่แล้ว — ผูกกับ session/replay) | ไม่มีตัวอื่นทำหน้าที่นี้ |
| 7 | Event Ledger | **KEEP (B) + EXPOSE ผ่าน API** (stream/snapshot) | UI ต้องดูสด |
| 8 | Reconciliation | **KEEP (B) + ISOLATE เป็น job** (เรียกเมื่อ broker ต่อ) | มี framework รอ interface |
| 9 | Risk | **KEEP SEPARATE (B)** — แสดงใน UI ผ่าน runtime service | OUR_EA_POLICY ห้ามปนกับ A |
| 10 | UI | **MERGE ที่ชั้น shell**: หน้า Analyzer เดิมทั้ง 13 คงเดิม + หน้า OUR EA เปลี่ยนจาก static export เป็น **อ่าน runtime API สด** (+ ปุ่ม mode/kill ที่ผ่าน validation) | แก้ drift + ให้เป็นโปรแกรมเดียวจริง |
| 11 | API | **MERGE ที่ชั้น web/backend**: เพิ่มกลุ่ม `/api/our_ea/*` (status/events/mode/kill) โดย backend คุยกับ runtime service ผ่าน interface เดียว ไม่ import strategy ตรง ๆ | ใช้ lifecycle เดียวกัน |
| 12 | Persistence | **KEEP ตามระบบ** (A: registries / B: checksum state) — ไม่รวม store | ความสำคัญ/ความถี่ต่างกัน |
| 13 | Monitoring | **ADD dashboard บน runtime API** (heartbeat/uptime/kill/mode + SLO ที่วัดแล้ว) | ข้อมูลวัดมีแล้ว ขาดที่แสดง |
| 14 | Audit | **KEEP + EXPOSE** (audit chain ของ B ออก API) | ตอบ "ทำไม EA ทำสิ่งนี้" จาก trace เดียว |

**Server shell (แก้ H)**: `run_server.py` รุ่นใหม่ = รับ argument จริง (argparse) + **instance lock** (PID + port-bind preflight + stale-PID ตรวจก่อน) + ถือ runtime service ตัวเดียว + shutdown สั่ง kill/flush ของ B ก่อนปิด

## PHASE P — MIGRATION PLAN (ขั้นต่อขั้น, ยังไม่ execute)

| ขั้น | source→destination | dependency | risk | tests ที่ต้องผ่าน | rollback | acceptance |
|---|---|---|---|---|---|---|
| P0 ปัดฝุ่น runtime | ปิดเซิร์ฟเวอร์เก่า 2 ตัว + ลบ PID ตาย + เริ่มตัวเดียวจาก HEAD ปัจจุบัน | ไม่มีโค้ดใหม่ | ต่ำ (reversible สุด) | curl ทุก endpoint 200 + 610 suite | เปิดใหม่ | เว็บเปิดได้, evidence 28 records, OUR EA page โหลด |
| P1 lifecycle hardening | run_server.py: argparse + lock + stale-PID | P0 | ต่ำ | tests lifecycle ใหม่ + web 125 เดิม | git revert ขั้นเดียว | เปิดซ้อนไม่ได้, --port ทำงาน/ถูกปฏิเสธชัดเจน |
| P2 UI refresh pipeline | release_status ผูกกับ manifest ทุก release | P0 | ต่ำมาก | test freshness ใหม่ | revert | UI ตรง manifest เสมอ (drift = 0) |
| P3 runtime service | เพิ่ม core/our_ea/runtime_service.py + /api/our_ea/* | P1 | กลาง | OUR EA suite + boundary scan ต้องยัง 0 | revert (A ไม่ถูกแตะ) | UI ดู state/event/mode สดได้ |
| P4 MT5 demo adapter | layer ใหม่ + env credential | P3 + environment จริง | กลาง-สูง (ใช้ demo เท่านั้น) | demo E2E จริงบน demo account | ปิด adapter (กลับ controlled) | broker snapshot จริง + forward demo เริ่มนับจริง |

ทุกขั้น: ห้ามแตะ A/frozen · ต้อง verify hash ก่อน-หลัง · commit แยกตาม milestone

## ลำดับที่แนะนำ (ตามความเสี่ยงจากน้อยไปมาก)
P0 → P1 → P2 → P3 → P4 (P0-P2 ทำได้ทันทีเมื่ออนุมัติ; P3 รออนุมัติ design เพิ่ม; P4 รอ environment)
