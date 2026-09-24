# PHASE 6 — Behavioral Model binding

Model version: V1.68-EVIDENCE-MODEL-v1.0 (hash 124F08984284E880F268C37E…)

VERIFIED (implemented as V1.68 behavior):
1. Base Lot 0.10 (R-BASE-LOT)
2. Lot floor ladder (R-LOT-FLOOR) — equivalence to SSOT via tests
3. Grid spacing ~5 USD with observed distribution + tolerance (R-GRID-SPACING)
4. Grid direction BUY down / SELL up (R-GRID-DIRECTION)
5. Both-sides initial exposure, 99.4% observed, exceptions kept (R-BOTH-SIDES)
6. Contract size GOLDmicro = 1.0 (R-CONTRACT-SIZE)
7. Partial close EXISTS (R-PARTIAL-EXISTS) — no trigger/volume guessing
8. Normal resume <=2s (R-NORMAL-RESUME) — restart recovery excluded

PARTIAL (hypothesis-configurable, never declared winner):
- Grid Trigger (H_PREV_ENTRY / H_EXTREME, no winner)
- Basket Trigger (GROSS>=1.00 / lots×0.50 / lots×0.85)
- Partial Level (FIFO-feasible 390 / ambiguous 102)

UNKNOWN (MODEL_UNCERTAINTY, safe OUR-EA policy instead):
- Partial Trigger
- Partial Volume Rule
- Emergency Mechanism
- Restart Recovery

REJECTED: AccumulatorTargetUSD=1.68 per basket (E027, 90.70% violations)
— not implemented, not selectable in config validation.
