"""Render registry documentation FROM the core source of truth.

Generates (do not edit by hand - rerun this tool instead):
    ASSUMPTION_REGISTRY.md
    EVIDENCE_REGISTRY.md
    ENVIRONMENT_PROFILE.md   (includes the EX5 integrity record)

Run:  python tools/generate_registry_docs.py
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.assumptions import default_registry  # noqa: E402
from core.environment import observed_test_environment  # noqa: E402
from core.evidence import default_evidence_registry  # noqa: E402
from core.ex5_integrity import record_ex5_integrity  # noqa: E402
from core.param_facts import parameter_facts  # noqa: E402

GENERATED_NOTE = ("> 🤖 สร้างอัตโนมัติจาก Core source of truth "
                  "(`python tools/generate_registry_docs.py`) — ห้ามแก้ไขมือเปลี่ยน "
                  "แก้ที่ core แล้วรันใหม่เสมอ\n")


def w(name: str, text: str) -> None:
    path = os.path.join(ROOT, name)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote", name)


def render_assumptions() -> str:
    reg = default_registry()
    order = {"VERIFIED_FROM_DOCUMENTATION": 0, "OBSERVED_FROM_TESTING": 1,
             "MODEL_ASSUMPTION": 2, "UNKNOWN": 3}
    items = sorted(reg.all(), key=lambda a: (order.get(a.status, 9), a.assumption_id))
    counts = {}
    for a in items:
        counts[a.status] = counts.get(a.status, 0) + 1
    lines = [
        "# ASSUMPTION REGISTRY — SNIPER CashFlow V1.68", "", GENERATED_NOTE, "",
        f"ทั้งหมด **{len(items)} รายการ** — "
        + " · ".join(f"{k}: {v}" for k, v in sorted(counts.items())), "",
        "สถานะ: `VERIFIED_FROM_DOCUMENTATION` (ระบุในเอกสารผู้ขาย) · "
        "`OBSERVED_FROM_TESTING` (ยืนยันจาก MT5 จริง) · "
        "`MODEL_ASSUMPTION` (สมมติฐานโมเดล) · `UNKNOWN` (ไม่มีข้อมูล — ไม่เดา)", "",
        "| ID | หมวด | สถานะ | ความมั่นใจ | หัวข้อ | โมดูลที่เกี่ยวข้อง | แหล่งอ้างอิง |",
        "|---|---|---|---|---|---|---|",
    ]
    for a in items:
        mods = ", ".join(a.affected_modules) or "—"
        src = a.source or "—"
        conf = a.confidence or "—"
        cat = a.category or "—"
        lines.append(f"| `{a.assumption_id}` | {cat} | `{a.status}` | {conf} "
                     f"| {a.title} | {mods} | {src} |")
    lines += ["", "รายละเอียดเต็มของแต่ละรายการอยู่ใน `core/assumptions.py` "
              "(และดูได้ผ่าน `GET /api/assumptions`)", ""]
    return "\n".join(lines)


def render_evidence() -> str:
    reg = default_evidence_registry()
    lines = [
        "# EVIDENCE REGISTRY — SNIPER CashFlow V1.68", "", GENERATED_NOTE, "",
        "หลักการ: `Evidence → Claim → Status → Assumption/Model` — "
        "หลักฐาน **ไม่เปลี่ยนสูตรอัตโนมัติเด็ดขาด** และ performance จากภายนอก "
        "(Myfxbook/backtest) ใช้ยืนยันสูตรภายใน EA ไม่ได้", "",
        f"ทั้งหมด **{len(reg.all())} รายการ** (E001-E010 เป็น seed ที่มีหลักฐานจริง)", "",
        "| ID | Source Type | แหล่ง | ข้ออ้าง (Claim) | ค่าที่สังเกต | สถานะ | ความมั่นใจ | พารามิเตอร์ |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in reg.all():
        obs = r.observed_value if r.observed_value else "—"
        if r.observed_value and len(r.observed_value) > 60:
            obs = r.observed_value[:57] + "…"
        lines.append(f"| `{r.evidence_id}` | {r.source_type} | {r.source_name} "
                     f"| {r.claim} | {obs} | `{r.status}` | {r.confidence} "
                     f"| {r.parameter or '—'} |")
    lines += [
        "",
        "**E007 vs E008 (สำคัญ):** `EmergencyDistanceFromCycleUSD` — "
        "OBSERVED DEFAULT = **90.0** (installation video) และ "
        "$500 RECOMMENDED PRESET = **50.0** เป็นสองระเบียนคนละชนิด ไม่รวมกัน "
        "และโมเดลจำลองคง default 50.0 ไว้เหมือนเดิม (ไม่ตีความ 90.0 เป็นสูตร "
        "และไม่ตีความ 50.0 ว่าเป็น internal EA default)", "",
        "External Evidence (Myfxbook): มีเฉพาะ data model/interface "
        "(`core.evidence.ExternalEvidence`, `INTERFACE READY`) — ยังไม่มี importer "
        "และห้ามสร้างข้อมูลปลอม", "",
    ]
    return "\n".join(lines)


def render_environment() -> str:
    env = observed_test_environment()
    ex5 = record_ex5_integrity()
    fields = env.observed_fields()
    lines = [
        "# ENVIRONMENT PROFILE — SNIPER CashFlow V1.68", "", GENERATED_NOTE, "",
        "## Observed Test Environment (ENV-OBS-001)", "",
        "| Field | ค่า |", "|---|---|",
    ]
    for k in ("environment_id", "ea_version", "platform", "broker", "account_type",
              "symbol", "timeframe", "leverage", "currency", "contract_size",
              "tick_size", "tick_value", "volume_min", "volume_max", "volume_step",
              "margin_mode", "source", "status"):
        lines.append(f"| {k} | {fields.get(k)} |")
    lines += [
        "",
        f"> {env.notes}", "",
        "ข้อกำหนด: **ห้ามเก็บ account number** (ไม่มี field นี้ในโมเดลโดยเจตนา) · "
        "leverage กำหนดโดย user/test data เท่านั้น · ค่าที่ไม่ทราบ = `UNKNOWN`",
        "", "## Parameter Facts (แยกชัด: โค้ด-ชื่อ ≠ ตัวตนพารามิเตอร์)", "",
        "| Parameter | ชื่อในโค้ด | สถานะตัวตน | ระเบียนค่า |", "|---|---|---|---|",
    ]
    for f in parameter_facts():
        recs = "; ".join(f"{v.kind}={v.value} ({v.status})" for v in f.value_records) or "—"
        lines.append(f"| {f.parameter_id} | {f.code_name or '—'} | `{f.status}` | {recs} |")
    lines += [
        "",
        "> PARAM_21: `AccumTargetUSD` เป็น **UNVERIFIED CANDIDATE** เท่านั้น — "
        "ตัวตนของแถว \"ใส่ 0 = ปิดใช้งาน\" ยังเป็น UNKNOWN จนกว่าจะมีหลักฐาน",
        "", "## EX5 Integrity Record", "",
        "| Field | ค่า |", "|---|---|",
        f"| filename | {ex5.filename} |",
        f"| format | {ex5.format} |",
        f"| EA version | {ex5.ea_version} |",
        f"| file_size | {ex5.file_size if ex5.file_size is not None else '—'} |",
        f"| sha256 (computed) | {ex5.sha256 or '—'} |",
        f"| md5 (computed) | {ex5.md5 or '—'} |",
        f"| **status** | **{ex5.status}** |",
        f"| historical SHA-256 | {ex5.historical_sha256} ({ex5.historical_status}) |",
        f"| historical MD5 | {ex5.historical_md5} ({ex5.historical_status}) |",
        f"| recorded_at | {ex5.recorded_at} |",
        "",
        f"> {ex5.notes} — ตรวจซ้ำวันไหนก็ได้ด้วย `python -c \"from core.ex5_integrity "
        "import record_ex5_integrity as r; print(r().to_dict())\"` "
        "(ถ้ามีไฟล์จริงจะคำนวณ hash จากไฟล์นั้นเท่านั้น)", "",
    ]
    return "\n".join(lines)


def main() -> None:
    w("ASSUMPTION_REGISTRY.md", render_assumptions())
    w("EVIDENCE_REGISTRY.md", render_evidence())
    w("ENVIRONMENT_PROFILE.md", render_environment())


if __name__ == "__main__":
    main()
