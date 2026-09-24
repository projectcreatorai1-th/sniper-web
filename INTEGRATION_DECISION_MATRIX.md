# INTEGRATION DECISION MATRIX
*เกณฑ์ตัดสินจากหลักฐานใน FULL_SYSTEM_AUDIT_REPORT.md · AUDIT ONLY*

## เมทริกซ์การตัดสิน (ต่อชิ้น)

| ชิ้น | รวมได้? | เงื่อนไขที่อนุญาต | สิ่งที่ต้องพิสูจน์ก่อนรวม | สถานะปัจจุบัน |
|---|---|---|---|---|
| Web server / lifecycle | ✅ MERGE (ตัวเดียว) | instance-lock + argparse + stale-PID guard | test เปิดซ้อน/ปิด-เปิด 100 รอบ | ยังไม่รวม (มี 2 ตัวซ้อน) |
| UI shell (หน้าเดียวทั้งสองระบบ) | ✅ MERGE | หน้า A ห้าม refactor; หน้า B อ่าน API สด | freshness test + boundary scan ยัง 0 | ครึ่งเดียว (B เป็น static เก่า) |
| API layer | ✅ MERGE ที่ backend | กลุ่ม `/api/our_ea/*` ผ่าน runtime-service interface เท่านั้น (ห้าม import strategy ตรง) | contract test ของ interface | ยังไม่มี |
| Runtime hosting | ✅ ADD (service เดียว) | ถือ mode/event/state ของ B; shutdown สั่ง kill/flush | recovery suite ยัง 8/8 | ยังไม่มี |
| Event ledger exposure | ✅ EXPOSE (ไม่ใช่ merge) | read-only stream | idempotency ไม่ถูกกระทบ | มี ledger ไม่มี exposure |
| Evidence contract | ❌ **DO NOT MERGE** | — | — | ถูกต้องอยู่แล้ว |
| Forensic/Analyzer logic | ❌ **DO NOT MERGE** | มีได้ทางเดียว: export ผ่าน immutable dataset (แบบเดิม) | — | ถูกต้อง (0 imports) |
| Lot/Grid/Basket/Cycle logic | ❌ ไม่ merge โค้ด | คุมด้วย equivalence/parity tests ต่อไป | — | ถูกต้อง (3 สาย lot เท่ากัน 100%) |
| Risk policy | ❌ อยู่กับ B เท่านั้น | แสดงผ่าน API ได้ | — | ถูกต้อง |
| Config | ❌ ไม่รวม 2 ชุด | mapping ระหว่างกันได้ถ้าจำเป็น (documented) | — | ถูกต้อง |
| MT5 connection | ✅ ADD (layer ใหม่) | demo ก่อนเท่านั้น + env credential | broker snapshot จริง + cancel-on-disconnect ใช้ได้จริง | MISSING (ENV_BLOCKED) |
| Monitoring/SLO | ✅ ADD บน runtime API | ค่าจากการวัดจริงเท่านั้น | baseline มีแล้ว (phase10) | มีข้อมูล ไม่มี dashboard |
| Persistence | ❌ ไม่รวม store | — | — | ถูกต้อง |
| Audit chain | ❌ ไม่แตะ (expose อย่างเดียว) | — | — | ถูกต้อง |

## ตัวชี้วัดว่า "รวมสำเร็จ" (ทุกข้อต้องจริงพร้อมกัน)
1. เปิดโปรแกรมเดียว → เห็นทั้ง Analyzer และ OUR EA runtime สด
2. เซิร์ฟเวอร์ซ้อนไม่ได้; PID ตรงเสมอ; `--port` ทำงาน
3. UI OUR EA ตรงกับ release_manifest ณ ขณะนั้นเสมอ (freshness test คุม)
4. Boundary scan ยัง **0** violation; frozen hash ไม่เปลี่ยน
5. 610 baseline tests ผ่าน + suite ใหม่ของ service/lifecycle ผ่าน
6. LIVE ยังถูกปฏิเสธทุกทาง (bypass suite ยังเขียว)
