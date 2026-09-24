# DO NOT MERGE BOUNDARIES
*รายการสิ่งที่ห้ามรวม/ห้ามแตะเด็ดขาด — อ้างอิงจากผล audit จริง*

## ห้ามรวม (DO NOT MERGE)

1. **Frozen Evidence Model** (`data/evidence_model/V1.68-EVIDENCE-MODEL-v1.0.json`)
   - audit ยืนยัน writer เดียวคือ freeze script ประวัติศาสตร์; runtime ไม่มี mutation path — อย่าเพิ่ม writer ไม่ว่ากรณีใด
2. **V1.68 forensic truth** (core/forensics/**)
   - ใช้ได้ทางเดียว: ผ่าน export immutable dataset (replay_dataset_v1 + hash) ตามที่ทำอยู่
3. **Analyzer internals** (core/calculations, core/evidence, core/cycle, core/basket, web/backend เดิม, desktop)
   - read-only ตลอดกาล; หน้า UI เดิมห้าม refactor ในงาน integration
4. **OUR EA strategy implementation** (core/our_ea/strategy + engines)
   - ห้ามดูด logic ของ A เข้ามา; การเชื่อมทำที่ service/API เท่านั้น
5. **Demo/Live separation**
   - mode controller + LIVE lock ต้องอยู่หน้า runtime service เสมอ; ห้ามให้ web layer เรียก adapter ตรง
6. **Evidence vs Policy**
   - ทุก limit/kill/recovery = OUR_EA_POLICY มี label ของตัวเอง; ห้ามเคลื่อนย้ายไปอยู่ใต้ชื่อ V1.68
7. **UNKNOWN vs VERIFIED semantics**
   - 4 UNKNOWN + 3 PARTIAL + 1 REJECTED ห้ามเปลี่ยนสถานะเพราะเหตุผลทาง integration ใด ๆ (เปลี่ยนได้ด้วย evidence ใหม่เท่านั้น)

## ห้ามแตะระหว่างการแก้ไขครั้งถัดไป (ตามที่พบใน audit)

- เซิร์ฟเวอร์เก่า 2 ตัว: ปิดได้เมื่ออนุมัติเท่านั้น (ยังไม่แตะในรอบ audit นี้)
- โปรเซสของ session อื่น (p9r_gates.py, pytest) — ไม่ใช่ของระบบนี้ ห้าม terminate จนกว่าเจ้าของยืนยัน
- สถานะ evidence ทั้งหมดใน data/evidence.json, model_candidates.json (append-only)

## เช็กลิสต์ก่อนทุกงาน integration ในอนาคต
- [ ] frozen hash ก่อน-หลัง เท่าเดิม
- [ ] `grep` import boundary ยัง 0
- [ ] git diff ไม่มีการแตะ core/(A) และ data/evidence_model/
- [ ] 610 baseline tests ผ่านก่อนเริ่มและหลังจบ
- [ ] LIVE bypass suite ยังเขียว
