# SECURITY.md — SNIPER CashFlow Analyzer

## Source boundaries (enforced by `DO_NOT_MERGE_BOUNDARIES.md`)

1. Frozen Evidence Model has exactly ONE writer (the freeze script). Never
   add another writer.
2. V1.68 forensic truth is consumed only via the immutable export
   (`replay_dataset_v1` + SHA256).
3. Analyzer internals (`core/calculations`, `core/evidence`, `core/cycle`,
   `core/basket`, legacy `web/backend`, `desktop`) are read-only; integration
   work must not refactor them.
4. OUR-EA strategy logic must never be pulled into this repository;
   integration happens at service/API level only.
5. Demo/Live separation: the mode controller + LIVE lock stay on the runtime
   service; the web layer never calls adapters directly.
6. Evidence labels (`OUR_EA_POLICY` vs `V1.68`) must not be moved or merged.
7. UNKNOWN/PARTIAL/REJECTED evidence statuses change only with new evidence.

## Secrets

- No credentials, API keys, tokens or private keys in source (repo policy;
  scan before every commit).
- `.gitignore` excludes `.env`, `*.pid`, `.web_upload/`, working `data/`
  files; the tracked `data/` files are the pinned frozen artifacts listed in
  `CONTRACTS.md` only.
- Broker/MT5 credentials never pass through this repository: execution is
  downstream (1144 Trading OS adapter plane).

## Pre-integration checklist (from the boundary doc)

- [ ] frozen hash identical before/after
- [ ] import-boundary grep still clean
- [ ] `git diff` touches no `core/` evidence internals or
      `data/evidence_model/`
- [ ] full test suite green before and after
- [ ] LIVE bypass suite still green
