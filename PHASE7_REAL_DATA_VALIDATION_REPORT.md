# PHASE 7 — Real-Data Evidence Validation

2026-09-25T03:26:45 · dataset hash `994955EA1889409A3B71C15C…` · split
{'DEVELOPMENT': 486, 'VALIDATION': 163, 'OOS': 163} (chronological per account, OOS never tuned on)

## OOS results (final 20%, untouched)

- Lot floor ladder: **0 errors / 909 checks** (0.000%)
- Grid direction exceptions: 0/583 (0.0%) — within documented 0.18%
- Basket hypothesis violations on OOS: {"H_GROSS_1_00": 1.23, "H_PER_LOT_0_50": 0.0, "H_PER_LOT_0_85": 0.61, "H_GROSS_1_68": 96.32}

## Counter-hypothesis conclusion

H_GROSS_1_68 violates on 96.32% of
OOS baskets — rejection confirmed out-of-sample. The remaining compatible
set {H_GROSS_1_00, H_PER_LOT_0_50, H_PER_LOT_0_85} cannot be separated by close-side data:
**no promotion**. Grid trigger anchors remain mathematically
indistinguishable: **no promotion**.

## Evidence review decisions

- **R-LOT-FLOOR**: STAY_VERIFIED — OOS errors 0/909
- **R-GRID-DIRECTION**: STAY_VERIFIED — OOS exception rate 0.0% within documented 0.18%
- **R-BASKET-TRIGGER**: STAY_PARTIAL — OOS-compatible set ['H_GROSS_1_00', 'H_PER_LOT_0_50', 'H_PER_LOT_0_85'] — no single winner; promotion impossible without evaluation-instant data
- **R-ACCUM-1-68**: STAY_REJECTED — OOS violations 96.32%
- **R-PARTIAL-TRIGGER**: STAY_UNKNOWN — no new evidence class in existing close-side dataset
- **R-PARTIAL-VOLUME**: STAY_UNKNOWN — no new evidence class in existing close-side dataset
- **R-EMERGENCY**: STAY_UNKNOWN — no new evidence class in existing close-side dataset
- **R-RESTART-RECOVERY**: STAY_UNKNOWN — no new evidence class in existing close-side dataset
- **R-GRID-TRIGGER**: STAY_PARTIAL — anchor/level ambiguity unchanged
- **R-PARTIAL-LEVEL**: STAY_PARTIAL — anchor/level ambiguity unchanged

## Status

`PASS-WITH-UNKNOWN (no promotions; consistency confirmed on OOS; 4 UNKNOWN + 3 PARTIAL preserved)` — promotions: 0
(tick-level data remains the unblocking requirement; nothing was
fabricated; §22 status quo preserved exactly)
