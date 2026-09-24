# FULL SYSTEM AUDIT REPORT
*AUDIT ONLY — ไม่มีการแก้โค้ด/config/runtime/process ใด ๆ · 2026-09-25 · ทุกข้อเถียงจากการ scan/AST/grep จริง*

## PHASE A — COMPLETE INVENTORY (AST scan ทั้ง repo)

**Python: 174 files · 311 classes · 435 top-level functions · 14 directories** + JS 2 files + HTML 1

| พื้นที่ | Files | Classes | หน้าที่ | RUNTIME? | Tests |
|---|---|---|---|---|---|
| **SYSTEM A** | | | | | |
| `core/` (31f, 66c) | 31 | 66 | SSOT formulas, registries, sim views | ไม่ (offline analysis) | tests/ 26 ไฟล์ + web 7 |
| `core/forensics/` (9f, 15c) | 9 | 15 | mt5_report/cycle_reconstruction/lot/grid/partial/basket/emergency/recovery | ไม่ | tests/forensics 3 |
| `web/backend/` (8f, 4c, 93fn) | 8 | 4 | HTTP API + static (pure stdlib WSGI) | ใช่ (เมื่อเปิดเซิร์ฟเวอร์) | tests/web 7 (125 tests) |
| `desktop/` (17f) | 17 | 16 | tkinter 12 หน้า | ใช่ (เมื่อเปิด app) | smoke ผ่าน web parity |
| `tools/` (35f, 117fn) | 35 | 0 | phase scripts (A-side phase5 + B-side phase6-10) | ไม่ (batch) | ผ่านการรันจริงทุก phase |
| **SYSTEM B** | | | | | |
| `core/our_ea/` (19f, 72c) | 19 | 72 | contract/rule_registry/uncertainty/state_machine/events/basket/lot/grid/partial/broker/idempotency/persistence/risk_guard/execution/config/strategy/replay/simulation/ops/data_pipeline | ใช่ (runtime core) | tests/our_ea 5 (94 tests) |
| `validation/` (1f) | 1 | 0 | independent validator (โค้ดแยกใหม่) | ไม่ | ตัวมันคือ validator |
| `tests/` รวม | 41 ไฟล์ | | | | **610 tests ผ่านทั้งหมด** |
| Frontend | app.js (1,850+ บรรทัด, 13 หน้า) + our_ea/our_ea_page.js | | SPA hash-routing | ผ่านเบราว์เซอร์ | 125 web tests + JS syntax |
| เอกสาร root | 50 ไฟล์ .md + manifests/registry JSON | | | ไม่ | — |

State/persistence ทั้งระบบ: `data/evidence.json`, `data/model_candidates.json`, `data/assumption_overrides.json` (A) · `data/our_ea/` state/logs/replay_dataset (B) · Frozen: `data/evidence_model/` (git-tracked, hash-sealed) · ไม่มี database engine ใด (ไฟล์ล้วน)

## PHASE B — SYSTEM A AUDIT

- **Data flow**: xlsx 5 ตาราง → mt5_report → cycle_reconstruction → แต่ละ engine → evidence/candidates → freeze — ผ่านการทดสอบ 4 บัญชีจริง
- **Calc flow**: `core/calculations.py` เป็น SSOT เดียวของฝั่ง A (floor หลัง MC-001) — grep ยืนยันไม่มี formula ซ้ำใน A
- **Evidence flow**: registry (append-only) → confirmation → frozen model (1 ครั้ง, hash-sealed) → OUR EA อ่านแบบ verify-hash
- **Frozen model access (grep จริง)**: `writers = 1` (`tools/phase5_3_freeze.py` — ประวัติศาสตร์, รันครั้งเดียว Phase 5.3) · `readers = core/our_ea/contract.py (verify-hash ก่อนใช้), tests, tools hash-check` · `runtime mutation paths = 0` ✅
- **Web backend**: stateless ต่อ request สำหรับ evidence (โหลดจาก JSON) — ยกเว้น module import ครั้งเดียวตอน startup (จุดเสี่ยง stale-memory เมื่อรันนาน)
- **Desktop**: 12 หน้า tkinter ใช้ core เดียวกับ web (parity tests คุม)

## PHASE C — SYSTEM B AUDIT (สถานะต่อชิ้น)

| ชิ้น | สถานะ | หลักฐาน |
|---|---|---|
| Strategy/Decision core | COMPLETE | strategy.py + 94 tests + replay |
| Signal (tick→decision) | COMPLETE | on_tick + guards |
| Risk | COMPLETE | risk_guard RK-1.1 (11 limits + kill) |
| Execution abstraction | COMPLETE | 4 adapters, LIVE locked |
| State machine | COMPLETE | explicit-only + recovery paths |
| Recovery | COMPLETE (policy) | 8/8 subprocess scenarios |
| Reconciliation | PARTIAL | framework + block มี; ต้องมี broker จริงถึงจะใช้เต็ม |
| Idempotency | COMPLETE | ledger + restore continuity |
| Kill switch (4 layers) | COMPLETE | ops.py + tests |
| Cancel-on-disconnect | COMPLETE (logic) | ENV_BLOCKED การใช้จริง (ไม่มี connection) |
| Broker/MT5 adapter | **MISSING ตัวจริง** | มีเพียง DemoAdapter จำลอง — ENVIRONMENT_BLOCKED |
| Event ledger | COMPLETE | EventLog JSON/JSONL/CSV + unique id |
| Persistence | COMPLETE | checksum + fsync + atomic |
| Config | COMPLETE | validated schema, ไม่มี silent fallback |
| Monitoring/Diagnostics | PARTIAL | ระบบวัดมี (soak/heartbeat); ยังไม่มี dashboard รันได้ (UI เป็น static export) |
| Paper | COMPLETE (verified E2E) | 183 events |
| Shadow/Observation | COMPLETE (mode controller) | ใช้ได้เมื่อมี market feed จริง — ENV_BLOCKED ตอนนี้ |
| Demo | PARTIAL→ENV_BLOCKED | E2E 14/14 ผ่านใน controlled env; MT5 demo จริงรอ environment |
| OOS/Stress/Capacity | COMPLETE | สั่งวัดจากข้อมูลจริง/สังเคราะห์แยกชัด |
| DR | COMPLETE | exercise 6/6 |
| Surveillance | COMPLETE | post-trade checks + Phase 9 |

## PHASE F — EVIDENCE BOUNDARY AUDIT (import graph จริง)

- `grep` imports จาก `core/our_ea/` ไป analyzer internals (**core.forensics / core.evidence / core.cycle / core.basket / core.calculations / MT5**): **0 รายการ** ✅
- Analyzer runtime imports ปรากฏเฉพาะใน `tools/` (export/audit scripts — ตามข้อยกเว้น RULE 8 ของ Boundary Lock: " Analyzer ใช้เพื่อ analysis เท่านั้น") และ `validation/` ไม่ import analyzer เลย (โค้ดอิสระ) ✅
- Reverse write (runtime→evidence): ไม่มี path ใดเขียน frozen model นอกจาก freeze script ประวัติศาสตร์ ✅
- **CRITICAL BOUNDARY FINDING: 0** — flow จริงคือ Analyzer → Frozen Contract (hash) → OUR EA ตามที่กำหนด

## PHASE G — "ตรงกับตัวโปรแกรมหรือไม่"

| ห่วงโซ่ | ผล |
|---|---|
| Frontend→API | ใช้ relative `fetch("/api/...")` same-origin ✅ ไม่มี hard-coded host/port |
| API→Core | ผ่าน web/backend → core/ SSOT ✅ (125 web parity tests) |
| UI OUR EA page | อ่าน **static export** (`release_status.json`) — **STALE_DRIFT พบจริง**: หน้าแสดง `OUR-EA-RC-v1.0 @01:49 (match 77.55%)` ขณะที่ manifest จริงคือ `OUR-EA-v1.0-final @03:32` — ต้องรัน `tools/phase6_release.py` เพื่อ refresh (ยังไม่แก้ตามคำสั่ง) |
| Runtime vs source | **STALE_RUNTIME พบจริง**: เซิร์ฟเวอร์ 2 ตัวซ้อน 8765 (PID 258364 รันโค้ดใน memory ตั้งแต่ 9/24 16:09 = ก่อน SSOT floor + evidence ทั้งชุด; PID 255408 @9/25 01:48) + PID file ชี้โปรเซสตาย (235240) — นี่คือสาเหตุ "เว็บเปิดไม่ได้/ข้อมูลไม่ตรง" |
| Model version ใน UI | หน้า OUR EA แสดง model hash เดียวกับ frozen (จาก export) ✅ เมื่อ refresh แล้ว |

## PHASE H — SERVER / RUNTIME ARCHITECTURE (root cause ของเคส 8765)

ตรวจ `web/backend/run_server.py` จริง:
- ไม่มี argparse → **`--port 8799` ถูกเงียบๆ ตัดทิ้ง** (อ่านเฉพาะ env WEB_PORT/PORT) → เซิร์ฟเวอร์"ทดสอบ"ที่คิดว่าอยู่ 8799 ไป bind 8765 จริง
- **ไม่มี single-instance lock / ตรวจ port-in-use ก่อน bind** → bind ได้ซ้อนเพราะอีกตัว bind 0.0.0.0 vs 127.0.0.1
- **ไม่มี stale-PID detection** (เขียน PID หลัง bind, ลบตอน shutdown สะอาดเท่านั้น — โปรเซส crash ทิ้ง PID ตายไว้)
- Frontend connection: same-origin ถูกแล้ว

**การจัดประเภท root cause**: เป็น **ทั้งสองอย่าง — Architecture gap เป็นต้นเหตุ, Operational เป็นตัวจุดชนวน** (ถ้ามี instance-lock/arg-validation ความผิดพลาด `--port` จะถูกปฏิเสธตั้งแต่แรก)

## PHASE I — DATA FLOW UNIFICATION (16 ขั้น)

INPUT→RAW DATA: EXISTING (data_pipeline, B) · NORMALIZATION: EXISTING (tick-level; ระดับ report อยู่ที่ A) · ANALYSIS: EXISTING (A/forensics, offline) · EVIDENCE: EXISTING (frozen) · DECISION: EXISTING (B) · RISK: EXISTING (B) · EXECUTION: EXISTING (B/adapter) · **MT5: MISSING (ตัวจริง) — NEEDS_INTERFACE** · DEAL/POSITION: DUPLICATED (A วิเคราะห์ย้อนหลัง / B รันไทม์ — ต่างบทบาท, ต้องมี bridge จาก MT5) · CYCLE/BASKET: DUPLICATED (A=reconstruction, B=live) · CLOSE: EXISTING (B) · RECONCILIATION: NEEDS_INTERFACE (มี framework รอ broker) · AUDIT: EXISTING (event ledger + reports)

## PHASE J — SSOT AUDIT

| เรื่อง | มีกี่ implementation | ใครควรเป็น/เป็น SSOT |
|---|---|---|
| Evidence | 1 (frozen json) | ✅ frozen contract |
| Lot | **3** (calculations / forensics LotEngine / our_ea LotEngine) | A=calculations (analysis), B=our_ea (runtime) — สามสายพิสูจน์เท่ากันด้วย tests; ตั้งใจแยกตาม boundary |
| Grid/Basket/Cycle | 2 ต่อชิ้น (A view/reconstruct vs B runtime) | ตั้งใจแยก — MUST_REMAIN_SEPARATE |
| Risk | 1 (our_ea RiskLimits) | ✅ |
| Config | **2** (EAConfig@A วิเคราะห์, OurEaConfig@B รันไทม์) | ตั้งใจแยก |
| Model version | 1 (frozen hash) | ✅ |
| Event ID | 1 (EventLog) | ✅ |
| Runtime state | 1 (PersistedState) | ✅ |
| Broker state | **MISSING** (ยังไม่มีตัวจริง) | MT5 authoritative เมื่อต่อ |

## PHASE K — CONFIGURATION AUDIT

- Duplicate: EAConfig vs OurEaConfig = **INTENTIONALLY_SEPARATE** (คนละวัตถุประสงค์, คนละ schema version)
- Conflicting: ไม่พบ (ค่า default B ผูกกับ VERIFIED rules ทั้งหมด)
- Hard-coded/hidden defaults: base_lot/step ใน OurEaConfig มาจาก evidence (E012/E015) — มี trace; hypothesis default (H_PREV_ENTRY/H_GROSS_1_00) เป็น **DECLARED choice** มี validation ห้าม 1.68
- Stale config: ไม่พบใน source; **พบใน runtime** (เซิร์ฟเวอร์เก่า + UI export เก่า — ตาม G/H)

## PHASE L — EVENT / STATE AUDIT

- Event fields จริง: event_id/timestamp/state_before-after/side/lot/price/level/rule_id/model_version/evidence_ref/execution_mode/trace_id/hypothesis_id/config_version/cycle_id/basket_id/position_id ✅ ตามสเปคเกือบครบ — **NOT_FOUND 2 ช่องเทียบ §11 ฉบับเก่า**: `correlation_id` แยกต่างหาก (ปัจจุบัน trace_id ทำหน้าที่นี้) และ `session_id` (มีใน DataSession ฝั่ง pipeline แต่ไม่ได้ส่งเข้า Event)
- Persistence/recovery/replay ของ event: ครบ (JSONL append + restore ผูก idempotency)
- Mode state machine (INIT→OBSERVATION→SHADOW→DEMO, LIVE locked): มีและถูกทดสอบ — **แต่ UI ยังไม่แสดง mode รันไทม์** (หน้า OUR EA เป็น static export; desktop ไม่มีหน้า B เลย) = ช่องว่างเดียวของ state visibility

## PHASE M — TEST ALIGNMENT

A กับ B ทดสอบคนละพฤติกรรมโดยตั้งใจ (A=สูตร/วิเคราะห์ย้อนหลัง, B=รันไทม์) — จุดเชื่อมคือ SSOT-equivalence tests + replay ที่ทำหน้าที่"ทดสอบข้ามระบบ"แทน
Gap ที่พบ: (1) ไม่มี test บังคับความสดของ release_status.json → เกิด drift จริง (G) (2) ไม่มี test lifecycle ของเซิร์ฟเวอร์ (instance-lock) → เกิด double-server จริง (H) (3) ไม่มี test ทดสอบ fresh-process ของ web backend กับ frozen hash ล่าสุด (ป้องกัน stale-memory)

## PHASE T — FINAL INTEGRITY CHECK

`git status` สะอาด (0 การเปลี่ยนแปลงก่อนเขียนเอกสาร) · frozen hash `124F08984284E880F268C3…` unchanged ✅ · ไม่มีการ start/stop/restart/terminate/MT5/order/sibling ในรอบนี้ · ไฟล์ที่เพิ่มในรอบ audit = เอกสาร 6 ชุดนี้เท่านั้น (แสดงแยกใน git status เป็น untracked)
