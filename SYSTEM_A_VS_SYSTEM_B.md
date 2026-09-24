# SYSTEM A vs SYSTEM B — Side-by-Side + Duplication Audit
*ผลจาก source code จริง (AST + grep) · AUDIT ONLY*

## PHASE D — 20 พื้นที่

| Area | System A (Analyzer/Forensics/Evidence) | System B (OUR EA/Runtime) | Duplicate? | Compatible? | Recommendation |
|---|---|---|---|---|---|
| 1 Data Model | Position/Deal/Order (MT5 report) + EvidenceRecord | PositionRef/Basket/Event/Deal(ผ่าน adapter) | บางส่วน | ใช่ (B ผูกกับ contract) | SHARED_CONTRACT (dataset export แบบสายนี้) |
| 2 Event Model | Cycle/event แบบวิเคราะห์ย้อนหลัง | immutable Event + ledger + idempotency | ไม่ | ใช่ (trace_id เชื่อมได้) | คงแยก; เพิ่ม session_id/correlation_id ทีหลังได้ |
| 3 State Model | stateless analysis | StateMachine 17 สถานะ + ModeController | ไม่ | — | คงแยก |
| 4 Configuration | EAConfig (preset วิเคราะห์) | OurEaConfig (runtime, validated) | ตั้งใจซ้ำ | ใช่ (default B อิง evidence) | MUST_REMAIN_SEPARATE |
| 5 Calculation | calculations.py SSOT (floor) | LotEngine เอง (equivalence-tested) | **ตั้งใจซ้ำ 3 สาย** | ✅ พิสูจน์เท่ากัน | คงแยกตาม boundary + คุมด้วย equivalence test |
| 6 Risk | risk.py = สรุปความเสี่ยงเชิง view | RiskGuard = บังคับใช้จริง | คนละบทบาท | ใช่ | คงแยก |
| 7 Execution | ไม่มี (view ล้วน) | adapters + LIVE LOCK | ไม่ | — | B อย่างเดียว |
| 8 Persistence | JSON registries + frozen | checksum state + event ledger | LOGICALLY_SIMILAR (ไฟล์ JSON ทั้งคู่) | ใช่ | คงแยก (ความสำคัญความถูกต้องต่างกัน) |
| 9 Logging | reports/registry | EventLog (JSONL/CSV) + audit chain | คนละระดับ | ใช่ | คงแยก |
| 10 Replay | — (เป็นผู้ถูก replay) | ReplayEngine 16,992 comparisons | ไม่ | — | B อย่างเดียว |
| 11 Validation | forensics + SSOT tests | independent validator + OOS | เสริมกัน | ใช่ | คงคู่ (dev ≠ validator) |
| 12 Monitoring | ไม่มี | heartbeat/soak/monitoring collection | ไม่ | — | ADD: dashboard ทีหลัง |
| 13 API | web/backend 93 endpoints | ไม่มี API runtime ของตัวเอง | ไม่ | — | ดู TARGET_ARCHITECTURE |
| 14 UI | 13 หน้า + desktop 12 หน้า | 1 หน้า static export | ไม่ | ⚠️ export เก่า (drift) | ADD: refresh pipeline/หน้า runtime |
| 15 Runtime | offline/batch | tick-driven runtime | ไม่ | — | คงแยก |
| 16 Recovery | ไม่เกี่ยว | 8/8 scenarios + policy | ไม่ | — | B |
| 17 Time | server time ใน report | UTC canonical + integrity | LOGICALLY_SIMILAR | ใช่ | B เป็นมาตรฐานเมื่อรวม |
| 18 Hashing | dataset/manifest hashes | hash ทุกชั้น (model→state→event) | แนวคิดซ้ำ (ดี) | ใช่ | SHARED_CONTRACT (hash discipline) |
| 19 Versioning | evidence/SSOT version | 6 model versions + governance | LOGICALLY_SIMILAR | ใช่ | คงแยก, เชื่อมด้วย frozen hash |
| 20 Error handling | exceptions→report | SAFE_STOP/UNCERTAIN เสมอ | คนละปรัชญา (A วิเคราะห์, B fail-safe) | ใช่ | คงแยก |

## PHASE E — Duplication Audit (จัดประเภท)

| รายการ | จำนวนที่พบ | ประเภท | เหตุผลจาก evidence |
|---|---|---|---|
| lot normalization | 3 (calculations/forensics/our_ea) | **INTENTIONALLY_SEPARATE** | boundary lock RULE 4 ห้าม import; equivalence tests L1-L50 พิสูจน์เท่ากัน 100% |
| grid logic | 2 (A: worst_case view / B: grid_engine runtime) | INTENTIONALLY_SEPARATE | คนละบทบาท view vs decision |
| basket | 2 (A: basket.py sim / B: basket.py runtime) | INTENTIONALLY_SEPARATE | ชื่อเหมือน หน้าที่ต่าง |
| cycle | 2 (A: reconstruction / B: live identity) | INTENTIONALLY_SEPARATE + SHARED_CONTRACT_CANDIDATE (replay_dataset เป็นสะพานแล้ว) | |
| event | A ไม่มี runtime event / B มี | ไม่ซ้ำ | |
| order/position model | A: historical rows / B: refs + fills | LOGICALLY_SIMILAR | bridge ที่ต้องมีเมื่อต่อ MT5 = MT5Adapter |
| timestamp | A: string เซิร์ฟเวอร์เวลา / B: UTC ms | LOGICALLY_SIMILAR | B เป็น canonical เมื่อรวม |
| config | 2 ชุด | INTENTIONALLY_SEPARATE | คนละวัตถุประสงค์ |
| risk | 2 (view vs guard) | INTENTIONALLY_SEPARATE | |
| persistence | 2 รูปแบบ (registry JSON vs checksum envelope) | LOGICALLY_SIMILAR | B แข็งกว่า — ใช้แนว B ขยายผลทีหลังได้ |
| recovery | B อย่างเดียว | ไม่ซ้ำ | |
| hash | หลายจุดแต่ต่างวัตถุ | SHARED_CONTRACT_CANDIDATE | hash discipline เดียวกันทั้ง repo |
| replay | B อย่างเดียว | ไม่ซ้ำ | |
| validation | A tests + B tests + independent | เสริมกันโดยตั้งใจ | |
| monitoring | B อย่างเดียว | ไม่ซ้ำ | |
| API/server | web/backend ตัวเดียว | ไม่ซ้ำ | **ช่องสำคัญ**: ยังไม่มี API ให้ B runtime |
| PID | run_server ตัวเดียว | ไม่ซ้ำ แต่ **อ่อน** (ไม่มี lock — ดู audit H) | EXACT_DUPLICATE = 0 ทั้งหมดที่พบ |

**สรุป E: ไม่มี EXACT_DUPLICATE แม้แต่รายการเดียว** — ทุกคู่ที่หน้าตาคล้ายคือ "ตั้งใจแยกตาม boundary" และถูกคุมด้วย equivalence/parity tests หรือเป็นสะพานข้อมูล (replay_dataset) แล้ว
