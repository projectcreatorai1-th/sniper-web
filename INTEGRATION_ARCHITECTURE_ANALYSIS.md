# INTEGRATION ARCHITECTURE ANALYSIS
*ผลจาก source จริง · แสดง trade-off ตามหลักฐาน ไม่จัดอันดับ "ดีที่สุด"*

## PHASE N — 3 ทางเลือก

### OPTION 1 — แยก A/B ต่อไปตามสถานะปัจจุบัน
- **Architecture**: repo เดียว, สองระบบไม่เชื่อมกันขณะรัน (เชื่อมด้วย frozen file + replay dataset export)
- **Advantages**: evidence safety สูงสุด (ตามที่พิสูจน์ใน Phase F = 0 violation); ไม่ต้องแตะโค้ดเลย; ผ่าน production audit มาแล้ว
- **Disadvantages**: "โปรแกรมเดียว" ที่ผู้ใช้ต้องการ **ไม่เกิด** — OUR EA ไม่มีหน้าตา runtime, ไม่มี API, ดูของได้แค่ static export ที่เก่า (drift พบแล้ว); ต่อ MT5 ต้องเขียน entrypoint ใหม่ทั้งหมด
- **Risk**: ต่ำต่อ evidence แต่สูงต่อ product (ผู้ใช้ได้ 2 โปรแกรมไม่ใช่ 1); server lifecycle อ่อนแอที่พบยังคงอยู่
- **Complexity**: ต่ำ · **Maintainability**: ปานกลาง (ชิ้นซ้ำเชิงแนวคิด 3 จุดต้องคุม equivalence test ต่อไป)
- **Test impact**: ไม่กระทบ (610 tests คงเดิม) · **Evidence safety**: สูงสุด · **Runtime safety**: ปานกลาง · **MT5 readiness**: ต่ำ (ยังไม่มี bridge)

### OPTION 2 — รวม "บาง service" โดยรักษา boundary (แนว shared contract + shared runtime shell)
- **Architecture**: โปรแกรมเดียวที่มี (1) Analyzer core อ่านอย่างเดียว (2) frozen contract เป็นสะพานเดิม (3) OUR EA runtime ถูก host ใน process เดียวกับ web server ผ่าน **runtime service ใหม่** (mode controller + event stream + snapshot API) (4) UI เพิ่มหน้า runtime ที่ดูสดจาก API ไม่ใช่ static export
- **Advantages**: ได้ "โปรแกรมเดียว" จริงตามเป้าหมาย; แก้ root cause ทั้ง 3 ที่พบ (server lifecycle, UI drift, ไม่มี runtime API) ในการออกแบบเดียว; boundary ไม่เปลี่ยนเลยเพราะตัวเชื่อมคือ contract เดิม
- **Disadvantages**: ต้องเพิ่มโค้ดใหม่ ~1 service + 1 หน้า UI + lifecycle ที่แข็งขึ้น; ต้องระวังไม่ให้ web backend กลายเป็นทางเข้าแก้ evidence (ยืนยันด้วย boundary test ต่อขยาย)
- **Risk**: ปานกลาง-ต่ำ (งานใหม่ทั้งหมดอยู่นอก A; แก้เฉพาะคอขวดที่ audit ชี้)
- **Complexity**: ปานกลาง · **Maintainability**: ดีขึ้น (หน้าเดียว เซิร์ฟเวอร์เดียว ข้อมูลชุดเดียว)
- **Test impact**: เพิ่ม tests ใหม่ (runtime API + lifecycle lock) — baseline 610 ไม่กระทบ
- **Evidence safety**: สูง (ไม่แตะ A/frozen; มี import-scan test คุมอยู่แล้ว)
- **Runtime safety**: สูงขึ้น (single-instance + stale-PID + fresh-process checks)
- **MT5 readiness**: สูงขึ้นที่สุดในสามทาง (runtime service คือที่เสียบ MT5Adapter)

### OPTION 3 — รวมเป็น unified application เดียวทุกชั้น (รวมทั้ง logic วิเคราะห์+รันไทม์)
- **Architecture**: core เดียว ใช้ forensics/evidence เป็น runtime ของ EA ตรง ๆ
- **Advantages**: โค้ดน้อยสุด "ดูสะอาด"; ไม่มีชิ้นซ้ำเลย
- **Disadvantages/ขัดหลักฐานโดยตรง**: ผิด Boundary Lock RULE 4 (ห้าม OUR EA import Analyzer runtime — ปัจจุบัน 0 imports โดยตั้งใจ); ทำให้ mutable forensic logic กลายเป็น dependency ของระบบเทรด → ของที่เคย "วิเคราะห์ย้อนหลัง" กลายเป็น "ตัดสินใจเงิน" แบบไม่มี contract hash คุม; replay/validator ที่พิสูจน์มาทั้งหมดใช้สมมติฐาน separation
- **Risk**: **สูงสุด** — หาก forensic code ถูกแก้เพื่อรองรับ runtime จะเกิด evidence drift แบบเงียบ (tamper-detection จะจับได้ตอน hash ตรวจ แต่ต้นทางวินัยหาย)
- **Complexity**: สูง (ต้อง merge + ทดสอบใหม่มหาศาล) · **Maintainability**: ต่ำลง (สองปรัชญา error-handling ชนกัน)
- **Test impact**: ต้องเขียนใหม่/รวม suite ขนาดใหญ่ · **Evidence safety**: ต่ำ · **Runtime safety**: ต่ำ (fail-safe philosophy ของ B โดนผสมกับ analysis exception ของ A) · **MT5 readiness**: ปานกลาง

## PHASE R — คำตอบ 15 ข้อ (ย่อ, รายละเอียดอยู่ใน audit หลัก)

1. **ซ้ำกัน?** เชิงแนวคิด 3 กลุ่ม (lot×3, grid/basket/cycle×2, config×2) — ไม่มี EXACT_DUPLICATE; ทุกคู่ตั้งใจแยกและถูก test คุม
2. **ขัดกัน?** ไม่พบความขัดแย้งเชิงตรรกะ; ที่พบคือ **ความไม่สดของ runtime** (เซิร์ฟเวอร์เก่า + UI export เก่า) ไม่ใช่โค้ดขัดกัน
3. **ควรใช้ร่วม?** hash discipline, replay dataset (เป็น contract แล้ว), UTC time (B เป็น canonical), หน้าเว็บ/เซิร์ฟเวอร์เดียว (service ใหม่)
4. **แยกเด็ดขาด?** Frozen model + forensic truth + strategy implementation + risk policy + UNKNOWN/VERIFIED semantics + Demo/Live คู่ (ดู DO_NOT_MERGE_BOUNDARIES.md)
5. **UI ตรง backend?** หน้า Analyzer: ตรง (125 parity tests) · หน้า OUR EA: **เก่า 1 รุ่น** (RC-v1.0 vs v1.0-final) — ต้อง refresh export
6. **Runtime ตรง source?** ตอนนี้ **ไม่เต็มที่** — เซิร์ฟเวอร์ 8765 มี 2 ตัว (ตัวหนึ่งโค้ดใน memory อายุ ~13 ชม. ก่อนแก้ SSOT)
7. **Server architecture ปัญหา?** ไม่มี single-instance lock, ไม่รับ/ปฏิเสธ `--port` argument, ไม่มี stale-PID detection, PID ตายค้าง
8. **SSOT ซ้ำ?** Lot มี 3 สาย (ตั้งใจ, equivalence-tested); นอกนั้น SSOT เดียวต่อเรื่อง
9. **state/config ซ้ำ?** config 2 ชุดตั้งใจแยก; state แยกตามระบบ — ไม่มี conflict
10. **OUR EA ใช้ Evidence Contract ถูก boundary?** **ใช่ — พิสูจน์ด้วย import graph = 0 violations; ทุกการโหลด verify-hash**
11. ถ้าอยากได้ "โปรแกรมเดียว" → ทำตาม OPTION 2 (รายละเอียด TARGET_ARCHITECTURE.md)
12. **ก่อนต่อ MT5 Demo ต้องมี**: MT5Adapter จริง (MetaTrader5 lib แยก layer), broker capability snapshot จาก environment จริง, feed→on_tick bridge, runtime service ที่ mention ข้างบน, demo credential ทาง env (ไม่ commit)
13. **ต้องแก้ก่อน (เชิงปฏิบัติ)**: เซิร์ฟเวอร์เก่า 2 ตัว + PID, refresh UI export, lifecycle hardening — ทั้งหมดรอคำสั่ง
14. **ไม่ควรแก้**: ทุกอย่างในหมวด DO-NOT-MERGE + frozen hash + evidence statuses
15. **เสี่ยงอะไรถ้ารวมผิดวิธี (OPTION 3)**: evidence drift เงียบ, fail-safe กลายเป็น analysis-exception, การันตี 0-duplicate-order/kill-switch ที่พิสูจน์ไว้ใช้ไม่ได้กับ dependency graph ใหม่, replay ทั้ง 16,992 comparisons อ้างอิง separation

## คำตอบหลักของผู้ใช้ (ตามหลักฐาน ไม่ใช่ความรู้สึก)

- **"ควรรวมระบบหรือไม่"**: ควรรวม **ที่ชั้น service/UI/runtime-shell (OPTION 2)** เท่านั้น — หลักฐาน: ปัญหาจริงที่พบทั้งหมด (เว็บเปิดไม่ได้, UI drift, ไม่มี runtime API) เป็นปัญหา "ไม่มีตัวเชื่อม" ไม่ใช่ปัญหา "แยกระบบ"
- **"ถ้ารวม รวมอะไร"**: server lifecycle ตัวเดียวที่แข็งแรง · runtime service (host OUR EA + mode controller) · API สำหรับ runtime state/event stream · UI หน้า runtime ดูสด · export pipeline อัตโนมัติ — **โดยไม่ merge โค้ด A เข้า B เลยแม้แต่บรรทัดเดียว**
- **"ถ้าไม่รวม เพราะอะไร"**: ส่วน logic/evidence ห้ามรวม (OPTION 3) เพราะขัดผลพิสูจน์ 3 ระดับ: boundary scan 0-violation ที่ใช้เป็นเงื่อนไข gate มาตลอด, hash-tamper detection ออกแบบบนสมมติฐาน separation, และปรัชญา fail-safe ของ B
- **"ทำอย่างไรให้ UI/Backend/OUR EA/Evidence/Runtime ใช้ข้อมูลชุดเดียว"**: (1) เซิร์ฟเวอร์ตัวเดียว + instance lock (2) runtime service เดียวเป็นคนถือ state ของ B (3) UI ทุกหน้าอ่านจาก API ของ service นั้น (4) evidence ยังมาจาก frozen contract เดิมผ่าน hash (5) export pipeline ต้องผูกกับ release manifest ทุกครั้ง (แก้ drift เชิงโครงสร้าง)
