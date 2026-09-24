# PHASE 6 — Historical Replay (§29-§31)

Dataset: data/our_ea/replay_dataset_v1.json (812 HIGH-confidence cycles,
immutable export, hash-verified). Comparisons: 16992
- MATCH 13177 · MISMATCH 27 ·
  UNKNOWN 812 · NOT_COMPARABLE 2976
- match rate 77.55%

Mismatch analysis (every mismatch has expected/actual/event/rule/
evidence/difference):
- R-BASKET-TRIGGER 22: hypothesis violations = 2.7% (documented 3.14%, E027)
- R-GRID-DIRECTION 3: 0.18% = exactly the documented exception rate (E014)
- R-GRID-SPACING 2: same fills as the direction exceptions

VERIFIED rules: lot floor / base lot / both-sides = 0 mismatches;
direction within documented exception rate. Fill scatter beyond the
band with correct direction is classified NOT_COMPARABLE (trigger
semantics PARTIAL — E026; no tick data to attribute execution scatter).

Determinism: run_id R-B09ADD72981E, result_hash 9AECCE74198E6EF545CC2E7B…
(same model+dataset+config -> identical hash; tested).
Normal resume: 810/
812 <=2s (99.75%).
