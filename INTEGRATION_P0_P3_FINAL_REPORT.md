# INTEGRATION P0→P3 FINAL REPORT
*2026-09-25 · ทุกผลมาจากการรันจริง (server/process/API/browser-level render/tests)*

## 1. Executive Summary
P0→P3 เสร็จสมบูรณ์ใน 4 commits: **ONE WEB SERVER (single-instance lock) · ONE UI SHELL (Analyzer เดิม + OUR EA runtime สด) · ONE API HOST (/api/our_ea/* 13 routes) · ONE RUNTIME SERVICE (owner ของ OUR EA lifecycle)** — โดยไม่รวม logic ของ A/B แม้แต่บรรทัดเดียว (boundary scan ยัง 0, frozen hash ไม่เปลี่ยน, Analyzer logic byte-identical)

## 2. Baseline (INTEGRATION_BASELINE_P0.md)
commit `b71d870` · pytest baseline **610 passed** · frozen `124F0898…` · เซิร์ฟเวอร์ซ้อน 2 ตัว + PID ตายค้าง (ปัญหาจาก audit)

## 3. P0 — Runtime cleanup (commit 6bdb67c)
- ยืนยัน ownership ด้วย command-line ก่อน terminate ทุกตัว: ปิด 255408 + 258364 (verified SNIPER servers) · PID ตาย 235240 ลบ · **ห้ามแตะ 259324/267928 ตามคำสั่ง — ไม่ถูกแตะ**
- หลัง cleanup: SNIPER instance เดียวจากโค้ดปัจจุบัน

## 4. P1 — Lifecycle hardening (commit 597b861)
argparse `--host/--port` จริง (ชนะ env; env ยังใช้เป็น fallback PaaS) · single-instance lock + ตรวจ process-identity ผ่าน command line (ห้าม kill แค่เพราะเลข PID ตรง) · stale/foreign PID ลบแบบปลอดภัย · port preflight (PORT_BUSY refuse) · clean shutdown SIGINT/SIGTERM/SIGBREAK (ลบ PID ตัวเองเท่านั้น — ทดสอบ "PID คนอื่นไม่ถูกลบ") · startup diagnostics (root/PID/lock/manifest hash/frozen hash)
**Tests 13/13 จริง** รวม **100 start/stop cycles** (race-tolerant ต่อ parallel suite โดยไม่ลดเกณฑ์: นับเฉพาะ cycle ที่ start จริง 100)

## 5-6. P2+P3 — Runtime Service / API / UI (commit 35a3e08 + fix)
- **RuntimeService** (`core/our_ea/runtime_service.py`): owner เดียวของ runtime — mode (INIT→OBSERVATION→SHADOW→DEMO; LIVE unreachable), state/risk/reconciliation/health/events, **typed provenance contract** (runtime_version/state_version/manifest_hash/trace_id/timestamp_utc/session_id ทุก response)
- **API** (`/api/our_ea/*`): 8 read-only + 5 command (start_observation/promote_shadow/promote_demo/kill/live) — **ไม่มี trading endpoint ใด ๆ** · command ทุกตัวต้องมี operator identity · promote_demo = ENVIRONMENT-BLOCKED (ไม่ปลอม DEMO) · live = LIVE_LOCKED + audit event
- **app.py**: เพิ่มเพียง dispatch hook (hook-purity test ยืนยันว่าไม่มีบรรทัด analyzer logic เปลี่ยน)
- **UI rewrite**: หน้า `#/our-ea` อ่าน runtime สด — STALE/OFFLINE detection, provenance แสดงครบ (manifest 71E052…/frozen 124F08…/session RT-…/PID/UTC), operator commands (audit-logged), refresh 5s loop เดียว + reconnect
- **§11 fix**: Event ได้ `session_id` + `correlation_id` (backward-compatible — historical ledger ใช้ต่อได้, มี test ยืนยัน)

## 7. Architecture before/after
Before: A กับ B ไม่เชื่อมกันขณะรัน; UI ของ B อ่าน static export เก่า; เซิร์ฟเวอร์ไม่มี lifecycle
After: `UI → /api/our_ea/* → RuntimeService → OUR EA components` ใน process เดียว; Analyzer อยู่หลัง read-only boundary เดิม; Frozen contract เป็นสะพานเดียว (hash-verified ทุกโหลด)

## 12-15. Session/boundary/frozen
session_id `RT-…` + correlation_id บน event/ทุก snapshot ✓ · runtime service ไม่ import Analyzer ใด (AST test) ✓ · **frozen `124F08984284E880F268C3…` unchanged ก่อน-ระหว่าง-หลัง** ✓ · `git diff 6bdb67c..HEAD` บน Analyzer logic + evidence = **0 ไฟล์** ✓

## 16. Test results
- Baseline 610 → **645 passed · 0 failed · 0 skipped** (เพิ่ม 35: lifecycle 13 + runtime/API/freshness/boundary/compat 22)
- Browser-level UI smoke จริงกับเซิร์ฟเวอร์รันอยู่: **11/11 PASS** (mode/manifest/frozen/session/PID/MT5 NOT_CONNECTED/LOCKED/commands/no-stale-export) — เจอและแก้ shim bug ของตัวทดสอบเอง (fetch recursion) ไม่ใช่ bug ของระบบ
- Analyzer UI ยังใช้งานจริง: / /api/config /api/evidence /api/assumptions /api/health = 200 ทั้งหมด

## 17-18. Security / LIVE LOCK
ไม่มี secret เพิ่ม · LIVE ถูกปฏิเสธทุกทางที่มีอยู่ (config/factory/mode) + **path ใหม่ทั้งหมด**: API command (`LIVE_LOCKED` + audit event), UI button (ผ่าน API เดียวกัน) — ทดสอบครบ · MT5 = NOT_CONNECTED จริงทุกชั้น (health/status/reconciliation/UI)

## 19-20. Known / environment limitations
- MT5 adapter ยังไม่มี (P4 งานแยก) → DEMO promotion = ENVIRONMENT-BLOCKED, reconciliation = NOT_CONNECTED (ไม่ปลอม)
- RuntimeService ใน P0-P3 ยังไม่มี market feed (ไม่มีการเทรด) — เป็น host + command + provenance layer พร้อมเสียบ feed ใน P4
- Browser smoke รันด้วย DOM shim บนเซิร์ฟเวอร์จริง (ไม่ใช่ screenshot) — ระบุตามจริงว่าไม่ใช่ browser engine เต็มตัว

## 21. Git commits
`6bdb67c` P0 · `597b861` P1 · `35a3e08` P2+P3 · final `INTEGRATION_REPORT` commit

## 22. Final decision
**INTEGRATION_P0_P3_COMPLETE** — โปรแกรมเดียวทำงานจริง (one server/one shell/one API host/one runtime service) โดย evidence boundary ไม่ถูกแตะ
**P4 MT5 DEMO: MAY START** (แต่เป็น work order แยกตามกฎ — ต้องมี environment/credential จริง)
