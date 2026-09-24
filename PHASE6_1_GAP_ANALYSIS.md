# PHASE 6.1 GAP ANALYSIS (§2)

Baseline: commit `2358300` · model V1.68-EVIDENCE-MODEL-v1.0 @ `124F08984284E880F268C3…` (hash verified, tree clean) · Phase 6 status: RC / PAPER READY / DEMO READY / LIVE LOCKED

## คำตอบ 9 ข้อตามลำดับ

**1. Demo deployment wiring เหลืออะไร**
- `DemoAdapter` เป็น placeholder (subclass SimulationAdapter) — ยังไม่มี demo runner entrypoint,
  ไม่มี demo-broker response simulation แบบ controlled, ไม่เคยรัน Demo E2E จริง
- ที่ต้องทำ: demo runner (`tools/phase6_1_demo.py`) + Demo E2E 13 ขั้นตอน (§17) + safety limits
  เฉพาะ demo (§10) — ทำได้ครบในเครื่องนี้โดยไม่ใช้เงินจริง

**2. TEST_R_RESTART_RECOVERY เหลืออะไร**
- มีแค่ (ก) spec ใน frozen model (ข) unit test เรื่อง save/restore state object
- ยังไม่เคย: จบ process จริง → restart process ใหม่ → restore → ทำงานต่อ
- ที่ต้องทำ: real subprocess restart harness + 8 scenarios (normal / active cycle /
  after partial / duplicate event / missing state / corrupted state / incompatible
  model version / stale state)

**3. Replay 77.55% เกิดจากอะไร**
- match_pct = MATCH / ทุก comparison — ตัวส่วนถูกขยายด้วยการเปรียบเทียบที่ "เปรียบไม่ได้ตามธรรมชาติ":
  NOT_COMPARABLE 2,976 (trigger semantics PARTIAL 2,827 + fill scatter 149) และ
  UNKNOWN 812 (partial trigger/volume — ห้าม fabricate)
- MISMATCH จริงมีแค่ **27** จาก 16,992 (0.16%)
- ตัวเลข 77.55% ไม่ใช่ "ผิด 22%" — เป็นผลรวมของการ classification ที่ซื่อตรง

**4. mismatch ใดเป็น expected limitation**
- R-BASKET-TRIGGER 22 รายการ = 2.71% ≈ hypothesis error rate ที่ evidence บอก (E027: 3.14%
  violations ของ H_GROSS_1_00) — PARTIAL rule ยังไม่มี verified trigger
- R-GRID-DIRECTION 3 รายการ = 0.18% = ตรง exception rate ที่ E014 ระบุ (3/1,695)
- R-GRID-SPACING 2 รายการ = fill เดียวกันกับ direction exceptions (ผิดทิศ)

**5. mismatch ใดเป็น implementation issue**
- ตรวจซ้ำใน PHASE6_1_REPLAY_AUDIT.md: จะ trace ทั้ง 27 รายการ — คาดว่า 0 implementation defect
  (lot/base/both-sides = 0 mismatch บน 812 clean cycles)
- implementation defect จริง 2 ตัวเคยเจอตอน failure-injection (rejected-entry state,
  close accounting) — แก้แล้วใน commit e5159fc

**6. mismatch ใดเกิดจากข้อมูลไม่ละเอียดพอ**
- fill scatter 149 รายการ (spacing หลุด band แต่ทิศถูก): ไม่มี tick data แยกว่า trigger
  ข้ามเมื่อไร vs slippage/gap — จัด NOT_COMPARABLE
- trigger semantics 2,827: H_PREV_ENTRY ≡ H_EXTREME ทางคณิตศาสตร์ใน ladder ชนิดนี้

**7. tick-level data ต้องการอะไร** → `data/our_ea/tick_requirements.json`
- GOLDmicro bid/ask (ms timestamps) ครอบหน้าต่างเทรดของทั้ง 4 บัญชี + deal linkage
  (ต้องได้จาก broker จริง — ใน repo ไม่มี → BLOCKED_BY_DATA)

**8. มี test ใดที่รายงาน PASS แต่ยังไม่ได้ execute จริงหรือไม่ — มี**
- GATE-6.11 (DEMO) = PASS_WITH_UNKNOWN จาก "adapter ready" — **ไม่เคยรัน Demo E2E**
- Restart recovery = unit-level restore เท่านั้น (ไม่ใช่ process restart จริง)
- Performance claim "replay <5s" วัดแบบ informal — ต้อง benchmark จริง
- ทั้งสามจะถูก execute จริงใน Phase 6.1 นี้

**9. มี claim ใน release manifest ที่เกินหลักฐานหรือไม่ — มีจุดที่ต้องแก้ระดับคำ**
- `demo_ready: PASS_WITH_UNKNOWN` + UI "Demo: READY" ควรเป็น "READY (E2E pending)" —
  6.1 จะรัน E2E แล้วเปลี่ยนเป็น DEMO VERIFIED ด้วยหลักฐานจริง
- `config_hash` เป็นสตริงพรรณนา ไม่ใช่ hash จริง — 6.1 จะ hash จริง
- manifest ยังไม่มี hash ของ report/recovery/demo artifacts — จะเพิ่ม

## สรุปงานที่จะทำ (เรียงตาม §1 commits)

1. `phase6.1-recovery` — persistence checksum + corrupted→SAFE_STOP + events
   config_version + restart harness 8 scenarios จริง + failure-injection expansion
2. `phase6.1-replay-audit` — audit ทั้ง 16,992 (classification 100%, trace 27 mismatches)
3. `phase6.1-demo-hardening` — demo runner + Demo E2E + live-lock bypass suite + tick
   requirements + paper E2E redo + benchmark
4. `phase6.1-final-audit` — traceability/rule-registry audit + gates A–U + manifest refresh + final report
