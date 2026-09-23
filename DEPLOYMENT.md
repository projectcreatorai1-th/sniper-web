# DEPLOYMENT — SNIPER CashFlow (Web)

> เว็บเป็น WSGI application มาตรฐาน (pure Python stdlib) — deploy กับ WSGI server ใดก็ได้
> ไม่มี database / login / secrets / external service: แอปเป็น calculator ล้วน ๆ stateless ทุก request

## 1. สิ่งที่ต้องมีบนเครื่อง server

- Python 3.10+ (พัฒนาและทดสอบบน 3.12) — **ไม่ต้อง pip install อะไรเลย** เพราะใช้ stdlib ทั้งหมด
- โฟลเดอร์ที่ต้องคัดลอกขึ้น server: `core/` และ `web/` (ทั้งสองโฟลเดอร์นี้พอ)

## 2. Environment variables (ทุกตัวมี default สำหรับ local เท่านั้น)

| ตัวแปร | ความหมาย | Default (local) | Production |
|---|---|---|---|
| `WEB_HOST` | bind address | `127.0.0.1` | ตั้งเป็น `0.0.0.0` หรือตาม platform |
| `WEB_PORT` | port | `8765` | ตาม platform (เช่น `$PORT`) |
| `WEB_MAX_UPLOAD_MB` | ขนาด upload สูงสุด (MB) | `8` | ตามต้องการ |

**ไม่มีค่าใด hard-code ไว้สำหรับ production ในโค้ด** (host/port/limit อ่านจาก env ทั้งหมด) และไม่มี secrets/ passwords/private paths ใน repo

## 3. วิธี deploy

### 3.1 waitress (แนะนำ — WSGI server โปรด่วน cross-platform)

```bat
pip install waitress
set WEB_HOST=0.0.0.0
set WEB_PORT=8080
waitress-serve --host=%WEB_HOST% --port=%WEB_PORT% web.backend.app:application
```

(Linux/macOS: `WEB_HOST=0.0.0.0 WEB_PORT=8080 waitress-serve --host=0.0.0.0 --port=8080 web.backend.app:application` — รันจาก root ของโปรเจกต์)

### 3.2 Docker

```bat
docker build -f web/deploy/Dockerfile -t sniper-web .
docker run --rm -p 8080:8080 sniper-web
```

Dockerfile ตั้ง `WEB_HOST=0.0.0.0` / `WEB_PORT=8080` ให้แล้ว (รับ `PORT` env มาทับได้)

### 3.3 Platform-as-a-Service (Render / Railway / Fly.io ฯลฯ)

- **Build command:** ไม่ต้องมี (ไม่มี dependency) — หรือ `pip install waitress` ถ้าใช้ waitress
- **Start command:** `python web/backend/run_server.py` (ค่า env `WEB_HOST`/`WEB_PORT` ให้ตั้งเป็น `0.0.0.0` และ port ของ platform)
  หรือ `waitress-serve --host=0.0.0.0 --port=$PORT web.backend.app:application`
- Health check path: `/api/health`

### 3.4 หลังคั่นด้วย reverse proxy (nginx)

```nginx
location / { proxy_pass http://127.0.0.1:8765; proxy_set_header Host $host; }
```

## 4. ตรวจสอบหลัง deploy (smoke test จริง)

```bat
curl https://<host>/api/health
python tools\make_check_payloads.py
python tools\runtime_check.py https://<host>
```

`runtime_check.py` ตรวจ 21 รายการ: ทุก API endpoint, parity กับ core, malformed input, upload security, static traversal

## 5. ข้อควรระวังด้าน security เมื่อ deploy สาธารณะ

- แอปไม่มีคำสั่งซื้อขาย/MT5/execution ใด ๆ โดยออกแบบ — ตรวจซ้ำได้จาก `tests/web/` (upload security suite)
- Upload จำกัด `.csv/.html/.htm/.txt` ≤ `WEB_MAX_UPLOAD_MB` (default 8) — ไฟล์ถูก parse เป็น text เท่านั้นแล้วลบทันที
- JSON body จำกัด 2MB, Set Builder จำกัด 300 combinations ต่อครั้ง (ป้องกัน CPU abuse)
- ถ้าต้องการ rate limit / TLS ให้ทำที่ reverse proxy หรือ platform
- ไม่เปิด CORS (frontend กับ API serve จาก origin เดียวกัน)

## 6. โครงสร้างที่เกี่ยวข้องกับ deployment

```
core/                  ← calculation core (ต้องคัดลอกขึ้น server เสมอ)
web/backend/           ← WSGI app + API + run_server.py
web/frontend/          ← static (index.html / app.js / style.css)
web/deploy/Dockerfile
tools/runtime_check.py ← post-deploy smoke test
```

## 7. อนาคต (ยังไม่ได้ทำตามสเปก MVP)

- ระบบ account/user: API ออกแบบ stateless + envelope มาตรฐานเดียวไว้แล้ว รองรับการเพิ่ม auth layer ภายหลังได้โดยไม่แก้ core
- การแก้สถานะ assumption / model rules จากเว็บ: ปัจจุบันอ่านอย่างเดียว (เขียนผ่าน Desktop เพื่อกัน multi-user เขียนชน `data/`)
