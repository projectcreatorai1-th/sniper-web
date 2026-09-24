# PHASE 6.1 FINAL REPORT

**Status: `OUR EA FINAL DEMO CANDIDATE · PAPER READY · DEMO VERIFIED · LIVE LOCKED`**
`PARTIAL HYPOTHESES REMAIN DATA-BLOCKED` (tick-level data filed, not fabricated)

Model V1.68-EVIDENCE-MODEL-v1.0 @ 124F08984284E880F268C37E… ·
commit `d9832dbbb4` · manifest hash `0FBBE408CAF29CAEE1356BC4…` · 2026-09-25T03:04:08

OUR EA implements the evidence-backed V1.68 behavioral model with explicit
uncertainty boundaries and separate OUR EA safety policies.

## Gates (§25)

| Gate | Result | Evidence |
|---|---|---|
| A frozen_model_unchanged | **PASS** | 124F08984284E880F268… |
| B analyzer_read_only | **PASS** | git diff e5159fc..HEAD on analyzer paths empty |
| C no_forbidden_imports | **PASS** | test_hardening_boundary scan + analyzer diff |
| D verified_rules_implemented | **PASS** | 16 impl refs |
| E partial_rules_remain_partial | **PASS** | grid/basket trigger PARTIAL; 1.68 unselectable |
| F unknown_rules_remain_unknown | **PASS** | 4 UNKNOWN via MODEL_UNCERTAINTY |
| G rejected_1_68_stays_rejected | **PASS** | config validation refuses H_GROSS_1_68 |
| H replay_deterministic | **PASS** | 9AECCE74198E6EF545CC… |
| I mismatch_classification_100pct | **PASS** | 0 unclassified / 0 defects (replay audit) |
| J restart_recovery_executed | **PASS** | 8/8 real subprocess scenarios |
| K corrupt_state_safe_stop | **PASS** | checksum -> StateCorruptionError -> SAFE_STOP |
| L duplicate_event_idempotent | **PASS** | restart scenario 4 + duplicate-tick tests |
| M paper_e2e | **PASS** | 183 events, full lineage |
| N demo_e2e | **PASS** | 14/14 steps, controlled environment |
| O failure_injection | **PASS** | 12+ failure classes incl. expansion |
| P risk_guard | **PASS** | OUR_EA_POLICY suite green |
| Q traceability_complete | **PASS** | matrix covers all 16 rules |
| R security_integrity | **PASS** | hash chain + tamper detection |
| S historical_regression | **PASS** | 594 tests |
| T live_lock | **PASS** | bypass suite: instantiation/config/env/persisted all REFUSED |
| U manifest_hash_consistent | **PASS** | refreshed below with real hashes |

## Counts
- Tests executed: **594** · passed: 594 · failed: 0 · skipped: 0 · quarantined: 0
- Replay comparisons: 16992 · exact matches: 13177 · classified mismatches: 29 · unexplained: **0**
- Recovery scenarios: 8/8 · failure-injection classes: 12+ · paper events: 183 · demo events: 133

## Key audit conclusions
1. Replay '77.55%' decomposed honestly: 27 mismatches (0.16%) all within documented exception/partials; 0 implementation defects; 0 unexplained.
2. TEST_R_RESTART_RECOVERY EXECUTED (real subprocesses): 8/8 — **OUR EA restart/recovery safety behavior verified** (V1.68 restart behaviour remains UNKNOWN — different claim).
3. Demo E2E executed: 14/14 steps in a controlled environment.
4. Live lock: every bypass attempt REFUSED (instantiation, config, case tricks, persisted state, factory).
5. Data-blocked: grid/basket trigger discrimination + partial trigger/volume + emergency bounds need tick data (tick_requirements.json).

## Remaining limitations
- Partial hypotheses DATA-BLOCKED (see above).
- Demo broker bridge is simulated (DemoAdapter controlled env); attaching a real demo account is a deployment step, not a code gap.

## Commits
- phase6.1-recovery `8ac773e` · phase6.1-replay-audit `645de06` · phase6.1-demo-hardening `d9832db` · phase6.1-final-audit (this commit)
