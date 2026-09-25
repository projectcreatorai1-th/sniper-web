# CONTRACTS.md — SNIPER CashFlow Analyzer

This repository is the **producer** of the ecosystem's frozen machine
contracts. It consumes none of the downstream contracts.

## Contracts owned here

| Contract | File | Version | Consumers |
| --- | --- | --- | --- |
| Frozen Evidence Model | `data/evidence_model/V1.68-EVIDENCE-MODEL-v1.0.json` (+ `.sha256.txt` sidecar) | V1.68-EVIDENCE-MODEL-v1.0 · SHA256 `124F0898…` | Strategy Spec generation; OUR-EA (hard pin) |
| Strategy Specification (master) | `STRATEGY_SPEC/strategy_spec.json` | 1.0.0 · canonical SHA256 `4648DFBB…` | OUR-EA (sanctioned path only) |
| Parameter / State / Invariant / Evidence-binding specs | `STRATEGY_SPEC/*.json` | 1.0.0 (hashes pinned in `spec_version.json`) | OUR-EA |
| EA Build Contract | `STRATEGY_SPEC/ea_build_contract.json` | 1.0.0 · SHA256 `6EFBDA5A…` | OUR-EA (compatibility gate) |
| Replay dataset | `data/our_ea/replay_dataset_v1.json` (+ sidecar) | v1 · SHA256 `994955EA…` | OUR-EA (replay validation) |
| Gateway CLIENT contract | `core/gateway/contracts.py` | 1.0.0 | implements the shared Gateway Contract consumed by OUR-EA client and served by 1144 Trading OS |

## Versioning rules

- Spec semver: **any VERIFIED-rule change = MAJOR** (recorded in
  `STRATEGY_SPEC/spec_version.json` → `compatibility`).
- `spec_version.json` self-pins the SHA256 of every generated spec file and
  records `created_from_commit` (the analyzer commit the spec was generated
  from) and `generated_at`.
- The evidence model is frozen forever: single writer (freeze script), no
  runtime mutation path (`DO_NOT_MERGE_BOUNDARIES.md` rule 1).

## Change protocol

1. Change evidence only with new evidence (UNKNOWN/PARTIAL/REJECTED statuses
   never move for integration reasons).
2. Regenerate the spec deterministically from the frozen model.
3. Verify three-way consistency: `canonical_hash(strategy_spec) ==
   spec_version.strategy_spec_hash == ea_build_contract.compatibility hash`.
4. Commit the regenerated artifacts together; tag `spec/x.y.z`.
5. Downstream (OUR-EA) re-pins via its three-way verification — no
   notification mechanism exists; the tag is the publication unit.
