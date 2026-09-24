# IMPLEMENTATION REPORT — PHASE 3

> วันที่: 2026-09-24 · SNIPER CashFlow Analyzer · External Evidence + Myfxbook Verification
> Baseline (freeze ก่อนเริ่ม — รันจริง): Desktop 286/286 · Web 105/105 · Integration 18/18 · GUI smoke 11/11

---

## Baseline

หยุดก่อนแก้และรันทุกชุดจริง — เขียวทั้งหมด (ดังบน) · หลังจบ Phase 3 ทุกชุดยังเขียว + tests ใหม่ 57 ตัว (ดู Tests Passed)

## Files Added

| ไฟล์ | เนื้อหา |
|---|---|
| `core/external_evidence.py` | ExternalEvidence v2 (ครบทุกฟิลด์ตามสเปก: id/source/url/name/retrieved/published/account_type/broker/platform/symbol/timeframe/period/raw_reference/extracted_metrics/extraction_status/confidence/notes/linked_*) · EvidenceSnapshot (append-only + hash) · EvidenceLink + human confirm · Conflict detection · SUPERSEDED · quality DIRECT/INDIRECT/CONTEXTUAL/UNKNOWN · INDIRECT-formula gate |
| `core/myfxbook.py` | MyfxbookImporter (URL→fetch→parse→validate→canonical→store+snapshot) · normalize_myfxbook_url (เก็บ original + normalized + trace ได้) · parser metrics/env/period (ขาด=UNKNOWN ไม่เดา) · duplicate→snapshot เพิ่ม · เนื้อหาเปลี่ยน→SUPERSEDED+record ใหม่ · IMPORT_FAILED พร้อมเหตุผลจริง · compare_environments (รายฟิลด์ MATCH/PARTIAL/MISMATCH/UNKNOWN) |
| `core/model_candidates.py` | ModelCandidate + store · lifecycle CANDIDATE/ACCEPTED/REJECTED/SUPERSEDED · accept ต้องมี reviewer + conflict-free · accept(+rules_patch)→ModelVersion ใหม่ (based_on_evidence + confirmed_by ผ่าน Phase 2 gate) |
| `core/external_report.py` | EXTERNAL_EVIDENCE_REPORT (Source/Retrieval/Period/Environment/Metrics/Snapshots/Linked Evidence+Assumptions+Observations/Candidates/Conflicts/Unknowns/Limitations) |
| `web/backend/evidence_api.py` | handlers 10 endpoints (เรียก core ล้วน) |
| `tests/test_external_evidence.py` | 17 tests (model/hash/snapshot/history/supersede/link/confirm/conflict/gate) |
| `tests/test_myfxbook.py` | 17 tests (URL normalize/valid/invalid/inaccessible/HTTP error/malformed/duplicate/changed/supersede/env compare 4 สถานะ) |
| `tests/test_model_candidates.py` | 13 tests (lifecycle/confirmation/accept→version/conflict-block/report) |
| `tests/web/test_web_evidence.py` | 10 tests (endpoints end-to-end + quality gate + honest failures) |
| `tools/patch_frontend_evidence.py` | สคริปต์ใส่หน้า Evidence (dev tool) |

## Files Modified

| ไฟล์ | การเปลี่ยน |
|---|---|
| `web/backend/app.py` | routing `/api/evidence/*` + `/api/model-candidates/*` (param-based + method gates) |
| `web/frontend/app.js` | หน้า "Evidence" (Import/รายการ/รายละเอียด/Link/Confirm/Candidates Accept/Reject) |
| `PROJECT_STATUS.md` | +หัวข้อ 18 Phase 3 |

## Tests Added

**+57** (desktop 47 · web 10) → รวม **333 desktop · 115 web**

## Tests Passed (รันจริงหลังเสร็จ)

```
Desktop/Core : 333/333 PASS (0 failed/skipped/errors)
Web          : 115/115 PASS (0 failed/skipped/errors)
Integration  : 18/18 PASS · GUI smoke 11/11 PASS · Core smoke PASS
Browser จริง : หน้า Evidence เรนเดอร์ + disclaimer + import box + candidates ครบ
```

## Myfxbook Access Result (ตามจริง — ไม่อ้างความสำเร็จ)

```
IMPORT BLOCKED
เหตุผล 1: myfxbook.com ตอบ HTTP 403 Forbidden แก่ probe จากเครื่องนี้ (bot protection)
เหตุผล 2: ยังไม่มี Myfxbook source URL จริงใน Evidence Registry (E001–E010 ไม่มี myfxbook source)
```

ตัว importer **พร้อมใช้งาน** และผ่านการทดสอบ 30 กรณีด้วย fixtures (fixtures อยู่ใน tests เท่านั้น ตามกฎ "ห้ามใช้ fixture เป็น production evidence") — เมื่อผู้ใช้มี URL บัญชีจริง ใส่ผ่านหน้า Evidence หรือ `POST /api/evidence/myfxbook/import` ระบบจะ fetch จริงและรายงานผลตามจริง (สำเร็จ/IMPORT_FAILED พร้อมเหตุผล) โดยไม่มีข้อมูลปลอม

## Imported Evidence (production)

**ไม่มี** — ตามจริง (ยังไม่มี source URL จริงให้ import) · registry seeds E001–E010 ยังเป็นหลักฐานภายในเดิม

## Snapshots

กลไกทำงานจริง (ทดสอบครบ): content_hash (SHA-256) + metrics_hash ต่อการ import · append-only — history ไม่ถูก overwrite (test ยืนยัน 3 snapshots เรียงลำดับ) · re-import เนื้อหาเดิม → snapshot ใหม่พร้อม note "unchanged" · เนื้อหาเปลี่ยน → record เก่า SUPERSEDED (เก็บ superseded_by) + record ใหม่

## Environment Comparisons

ทำงานจริงรายฟิลด์ (Broker/Platform/Symbol/AccountType/Timeframe): exact→MATCH · ซ้อนกัน→PARTIAL_MATCH · ต่าง→MISMATCH · ไม่มีข้อมูล→UNKNOWN (ไม่เดา) · บัญชีคนละ broker = environment ต่างกันเสมอ (ระบุใน note) · หลาย account เก็บแยกกันสมบูรณ์ (ไม่ aggregate)

## Candidate Rules

flow ครบ: Evidence→Link→Candidate→(conflict check)→**Human Review (reviewer name)**→Accept→ModelVersion ใหม่ (บันทึก based_on_evidence + previous_version + confirmed_by) · Reject/Supersede ทำงาน · มี conflict ที่ยังไม่แก้ = **ห้าม accept** (test ยืนยัน + แก้ด้วยการ unlink แล้ว accept ผ่าน)

## Conflicts

ตรวจจับจริง: link ที่ **confirmed แล้ว** ฝั่ง supports และ contradicts ชนกันที่ assumption/observation เดียวกัน → CONFLICT (แสดงสองฝั่ง ไม่เลือกข้าง ไม่แก้ model ให้ตรง) · unconfirmed ไม่นับเป็น conflict

## Unknowns

period/published_at/account_type ที่ source ไม่มี = UNKNOWN (ไม่เดา) · quality ที่ source type ไม่รู้จัก = UNKNOWN · เอกสารรายงาน unknowns ทุกฟิลด์ที่ขาด

## Limitations (ระบุใน report ทุกครั้ง)

1. `External performance data does not prove internal EA formulas.` (บังคับใน disclaimer + gate)
2. Myfxbook เป็น INDIRECT — ใช้ context/cross-check เท่านั้น ห้าม supports สูตร (gate บน server + test)
3. หน้า Myfxbook ที่ render ด้วย JS อาะ parse ไม่ออก → IMPORT_FAILED พร้อมเหตุผล แทนการเดา
4. หลาย account ไม่ aggregate เป็น universal behavior

## Regression

Baseline ทั้งหมดยังเขียว · ไม่แก้ regression pin ใด ๆ · ไม่มีสูตร/preset/parameter เปลี่ยน

## Remaining Gaps

(1) ยังไม่มี production Myfxbook import จริง (รอ URL จริงจากผู้ใช้ + การเข้าถึงที่ไม่โดน 403 เช่นผ่าน shared-statements JSON ที่เปิด public) (2) Desktop GUI ยังไม่มีหน้า Evidence (ใช้ Web) (3) observation ↔ evidence link ยังทำผ่าน target_type=OBSERVATION ด้วย manual id (ยังไม่มี picker อัตโนมัติ) (4) HTML report ของ external evidence ยังไม่มี (มี JSON report)

## Recommended Next Phase

1. **ขอ source จริงจากผู้ใช้**: URL Myfxbook บัญชีจริงที่เปิด public → import จริงครั้งแรก + snapshot แรก
2. Desktop GUI Evidence page (อ่านจาก core เหมือน Web)
3. Timeline Simulator (ราคา-เวลา) ต่อจาก Phase 2 cycle timeline
4. ประเมินหลักฐานสะสม → ตัดสินใจว่าพอสำหรับ OUR EA Strategy Engine หรือยัง

---

## คำรับรองตามข้อกำหนด

```
No fake external data        ✓ (fixtures เฉพาะใน tests; production ไม่มีข้อมูลปลอม — IMPORT BLOCKED ตามจริง)
No automatic model correction ✓ (accept ต้องมี reviewer + conflict-free + ผ่าน confirmed_by gate)
No automatic learning        ✓ (ไม่มี ML/auto-generation ใด ๆ)
No live trading              ✓ (READ/IMPORT/ANALYZE/SIMULATE/VERIFY เท่านั้น)
No EX5 modification/decompilation ✓
```

## ACCEPTANCE CRITERIA — ผลตรวจ (22/22)

- [x] ExternalEvidence ใช้งานจริง (model+store+persistence)
- [x] Myfxbook importer ทำงานจริง **และรายงาน access limitation ถูกต้อง** (IMPORT BLOCKED + เหตุผล 2 ข้อ ตามข้อ 25)
- [x] Historical snapshot มี hash (content+metrics SHA-256, append-only)
- [x] External metrics แยกจาก internal EA rules (OBSERVED_EXTERNAL_METRIC + gate)
- [x] Multiple accounts แยก environment (ไม่ aggregate)
- [x] Evidence ↔ Assumption linking (supports/contradicts/context_for + confirm)
- [x] Evidence ↔ Observation linking (target_type OBSERVATION)
- [x] ModelCandidate ทำงาน (lifecycle ครบ)
- [x] Human confirmation gate (ทุก accept/confirm/reject ต้องมี reviewer)
- [x] Conflict detection (confirmed links เท่านั้น + block accept)
- [x] Environment comparison (4 สถานะ รายฟิลด์)
- [x] Evidence GUI ทำงานจริง (Web — ทดสอบ browser จริง)
- [x] Candidate GUI ทำงานจริง (Accept/Reject + confirmation)
- [x] API ทำงานจริง (10 endpoints + tests end-to-end)
- [x] Report ทำงานจริง (11 sections + disclaimer บังคับ)
- [x] No fake external data / [x] No automatic model correction / [x] No automatic learning
- [x] No live trading / [x] No EX5 modification/decompilation
- [x] Existing regression tests pass (333/333 + 115/115 รวมของเก่าครบ)
- [x] New tests pass (+57)
- [x] PROJECT_STATUS updated
