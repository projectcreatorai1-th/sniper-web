# INDEPENDENT VALIDATION REPORT (§23)

2026-09-25T03:30:30 · validator re-derived expectations from RAW data with independent
code (fresh xlsx parser, own ladder implementation, own OOS split) —
developer test suites were NOT the evidence here.

| # | Check | Verdict | Detail |
|---|---|---|---|
| 1 | frozen-hash | **CONFIRMED** | 124F08984284E880F268… |
| 2 | status-preservation | **CONFIRMED** | UNKNOWN/VERIFIED/REJECTED preserved in frozen contract |
| 3 | ladder-set-membership[floor] | **CONFIRMED** | membership 5157/5163 — floor must cover ~everything; round/ceil are distinguishable but overlap; decisive test is rank-based below |
| 4 | ladder-set-membership[round] | **CONFIRMED** | membership 4578/5163 — floor must cover ~everything; round/ceil are distinguishable but overlap; decisive test is rank-based below |
| 5 | ladder-set-membership[ceil] | **CONFIRMED** | membership 3748/5163 — floor must cover ~everything; round/ceil are distinguishable but overlap; decisive test is rank-based below |
| 6 | rank-ladder[floor] | **CONFIRMED** | errors 0/4451 |
| 7 | rank-ladder[round] | **CONFIRMED** | errors 310/4451 |
| 8 | rank-ladder[ceil] | **CONFIRMED** | errors 1727/4451 |
| 9 | direction-counterexample | **CONFIRMED** | random side rate 0.52 — proves 99.8% is not an artefact of the metric |
| 10 | 1.68-oos-counter-hypothesis | **CONFIRMED** | violations 157/163 |
| 11 | tamper-detection | **CONFIRMED** | promoting UNKNOWN by editing JSON changes the hash -> detectable at load |

## Verdict: ALL CONFIRMED

Counterexample challenges executed: round/ceil ladders fail at L5/L7/L10
(rank-based), random-direction baseline ~50% (metric sanity), 1.68 fails
OOS by the validator's own split, tampering the frozen contract changes
its hash (detected at load). Negative cases preserved.
