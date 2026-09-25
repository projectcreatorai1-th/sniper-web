# VERSIONING.md — SNIPER CashFlow Analyzer

Four version layers are in use. They are NOT interchangeable.

| Layer | Form | Current | Lives in |
| --- | --- | --- | --- |
| Code version | git commit SHA + tags | `175a259` (tag `spec/1.0.0`) | git |
| Product/system | analyzer release identity | V1.68 lineage (evidence model name) | evidence model filename |
| Contract version | semver | Strategy Spec 1.0.0 · Build Contract 1.0.0 · Gateway 1.0.0 | artifact JSON + `core/gateway/contracts.py` |
| Artifact hash | SHA256 (canonical JSON / file) | spec `4648DFBB…` · model `124F0898…` · replay `994955EA…` | `spec_version.json`, sidecars |

## Tag scheme

- `spec/x.y.z` — annotated tag on the commit containing a published Strategy
  Specification state (x.y.z = spec semver). `spec/1.0.0` → `175a259`.

## Rules

- Provenance-only spec regeneration (e.g. `created_from_commit` refresh)
  keeps spec version at the same semver but changes the canonical hash;
  `ea_build_contract` re-pins it. OUR-EA accepts this via three-way
  consistency (see `PROVENANCE.md`).
- The ecosystem-wide component/version table is maintained in the
  1144-Trading-OS repository: `COMPATIBILITY_MATRIX.md`.
- Never bump a contract version without updating every pin of it in the same
  commit.
