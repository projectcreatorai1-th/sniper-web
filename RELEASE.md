# RELEASE.md — SNIPER CashFlow Analyzer

## What a release is

A release is a **tagged, verified repository state**:

- Strategy Spec publication: tag `spec/x.y.z` on the commit containing the
  pinned spec artifacts (current: `spec/1.0.0` → `175a259`).
- Web/desktop deployments are independent of spec publication and follow
  their own deployment docs (`DEPLOYMENT.md`; web ships via
  `web/deploy/Dockerfile`).

## Release gate (all must pass)

1. `python run_tests.py` — full unittest suite green (baseline 706 tests).
2. Three-way spec hash consistency (see `PROVENANCE.md` verifier snippet).
3. Evidence model file SHA256 == sidecar == `124F0898…`.
4. Working tree clean; spec files committed in a single commit.
5. Boundary checklist green (`SECURITY.md`).

## Rollback

- Code: `git revert` / checkout of a prior tag. No history rewrite, no force
  push (repo rule).
- Spec publication: move forward, not back — publish a corrected
  `spec/x.y.z+1`; consumers (OUR-EA) re-verify via their three-way check and
  refuse incompatible MAJORs. The frozen evidence model is never rolled back.
- Web: redeploy previous Docker image / previous commit.

## After release

- Push tag + main to origin (normal push only).
- Record the new state in the ecosystem compatibility matrix
  (`1144-Trading-OS/COMPATIBILITY_MATRIX.md`).
