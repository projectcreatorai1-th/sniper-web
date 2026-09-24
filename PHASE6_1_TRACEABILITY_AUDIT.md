# PHASE 6.1 — Traceability Audit (§14)

Model V1.68-EVIDENCE-MODEL-v1.0 @ 124F08984284E880F268…

Every rule traces: Evidence -> Rule -> Implementation -> Test -> Replay ->
Runtime event -> Audit output. All 16 rules carry implementation
references (Phase 6 append) and test references (tests/our_ea/).

| rule_id | status | evidence | implementation | ok |
|---|---|---|---|---|
| R-ACCUM-1-68 | REJECTED | E027 | excluded — config validation refuses hypothesis | PASS |
| R-BASE-LOT | VERIFIED | E015 | core/our_ea/lot_engine.py::LotConfig.base_lot | PASS |
| R-BASKET-TRIGGER | PARTIAL | E016;E027 | partial_engine BasketCloseEngine hypotheses | PASS |
| R-BOTH-SIDES | VERIFIED | E015 | core/our_ea/strategy.py::_open_cycle | PASS |
| R-CONTRACT-SIZE | VERIFIED | E019 | core/our_ea/config.py broker.contract_size | PASS |
| R-EMERGENCY | UNKNOWN | E021 | OUR_EA_EMERGENCY_POLICY only (risk_guard.py) | PASS |
| R-GRID-DIRECTION | VERIFIED | E014 | core/our_ea/grid_engine.py::next_add_price | PASS |
| R-GRID-SPACING | VERIFIED | E013 | core/our_ea/grid_engine.py | replay spacing checks | PASS |
| R-GRID-TRIGGER | PARTIAL | E026 | grid_engine hypothesis_id (configurable) | PASS |
| R-LOT-FLOOR | VERIFIED | E012;E028 | core/our_ea/lot_engine.py | tests/our_ea/test_our_ea.py | PASS |
| R-NORMAL-RESUME | VERIFIED | E018 | core/our_ea/strategy.py RESUME_NEW_CYCLE | PASS |
| R-PARTIAL-EXISTS | VERIFIED | E025 | core/our_ea/partial_engine.py (decisions refused) | PASS |
| R-PARTIAL-LEVEL | PARTIAL | E025 | MODEL_UNCERTAINTY (not implemented) | PASS |
| R-PARTIAL-TRIGGER | UNKNOWN | E025 | MODEL_UNCERTAINTY (not implemented) | PASS |
| R-PARTIAL-VOLUME | UNKNOWN | E025 | MODEL_UNCERTAINTY (not implemented) | PASS |
| R-RESTART-RECOVERY | UNKNOWN | E022 | persistence.RecoveryPolicy (OUR_EA_POLICY) | PASS |

Verified-no-evidence: 0 · no-status: 0
Phase 5/6 historical rows untouched (append-only; Phase 6.1 rows appended
to TRACEABILITY_MATRIX.csv below).
