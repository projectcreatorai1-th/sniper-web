# INTEGRATION BASELINE — P0 (ก่อนแก้ไขใด ๆ)
*บันทึกจากการ inspect จริง 2026-09-25 ~06:05*

## Git
- commit `b71d870` (origin/main sync) · branch `main` · working tree: สะอาด ยกเว้นเอกสาร audit 6 ชุด (untracked — จะ commit ใน milestone 1)
- manifest hash `71E0525190D1482BA2206DFE…` · frozen `124F08984284E880F268C37E…` (ตรง sidecar)

## Server / port ปัจจุบัน (ปัญหาที่ P0 จะจัดการ)
| พอร์ต | PID | Command line | สถานะเจ้าของ | การจัดการ |
|---|---|---|---|---|
| 8765 (127.0.0.1) | 255408 | `python.exe web/backend/run_server.py --port 8799` | **ของโปรเจกต์นี้** (คำสั่ง run_server.py + ถือพอร์ต 8765) — คือ instance ที่ session นี้ทิ้งไว้ (ตั้งใจ 8799 แต่ argument ถูกเงียบ) | จะ terminate ใน P0 |
| 8765 (0.0.0.0) | 258364 | `python web\backend\run_server.py` | **ของโปรเจกต์นี้** (คำสั่งตรง) — instance เก่า 9/24 16:09 (pre-SSOT-floor) | จะ terminate ใน P0 |
| 8799 | — | ว่าง | — | — |
| PID file | 235240 | โปรเซสตายแล้ว | stale | จะลบอย่างปลอดภัย |
| **ห้ามแตะ** | 259324 | `python tools/p9r_gates.py` | session อื่น | ไม่แตะ |
| **ห้ามแตะ** | 267928 | `pytest -q` | session อื่น | ไม่แตะ |

## Entrypoints / routes ปัจจุบัน
- Server: `web/backend/run_server.py` (env-only port, ไม่มี argparse/lock/stale-PID)
- API: `web/backend/app.py` (~93 endpoints กลุ่ม /api/*) — **ไม่มี** `/api/our_ea/*`
- UI: SPA 13 หน้า + `#/our-ea` (อ่าน static export `web/frontend/our_ea/release_status.json` = RC-v1.0 เก่า)

## Inventory ที่เกี่ยวข้อง
- OUR EA: `core/our_ea/` 19 ไฟล์ 72 classes (strategy/ops/data_pipeline/runtime ยังไม่มี service)
- Analyzer (ห้ามแตะ): core/calculations.py, core/forensics/**, core/evidence.py, core/cycle.py, core/basket.py, data/evidence.json, model_candidates.json

## Baseline tests (pytest -q, ก่อน implementation)
**610 passed · 0 failed · 0 skipped · 0 errors** (3 subtests passed, 3.87s)

## เป้าหมาย P0→P3
P0 ปิดเซิร์ฟเวอร์เก่าที่ยืนยันเจ้าของได้ → เหลือ 1 instance จากโค้ดปัจจุบัน · P1 lifecycle hardening (argparse+lock+stale-PID+shutdown+diagnostics) · P2 UI freshness อ่าน API สด · P3 runtime service + `/api/our_ea/*` + session/correlation
