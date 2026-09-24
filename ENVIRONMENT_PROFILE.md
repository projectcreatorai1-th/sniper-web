# ENVIRONMENT PROFILE — SNIPER CashFlow V1.68

> 🤖 สร้างอัตโนมัติจาก Core source of truth (`python tools/generate_registry_docs.py`) — ห้ามแก้ไขมือเปลี่ยน แก้ที่ core แล้วรันใหม่เสมอ


## Observed Test Environment (ENV-OBS-001)

| Field | ค่า |
|---|---|
| environment_id | ENV-OBS-001 |
| ea_version | 1.68 |
| platform | MT5 |
| broker | XM Global |
| account_type | Hedge |
| symbol | GOLDmicro |
| timeframe | M15 |
| leverage | UNKNOWN |
| currency | UNKNOWN |
| contract_size | UNKNOWN |
| tick_size | UNKNOWN |
| tick_value | UNKNOWN |
| volume_min | UNKNOWN |
| volume_max | UNKNOWN |
| volume_step | UNKNOWN |
| margin_mode | UNKNOWN |
| source | Installation Video — วิธีติดตั้ง EA SNIPER.mp4 (E002-E006) |
| status | OBSERVED |

> OBSERVED TEST ENVIRONMENT. M15 is NOT a required timeframe, XM Global is NOT a required broker, GOLDmicro is NOT a universal symbol. Account numbers are deliberately not stored.

ข้อกำหนด: **ห้ามเก็บ account number** (ไม่มี field นี้ในโมเดลโดยเจตนา) · leverage กำหนดโดย user/test data เท่านั้น · ค่าที่ไม่ทราบ = `UNKNOWN`

## Parameter Facts (แยกชัด: โค้ด-ชื่อ ≠ ตัวตนพารามิเตอร์)

| Parameter | ชื่อในโค้ด | สถานะตัวตน | ระเบียนค่า |
|---|---|---|---|
| PARAM_18 | EmergencyDistanceFromCycleUSD | `DOCUMENTED` | OBSERVED VALUE=90.0 (OBSERVED); RECOMMENDED PRESET=50.0 (DOCUMENTED); EA DEFAULT=50.0 (MODEL) |
| PARAM_21 | AccumTargetUSD | `UNKNOWN` | — |

> PARAM_21: `AccumTargetUSD` เป็น **UNVERIFIED CANDIDATE** เท่านั้น — ตัวตนของแถว "ใส่ 0 = ปิดใช้งาน" ยังเป็น UNKNOWN จนกว่าจะมีหลักฐาน

## EX5 Integrity Record

| Field | ค่า |
|---|---|
| filename | SNIPER CashFlow V 1.68.ex5 |
| format | EX5 format 2 |
| EA version | 1.68 |
| file_size | — |
| sha256 (computed) | — |
| md5 (computed) | — |
| **status** | **SOURCE_FILE_NOT_PRESENT** |
| historical SHA-256 | 31E5176E794C29BE265EBF1B449B1047F2125C57A1CD227B257F89A54BF9CE37 (RECORDED_EXTERNAL_BASELINE) |
| historical MD5 | 3972D8436537F36F08FDF1E35C45750A (RECORDED_EXTERNAL_BASELINE) |
| recorded_at | 2026-09-24T09:43:22 |

> Source .ex5 not present in this workspace; no fake file is created and no hash is fabricated. Historical baselines are external records only. — ตรวจซ้ำวันไหนก็ได้ด้วย `python -c "from core.ex5_integrity import record_ex5_integrity as r; print(r().to_dict())"` (ถ้ามีไฟล์จริงจะคำนวณ hash จากไฟล์นั้นเท่านั้น)
