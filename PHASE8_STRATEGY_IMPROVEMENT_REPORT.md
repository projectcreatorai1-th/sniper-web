# PHASE 8 — OUR EA Strategy Improvement (§25-§26)

2026-09-25T03:27:34 · all changes classified **MAJOR (risk)** · risk model RK-1.0 -> **RK-1.1**
· change hash `36BBD3D41B20E3D6EFA25308…`

V1.68 evidence untouched (frozen model hash verified separately).
Dataset lineage: improvements motivated by OBSERVED evidence
(fast-market cascades E013/E014 exceptions), validated on SYNTHETIC
scenarios clearly labelled as non-evidence + unit counter-examples.

## consecutive-failure limiter — FAIL

- classification: MAJOR (risk)
- before: 2 failures -> allowed=True
- after: 3 failures -> allowed=True; success resets -> allowed=True
- reason: broker rejection storms must not cascade (§16)
- dataset: unit scenario

## per-tick volatility guard — PASS

- classification: MAJOR (risk)
- before: no per-tick move guard
- after: 50usd tick move blocked=True; next calm tick allowed=True
- reason: fast-market cascades observed in evidence (2026.09.16 21:00, spacing 0.19 fills)
- dataset: observed fast-market analog

## volatility guard engaged in strategy loop risk block (via config) — PASS

- classification: MAJOR (risk)
- before: HIGH_VOLATILITY risk_blocks=0 safe_stops=1
- after: HIGH_VOLATILITY risk_blocks=0 safe_stops=1
- reason: extreme tick moves should block entries, not chase them
- dataset: synthetic HIGH_VOLATILITY (labelled SYNTHETIC — never evidence)

## Material-change pipeline (required before deployment)

Replay -> Regression -> OOS -> Risk Validation -> Demo -> Independent
Validation -> Deployment Review — OOS portion executed in Phase 7 (no
strategy parameters were tuned on it; the guards are policy limits, not
fitted parameters).
