# PROJECT STATUS — SNIPER CashFlow Analyzer

> อัปเดต: 2026-09-23 · App v1.0.0 · สถานะ: **ใช้งานได้จริง (Working)** — ไม่มี mock/placeholder/TODO ใน logic

---

## 1. สิ่งที่ทำเสร็จ (ครบทั้ง 15 Module)

| Module | ความสำเร็จ | ไฟล์หลัก |
|---|---|---|
| M1 EA Config | พารามิเตอร์ครบ 27 ตัว (รวมช่อง Symbol ที่ชื่อ input ไม่เป็นที่รับรู้), preset $500/$3000 (ยืนยันจากอินโฟกราฟิกจริง), validation, save/load/export/import JSON | `core/config.py`, `desktop/pages/ea_settings.py` |
| M2 Grid Calculator | ตาราง Level/Distance/Lot/CumLot/Exposure/Floating P/L/Margin/AvgEntry, รองรับ depth 1–500 (5/10/20/30/50/100 + custom) | `core/grid.py`, `desktop/pages/grid_calculator.py` |
| M3 Worst Case | ตลาดวิ่งทางเดียว preset 10/20/30/50/75/100 + custom, 3 สถานการณ์ (BUY/SELL/BOTH), emergency note | `core/worst_case.py`, `desktop/pages/worst_case.py` |
| M4 Basket/Partial | จำลอง BasketCloseAllUSD, PartialTrigger/Percent/OnlyOnce, ระยะราคาที่ต้องเด้งกลับ, สลังที่เหลือหลัง partial | `core/basket.py` (แสดงผลในหน้า Grid Calculator) |
| M5 Risk Dashboard | สรุปครบทุก metric ตามสเปก + Risk Flags 6+ แบบ โดย threshold ผู้ใช้ตั้งเองได้ทั้งหมด | `core/risk.py`, `desktop/pages/risk.py` |
| M6 Backtest Import | CSV (tab/comma, UTF-16 ทนทาน), HTML (parse ทั้ง summary + deals table), TXT — ข้อมูลไหนไม่มีแสดง N/A | `core/backtest_io.py` |
| M7 Backtest Analyzer | grid depth (buy/sell/รวม), lot stats, worst drawdown episode, longest recovery, losing streak, equity curve | `core/backtest_analysis.py`, `desktop/pages/backtest.py` |
| M8 Set Builder | สร้าง combinations จาก list ค่า, filter ตามข้อจำเป็นจำกัด (DD/Grid/Lot/Margin), ไม่มีการจัดอันดับ "ดีที่สุด" | `core/setbuilder.py`, `desktop/pages/set_builder.py` |
| M9 Set Comparison | ตารางรวมทุก set + Save/Duplicate/Delete/Export/Import/Load | `core/setbuilder.py (SetStore)`, `desktop/pages/compare.py` |
| M10 Behavior Verification | บันทึกข้อมูลจริง (manual/import) เทียบ Simulation Model → MATCH/MISMATCH/UNKNOWN | `core/model_vs_observed.py`, `desktop/pages/behavior.py` |
| M11 Assumption Registry | ระบบกลาง 20 assumption IDs, 4 สถานะ, เปลี่ยนสถานะพร้อมหลักฐาน (persist), ทุกผลคำนวณแนบ assumption IDs | `core/assumptions.py`, `desktop/pages/settings.py` |
| M12 Export/Report | JSON + CSV + HTML (พิมพ์เป็น PDF จาก browser ได้ — ไม่เพิ่ม dependency) | `core/report.py`, `desktop/pages/reports.py` |
| M13 MT5 Data Pipeline | Adapter interface: CSVAdapter / TesterReportAdapter / LogAdapter / ManualAdapter → BehaviorRecord schema เดียว 17 ฟิลด์, Event types 10 แบบ | `core/mt5_adapters.py` |
| M14 Model vs Observed | ตรวจ 6 หมวด (spacing/lot/level/basket/partial/count), แนะนำ lot rule จาก observation (log-linear fit), "Apply Observed Rule" สร้าง model version ใหม่เมื่อผู้ใช้ยืนยันเท่านั้น | `core/model_vs_observed.py`, `core/model_rules.py` |
| M15 Test Session | Session แยกไฟล์ JSON ต่อ session (ID/version/broker/balance/events/comparison), New/Load/Delete | `core/sessions.py` |

**GUI (Windows Desktop, tkinter):** 11 หน้าครบตามสเปก — Dashboard, EA Settings, Grid Calculator, Worst Case, Risk, Backtest, Set Builder, Compare, Behavior Verification, Reports, Settings + toolbar New/Open/Save/Import/Export/Reset + status bar แสดง model version

**สถาปัตยกรรม:** Core (`core/`) ไม่ import tkinter เลย — GUI อยู่ใน `desktop/` เรียก Core อย่างเดียว ทุกสูตรอยู่ใน `core/calculations.py` จุดเดียว (ตรวจด้วย grep แล้วว่าไม่มีสูตรซ้ำนอกไฟล์นี้)

---

## 2. สิ่งที่ทดสอบแล้ว

- **Unit + integration tests: 157 tests / ผ่าน 157 / ตก 0** (`python run_tests.py`)
  - ครอบคลุม: default config, lot/grid/cumulative/basket/partial/worst-case/DD/margin calculation, validation ทุกกฎ, import/export round-trip ทุกชนิด, presets, assumption registry + persistence, adapters 4 ตัว, model-vs-observed, sessions, set builder/store, report exports
- **Regression tests** (`tests/test_regression.py`): pin ค่าตัวอย่าง BaseLot 0.1 / Multiplier 1.1 / GridStep 5 / XAUUSD cs=100 / ทุน $500 — เช่น lot sequence `[0.1, 0.11, 0.12, 0.13, 0.15]`, worst case $50 BOTH_SIDES = 11 levels / 1.95 lots / floating −$3,255 / DD 651% — ถ้าค่าเปลี่ยนโดยไม่ตั้งใจ test จะตกทันที
- **Integration end-to-end** (`python integration_check.py`): 18/18 ผ่าน — workflow จริงตั้งแต่เปิดโปรเจกต์ → คำนวณ → import backtest → สร้าง session → เทียบ model → export รายงาน → set builder → assumption evidence
- **GUI smoke test** (`python smoke_gui.py`): สร้างหน้าต่าง วนทุก 11 หน้า ไม่มี crash
- **ความสอดคล้องของการคำนวณ:** ตรวจว่า Grid Calculator / Worst Case / Risk ให้ตัวเลขชุดเดียวกันจาก core เดียวกัน (integration check ข้อ 2)

---

## 3. จำนวน tests

| ชุด | จำนวน | ผล |
|---|---|---|
| Unit/Integration (`tests/`, 14 ไฟล์) | 157 | ผ่าน 157 / ตก 0 |
| End-to-end workflow | 18 checks | ผ่าน 18 |
| GUI smoke | 11 หน้า | ผ่าน |

---

## 4. สิ่งที่เป็น Verified (จากเอกสารผู้ขาย — ไม่ใช่การรับประกัน)

- ค่า default พารามิเตอร์ทั้ง 27 ตัว (คู่มือ PDF 13 หน้า)
- Preset ทุน $500 / $3000 (ยืนยันซ้ำกับภาพอินโฟกราฟิกจริงทั้ง 2 ภาพ)
- GridStepUSD = ระยะราคา (หน่วยดอลลาร์ของสินทัพย์) ระหว่างออเดอร์
- Basket Close: ปิดทั้งหมดเมื่อกำไรรวมสุทธิถึง BasketCloseAllUSD
- Partial close ครั้งเดียวต่อรอบเมื่อ OnlyOnce=true
- Emergency: trigger ตามระยะราคาจากกรอบเทรด / เวลาทั้งหมดเป็นเวลาไทย ICT
- UseMartingale (ภาพ) = UsePositionSizeOptimization (PDF)

## 5. สิ่งที่เป็น Assumption (โมเดลจำลอง — สถานะ MODEL_ASSUMPTION)

สมบูรณ์ใน **Assumption Registry** (`core/assumptions.py`, ดูได้/แก้สถานะได้ในหน้า Settings):
- `LOT_FORMULA_ASSUMPTION_001` — lot = BaseLot × Multiplier^(level−1), normalize ตาม lot step
- `GRID_TRIGGER_ASSUMPTION_001` — วัดระยะจากราคาออเดอร์ล่าสุด
- `GRID_DIRECTION_ASSUMPTION_001` — เพิ่มไม้เฉพาะทิศตรงข้าม (averaging)
- `BOTH_SIDES_OPEN_AT_START_ASSUMPTION_001` — เปิด level 1 ทั้งสองฝั่งตอนเริ่มรอบ
- `BASKET_SCOPE_ASSUMPTION_001` — basket รวมสองฝั่งเป็นชุดเดียว (สลับ PER_SIDE ได้ใน model rules)
- `PARTIAL_CLOSE_ASSUMPTION_001` — ปิด % ของ volume รวมแบบ pro-rata
- `PL_CONVERSION_ASSUMPTION_001` — P/L = Δราคา × lot × contract size (ไม่รวม spread/commission/swap)
- `XAUUSD_CONTRACT_ASSUMPTION_001` — contract 100 oz (0.1 lot ≈ $10 ต่อ $1 — อ้างอิงรายงาน)
- `MARGIN_ASSUMPTION_001` — margin = lot × cs × ราคา / leverage × margin_rate
- `EMERGENCY_FRAME_ASSUMPTION_001` — กรอบเทรด = ช่วงราคาตั้งแต่เริ่มรอบถึงไม้ล่าสุด

## 6. สิ่งที่ยัง Unknown (ระบุชัด ไม่เดา)

- จำนวนชั้น Grid สูงสุดภายใน EX5 (`MAX_GRID_DEPTH_UNKNOWN_001`)
- ตรรกะภายใน EX5 ทั้งหมด (`EA_BEHAVIOR_NOT_VERIFIED_001`) — ต้องใช้ Behavior Verification สะสมหลักฐานแทนการ decompile (ซึ่งห้ามทำ)
- ชื่อ input จริงของพารามิเตอร์ #1 (`SYMBOL_INPUT_NAME_UNKNOWN_001`)
- ล็อกบัญชี/โบรกเกอร์/วันหมดอายุในไฟล์ปิด, magic number, spread/commission จริงของโบรกเกอร์

---

## 7. วิธีรันโปรแกรม

```bat
cd SNIPER-CashFlow-Analyzer
python run_app.py        # เปิดโปรแกรม (ต้องมี Python 3.10+ บน Windows — ใช้ stdlib ล้วน ไม่ต้อง install อะไร)

python run_tests.py          # รัน tests ทั้งหมด (157)
python integration_check.py  # รัน end-to-end workflow check (18)
python smoke_gui.py          # ตรวจ GUI ทุกหน้าแบบไม่เปิดหน้าต่างค้าง
```

ข้อมูลผู้ใช้เก็บใน `data/` — `sets.json`, `model_versions.json`, `assumptions_overrides.json`, `sessions/*.json`

## 8. วิธีนำ Core ไปทำ Web Version ภายหลัง

`core/` เป็น pure Python ไม่ผูก GUI:
1. สร้าง backend (FastAPI/Flask ก็ได้) import `core` ตรง ๆ
2. เรียกฟังก์ชันเดิม: `build_grid_table()`, `simulate_worst_case()`, `build_risk_summary()`, `simulate_basket()`, `parse_backtest_file()`, `compare_behavior()` ฯลฯ — ทุกฟังก์ชันคืน structured result ที่มี `to_dict()` + assumption IDs พร้อม serialize เป็น JSON แล้ว
3. config/project/report เป็น JSON versioned (`SNIPER_V1_68_CONFIG`, `SNIPER_PROJECT_V1`, `SNIPER_REPORT_V1`) — Web ใช้ schema เดียวกันได้ทันที
4. Logic คำนวณห้ามเขียนใหม่ — ถ้าต้องการภาษาอื่น (JS) ให้ยึด `tests/test_regression.py` เป็น golden values เพื่อพิสูจน์ว่าผลตรงกัน

## 9. ข้อจำกัดที่ระบุไว้ตามสเปก

- โปรแกรมนี้เป็น **Analyzer / Calculator / Simulator เท่านั้น** — ไม่มีคำสั่งซื้อขายจริง ไม่แก้บัญชี MT5 ไม่ควบคุม EA
- ไม่อ้างว่า simulation = ผล backtest จริง / ไม่รับประกันกำไร / ไม่จัดอันดับ set ว่า "ดีที่สุด-ปลอดภัยที่สุด"
- ไม่ decompile/แก้ไข `.ex5` และไม่เดาสูตรที่พิสูจน์ไม่ได้ — ทุกจุว่างระบุ UNKNOWN/ASSUMPTION พร้อมระบบรองรับการแก้ไข (Symbol Profile / Risk Thresholds / Model Rules / Assumption Registry แก้ได้ทั้งหมดโดยไม่แก้โค้ด)
