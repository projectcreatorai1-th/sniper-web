# FINAL LIVE DECISION PACKET (§47)

**SYSTEM STOPS HERE: LIVE_GATE_PENDING — the EA never decides this.**

## Verified facts
- 8 VERIFIED V1.68 rules implemented and replay-verified (OOS 0 lot errors)
- 594+ tests green · replay deterministic · recovery 8/8 · demo E2E 14/14
- DR exercised · secrets clean · independent validation CONFIRMED

## Unknowns (never promoted)
- Emergency Mechanism
- Partial Trigger
- Partial Volume Rule
- Restart Recovery

## Partial rules (hypothesis-configurable, no winner)
- Basket Trigger Semantics
- Grid Trigger Semantics
- Partial Level Rule

## Rejected
- AccumulatorTargetUSD = 1.68 per basket (OOS violations 96.32%)

## Risk limits in force (OUR_EA_POLICY RK-1.1)
max positions/depth/lot/loss/drawdown/margin/spread/slippage/
consecutive-failures/tick-volatility · multi-layer kill · kill switch

## Observations
- basket closes cluster ≈ +$1.0-1.2 (domain OBSERVED; trigger PARTIAL)
- worst observed production grid: 32 levels / 20.07 lots / 28.1h
  survived to +21.80 — V1.68 risk profile is the decision context

## Blocking gaps for LIVE (all documented, none fabricated)
- extended forward demo (ENVIRONMENT-LIMITED)
- interactive broker capability audit (ENVIRONMENT-BLOCKED)
- tick-level data for PARTIAL/UNKNOWN resolution (DATA-BLOCKED)

## Exact release identity
- commit `7eef4942babde6abd56f4d04f0459a87f8a5a74e` · manifest `71E0525190D1482BA2206DFEDACC15D003D75BF9B29E75FBC2041F053AF95E34` · frozen model
  `124F08984284E880F268C37E…`

**Awaiting: HUMAN DECISION (PROJECT_OWNER). LIVE remains LOCKED.**
