# PROVENANCE.md — SNIPER CashFlow Analyzer

This repository sits at the **top of the ecosystem provenance chain**:

```
Frozen Evidence Model (here, hash-pinned forever)
  → deterministic generation (tools/generate_strategy_spec.py)
Strategy Specification 1.0.0 (here, STRATEGY_SPEC/, self-pinned)
  → hash compatibility gate
EA Build Contract 1.0.0 (here)
  → consumed via ../SNIPER-CashFlow-Analyzer (sanctioned path, verify())
OUR-EA  (github.com/projectcreatorai1-th/our-ea)
  → Gateway Contract 1.0.0
1144 Trading OS (github.com/projectcreatorai1-th/1144-trading-os)
  → MT5 → Broker
```

## Current published state

- Tag **`spec/1.0.0`** → commit `175a259` (pushed to origin).
- `spec_version.json`: spec 1.0.0 / schema 1.0.0, spec hash `4648DFBB…`,
  build-contract hash `6EFBDA5A…`, evidence model `124F0898…`,
  `created_from_commit` = `b7c87b426c…`.
- Strategy Spec state 1.0.0 is the state OUR-EA tag `ea/v1.0.0` verifies
  against (its deployment manifest pins the same hashes).

## How to verify (read-only)

```bash
python - <<'PY'
import json, hashlib
def canon(o): return hashlib.sha256(json.dumps(o, sort_keys=True,
    separators=(",", ":"), ensure_ascii=False, default=str
    ).encode()).hexdigest().upper()
ss = json.load(open("STRATEGY_SPEC/strategy_spec.json"))
sv = json.load(open("STRATEGY_SPEC/spec_version.json"))
bc = json.load(open("STRATEGY_SPEC/ea_build_contract.json"))
a = canon(ss)
assert a == sv["strategy_spec_hash"].upper()
assert a == bc["compatibility_requirements"]["strategy_spec_hash"].upper()
print("three-way consistency OK:", a)
PY
```

Full cross-repository audit: `1144-Trading-OS/THREE_REPO_PROVENANCE_AUDIT.md`.

## Regeneration policy

Regenerate ONLY with a reason (new evidence, provenance refresh) — never to
"make a check pass". After regeneration, commit all changed spec files
together in one commit and move/create the `spec/x.y.z` tag. The frozen
evidence model itself is never regenerated.
