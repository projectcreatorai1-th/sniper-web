# EVIDENCE REGISTRY — SNIPER CashFlow V1.68

> 🤖 สร้างอัตโนมัติจาก Core source of truth (`python tools/generate_registry_docs.py`) — ห้ามแก้ไขมือเปลี่ยน แก้ที่ core แล้วรันใหม่เสมอ


หลักการ: `Evidence → Claim → Status → Assumption/Model` — หลักฐาน **ไม่เปลี่ยนสูตรอัตโนมัติเด็ดขาด** และ performance จากภายนอก (Myfxbook/backtest) ใช้ยืนยันสูตรภายใน EA ไม่ได้

ทั้งหมด **10 รายการ** (E001-E010 เป็น seed ที่มีหลักฐานจริง)

| ID | Source Type | แหล่ง | ข้ออ้าง (Claim) | ค่าที่สังเกต | สถานะ | ความมั่นใจ | พารามิเตอร์ |
|---|---|---|---|---|---|---|---|
| `E001` | DOCUMENTATION | EA file name / seller manual | EA version = 1.68 | 1.68 | `DOCUMENTED` | HIGH | — |
| `E002` | VIDEO | Installation Video — วิธีติดตั้ง EA SNIPER.mp4 | Observed platform = MT5 | MT5 | `OBSERVED` | MEDIUM | — |
| `E003` | VIDEO | Installation Video — วิธีติดตั้ง EA SNIPER.mp4 | Observed broker = XM Global | XM Global | `OBSERVED` | MEDIUM | — |
| `E004` | VIDEO | Installation Video — วิธีติดตั้ง EA SNIPER.mp4 | Observed account type = Hedge | Hedge | `OBSERVED` | MEDIUM | — |
| `E005` | VIDEO | Installation Video — วิธีติดตั้ง EA SNIPER.mp4 | Observed symbol = GOLDmicro | GOLDmicro | `OBSERVED` | MEDIUM | — |
| `E006` | VIDEO | Installation Video — วิธีติดตั้ง EA SNIPER.mp4 | Observed timeframe = M15 | M15 | `OBSERVED` | MEDIUM | — |
| `E007` | VIDEO | Installation Video — วิธีติดตั้ง EA SNIPER.mp4 | EmergencyDistanceFromCycleUSD observed default = 90.0 | 90.0 | `OBSERVED` | MEDIUM | EmergencyDistanceFromCycleUSD |
| `E008` | DOCUMENTATION | Seller preset image / PDF ($500 recommended) | $500 recommended EmergencyDistanceFromCycleUSD = 50.0 | 50.0 | `DOCUMENTED` | MEDIUM | EmergencyDistanceFromCycleUSD |
| `E009` | DOCUMENTATION | Seller preset image ($3000 recommended) | $3000 recommended values as supplied; values requiring confirmation remain unverified | — | `DOCUMENTED` | LOW | — |
| `E010` | OTHER | Recorded external baseline (historical) | EX5 SHA-256/MD5 historical baseline for SNIPER CashFlow V 1.68.ex5 | sha256=31E5176E794C29BE265EBF1B449B1047F2125C57A1CD227B25… | `DOCUMENTED` | MEDIUM | — |

**E007 vs E008 (สำคัญ):** `EmergencyDistanceFromCycleUSD` — OBSERVED DEFAULT = **90.0** (installation video) และ $500 RECOMMENDED PRESET = **50.0** เป็นสองระเบียนคนละชนิด ไม่รวมกัน และโมเดลจำลองคง default 50.0 ไว้เหมือนเดิม (ไม่ตีความ 90.0 เป็นสูตร และไม่ตีความ 50.0 ว่าเป็น internal EA default)

External Evidence (Myfxbook): มีเฉพาะ data model/interface (`core.evidence.ExternalEvidence`, `INTERFACE READY`) — ยังไม่มี importer และห้ามสร้างข้อมูลปลอม
