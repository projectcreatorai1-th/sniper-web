# PHASE 6 — Architecture (§7)

```
V1.68 Evidence (frozen, read-only)
  ↓ V1.68-EVIDENCE-MODEL-v1.0.json (hash-verified contract)
Frozen Behavioral Model -> RuleRegistry (16 rules, statuses bound)
  ↓
OUR EA Strategy Core (core/our_ea/strategy.py)
  lot/grid/basket/partial engines (hypothesis-configurable)
  state machine (explicit transitions only)
  immutable events + idempotency + persistence
  ↓
Risk Guard (OUR_EA_POLICY — separate from V1.68 model)
  ↓
Execution Intent -> ExecutionAdapter
  Simulation / Paper / Demo      [LIVE: HARD LOCKED]
```

Boundary compliance: OUR EA imports no Analyzer runtime; the only
Analyzer artifacts consumed are the frozen model JSON and the immutable
replay dataset export (both hash-verified). Build commit e5159fc27f.
