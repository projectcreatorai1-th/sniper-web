# PHASE 6 PROJECT BOUNDARY REPORT

**ตรวจสอบก่อนการเขียนใด ๆ ตาม PROJECT BOUNDARY LOCK (RULE 9) — 2026-09-24**

## CURRENT_PROJECT

**SNIPER CashFlow Analyzer** (ต่อไปนี้เป็น EVIDENCE SOURCE — READ-ONLY สำหรับ Phase 6)

- Identity markers: `core/calculations.py` (SSOT docstring), `core/evidence.py`,
  `core/forensics/`, `web/backend/app.py`, `desktop/`, `run_app.py`,
  `create_desktop_shortcut.py`
- โปรเจกต์ OUR EA จะถูกสร้างภายใน repository เดียวกันที่ `core/our_ea/`
  (ตาม Master Command §11 "ห้ามสร้าง project ใหม่ / ห้ามลบของเดิม")
  โดย Analyzer core เดิมทั้งหมดกลายเป็น read-only source

## CURRENT_REPOSITORY

```
git root : C:/Users/BANK/.zcode/workspace/default/SNIPER-CashFlow-Analyzer
remote   : origin https://github.com/projectcreatorai1-th/sniper-web.git
```

- Git root ตรงกับโฟลเดอร์โปรเจกต์เอง — **ไม่มีการแชร์ git กับ sibling projects**
- Branch: `main` · HEAD `3c37087` (Phase 4 final) + Phase 5 milestone commits

## CURRENT_BRANCH

`main` (up to date with origin/main ณ ตอนตรวจ; จะ commit ต่อใน branch นี้
ตาม milestone — ห้าม force push / reset --hard / clean -fd ตาม RULE 10)

## SOURCE_PROJECTS (siblings ใน workspace — ทั้งหมดห้ามแตะ)

Workspace `C:\Users\BANK\.zcode\workspace\default\` มีโปรเจกต์อื่น เช่น
`1144-Trading-OS`, `1144`, `1144 Projects`, `rodominicz-realtest`,
`ai-anime-studio`, `content-studio-landing*`, `director`, `grids`, `models`
และไฟล์ระดับ workspace (`SNIPER_CashFlow_V1.68_Full_Report.md` = เอกสารต้นทาง
read-only, `ea_*` media, `transcribe_ea.py`)

## READ_ONLY_ARTIFACTS (Analyzer → OUR EA contract)

| Artifact | สถานะ |
|---|---|
| `data/evidence_model/V1.68-EVIDENCE-MODEL-v1.0.json` + `.sha256.txt` | FROZEN — ห้ามแก้ (hash `124F08984284E880F268…`) |
| `data/evidence_model/V1.68-EVIDENCE-MODEL-v1.0-draft.json` | historical — ห้ามแก้ |
| `TRACEABILITY_MATRIX.csv` | contract — แก้ได้เฉพาะเมื่อมี Phase ใหม่พร้อม audit |
| `data/phase5_2_confirmation_packet.json`, `data/phase5_2_forensics.json` | forensic results — ห้ามแก้ |
| `data/phase5_3_confirmation_audit.json`, `data/phase5_3_gate.json` | confirmation audit — ห้ามแก้ |
| `data/evidence.json`, `data/model_candidates.json` | registries — append-only ผ่าน review เท่านั้น |
| `data/phase5_1_*`, `data/phase5_validation_results.json` | historical reports — ห้ามแก้ |
| `PHASE5_*_REPORT.md`, `PHASE5_GATE_REPORT.md`, `AUDIT_REPORT.md` ฯลฯ | historical reports — ห้ามแก้ |
| ไฟล์ข้อมูลต้นทาง 4 บัญชี (`C:\Users\BANK\Desktop\ReportHistory-*.xlsx`) | original datasets — ห้ามแก้ (hashes ฝังใน freeze) |

## WRITE_SCOPE (Phase 6 เขียนได้เฉพาะ)

```
core/our_ea/**            (ใหม่ — Behavioral Model, Strategy Core)
tests/our_ea/**           (ใหม่ — tests ของ OUR EA)
tools/phase6_*.py         (ใหม่ — orchestration/scripts)
PHASE6_*.md               (ใหม่ — รายงาน phase)
tester/**                 (ใหม่ — MT5 Strategy Tester package, §23)
data/our_ea/**            (ใหม่ — OUR EA state/output — แยกจาก data/ ของ Analyzer)
web/frontend/app.js       (เฉพาะเพิ่มหน้า OUR EA — ห้ามแตะ evidence/registry UI)
```

## FORBIDDEN_PATHS

1. ทุก path นอก `C:/Users/BANK/.zcode/workspace/default/SNIPER-CashFlow-Analyzer/`
2. READ_ONLY_ARTIFACTS ทั้งหมดข้างต้น (รวมถึงการ "แก้เพื่อให้ EA ทำงาน")
3. `core/calculations.py`, `core/forensics/**`, `core/evidence.py`,
   `core/cycle.py`, `core/basket.py` ฯลฯ — Analyzer runtime = read-only
   (RULE 4: OUR EA **ห้าม import** Analyzer runtime เช่น forensics/cycle
   reconstruction/basket forensic/evidence parser เข้า Strategy Core)
4. `desktop/**`, `web/backend/**` (ยกเว้นเพิ่ม read-only view ตามที่ Phase กำหนด)
5. `.ex5` ทุกไฟล์ (ห้ามแก้/decompile ตามกฎเดิม)

## ARCHITECTURE CONTRACT (FINAL BOUNDARY)

```
ANALYZER (read-only)
   ↓  V1.68-EVIDENCE-MODEL-v1.0.json + TRACEABILITY_MATRIX.csv (immutable contract)
OUR EA (core/our_ea/ — implementation เอง, trace กลับทุก rule)
   ↓
PAPER → DEMO → LIVE (LOCKED)
```

- **ไม่มี reverse write**: OUR EA → Analyzer ❌
- **ไม่มี runtime import**: Analyzer runtime → OUR EA runtime ❌
- มีเฉพาะ: Evidence Contract → OUR EA implementation ✅
- OUR EA policy (Risk Guard, Emergency Stop, Max Grid/Lot/DD, Margin/Spread
  protection, Timeout, Kill Switch, Restart Recovery) = **OUR EA POLICY**
  ห้ามเขียนกลับ V1.68 Evidence Model (RULE 6)
- UNKNOWN 4 ข้อ (Partial Trigger, Partial Volume, Emergency Mechanism,
  Restart Recovery) ต้อง emit `MODEL_UNCERTAINTY` — ห้าม implement เป็น
  V1.68 behavior (RULE 7)

## VERIFICATION RESULT

| ตรวจสอบ | ผล |
|---|---|
| git root = project folder | ✅ (ไม่ใช่ workspace root — ไม่มีพื้นที่ใช้ร่วม) |
| branch | ✅ main (ไม่มี merge ข้ามโปรเจกต์) |
| git status | ✅ ทุก change (11 M + 15 ??) อยู่ใน repo นี้เท่านั้น — ไม่มีการแตะ sibling |
| project identity | ✅ marker files ครบ (Analyzer) |
| frozen model integrity | ✅ hash ตรง sidecar (`124F0898…`) |
| boundary violation ที่ตรวจพบ | **ไม่มี** |

**BOUNDARY CONFIRMED — อนุญาตให้เขียนได้เฉพาะ WRITE_SCOPE ข้างต้นเท่านั้น**

## GIT DISCIPLINE (RULE 10 — บังคับใช้จากนี้)

- ก่อน implementation: `git status` ทุกครั้ง
- Milestone commits แยก: `phase6-model`, `phase6-state-machine`, `phase6-replay`,
  `phase6-risk`, `phase6-paper`, `phase6-release`
- ห้าม `reset --hard` / `clean -fd` / force push เว้นแต่ PROJECT_OWNER สั่งตรง
- Phase 5 milestone ถูก commit ก่อนเริ่ม Phase 6 (ด้านล่าง)
- Immutable contract artifacts ถูกบังคับ track ใน git (`git add -f
  data/evidence_model/ data/phase5_3_*.json`) เพราะ `data/` ถูก ignore —
  เพื่อรับประกันความ immutable ของ contract (RULE 8)
