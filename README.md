# SNIPER CashFlow Analyzer — Web (EA V1.68 Simulation Model)

เครื่องมือคำนวณ/จำลอง EA SNIPER CashFlow V1.68 แบบเว็บ — Grid Calculator, Worst Case
Simulator, Risk Dashboard, Set Builder, Backtest Analyzer และรายงาน JSON/CSV/HTML

**Simulation Model — not verified internal EA formula.** เครื่องมือนี้เป็น
calculator/simulator เท่านั้น ไม่มีการเชื่อมต่อ MT5 ไม่มีคำสั่งซื้อขาย และไม่รับประกันกำไร

## สถาปัตยกรรมสั้น ๆ

- `core/` = Calculation Core เดียว (source of truth) — สูตรทั้งหมดอยู่ใน `core/calculations.py`
- `web/backend/` = WSGI API (pure Python stdlib) เรียก `core/*` โดยตรง — ไม่มีสูตรซ้ำ
- `web/frontend/` = HTML/JS/CSS ธรรมดา เรียก API อย่างเดียว
- Desktop (tkinter) กับ Web ใช้ Core ชุดเดียวกัน → ผลลัพธ์เหมือนกันเป๊ะ (พิสูจน์ด้วย parity tests)

## รันในเครื่อง (Python 3.10+ ไม่ต้อง install อะไร)

```bat
python web\backend\run_server.py     :: → http://127.0.0.1:8765
```

## Tests

```bat
python run_tests.py        :: core/desktop suite (157)
python run_web_tests.py    :: web suite: parity + API + HTTP + upload security (93)
```

## Deploy

ดู `DEPLOYMENT.md` (waitress / Docker / Render และอื่น ๆ) — host/port รับจาก env
(`WEB_HOST`, `WEB_PORT`, หรือ `PORT` แบบ PaaS) ตรวจหลัง deploy ด้วย
`python tools\runtime_check.py https://<host>`

## หน้าเว็บ

หน้าแรก · EA Settings (27 พารามิเตอร์ + presets) · Grid Calculator · Worst Case ·
Risk Dashboard · Set Builder (ไม่มีการจัดอันดับ) · Backtest Analyzer (CSV/HTML/TXT) ·
รายงาน · Assumption Registry (Verified / Observed / Model assumption / Unknown)
