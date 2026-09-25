# Edge Case Matrix

*ทุกกรณี — Input → Detection → Decision → Action → Expected Result*

## Market Data Edge Cases

| # | Case | Input | Detection | Decision | Action | State | Status |
|---|---|---|---|---|---|---|---|
| EC-001 | No tick | No market data received | heartbeat timeout | DEGRADED | Stop new entries | DEGRADED | CONFIGURED |
| EC-002 | Delayed tick | Tick arrives late (>threshold) | timestamp check | Skip stale tick | Log + skip | unchanged | CONFIGURED |
| EC-003 | Invalid price | price <= 0 or NaN | price validation | Skip tick | ERROR event + skip | unchanged | CONFIGURED |
| EC-004 | Abnormal spread | spread > max_spread_usd | risk guard | Block new entries | RISK_BLOCK event | unchanged | CONFIGURED |
| EC-005 | Price jump | abs(move) > max_tick_volatility | tick volatility guard | Block new entries | RISK_BLOCK event | unchanged | CONFIGURED |
| EC-006 | Duplicate tick | Same tick_id or price | idempotency check | Skip duplicate | Log + skip | unchanged | CONFIGURED |
| EC-007 | Out-of-order tick | timestamp < last_timestamp | monotonicity check | Skip late tick | RISK_BLOCK + skip | unchanged | CONFIGURED |

## Strategy Edge Cases

| # | Case | Input | Detection | Decision | Action | State | Status |
|---|---|---|---|---|---|---|---|
| EC-010 | Flat, no positions | basket empty | state check | Open new cycle | BUY+SELL base_lot | WAITING → BOTH_SIDES | VERIFIED |
| EC-011 | BUY side only | only BUY open | state check | Continue grid | Grid add check (BUY) | unchanged | VERIFIED |
| EC-012 | SELL side only | only SELL open | state check | Continue grid | Grid add check (SELL) | unchanged | VERIFIED |
| EC-013 | Both sides open | BUY + SELL open | state check | Grid + basket check | Per-side evaluation | GRID_ACTIVE | VERIFIED |
| EC-014 | Grid trigger hit | price crosses anchor-step | grid engine | Risk check → open | GRID_ADD event | GRID_ACTIVE | PARTIAL (anchor) |
| EC-015 | Basket trigger hit | profit >= threshold | basket engine | Close all | BASKET_CLOSE events | → CLOSED | PARTIAL (hypothesis) |
| EC-016 | Partial trigger | partial enabled + unknown condition | partial engine | MODEL_UNCERTAINTY | Skip + log | UNCERTAIN | UNKNOWN |
| EC-017 | All entries rejected | broker rejects all opens | adapter response | Abandon cycle | CYCLE_END (rejected) | → WAITING | CONFIGURED |

## Risk Edge Cases

| # | Case | Input | Detection | Decision | Action | State | Status |
|---|---|---|---|---|---|---|---|
| EC-020 | Max lot exceeded | total_lot > max_total_lot | risk guard | Block | RISK_BLOCK | unchanged | CONFIGURED |
| EC-021 | Max positions | open > max_positions | risk guard | Block | RISK_BLOCK | unchanged | CONFIGURED |
| EC-022 | Max grid depth | depth > max_grid_depth | risk guard | Block | RISK_BLOCK | unchanged | CONFIGURED |
| EC-023 | Max loss | floating < -max_loss | emergency policy | SAFE_STOP | Close assessment | SAFE_STOP | CONFIGURED |
| EC-024 | Kill switch engaged | kill_board.any_engaged | kill board | Block all | SAFE_STOP | SAFE_STOP | CONFIGURED |
| EC-025 | Consecutive failures | failures >= threshold | risk guard | Block | RISK_BLOCK | unchanged | CONFIGURED |

## Runtime Edge Cases

| # | Case | Input | Detection | Decision | Action | State | Status |
|---|---|---|---|---|---|---|---|
| EC-030 | Process restart | state file exists + checksum valid | StateStore.load | Restore | Continue from saved state | restored | CONFIGURED |
| EC-031 | Corrupted state | checksum mismatch | StateCorruptionError | SAFE_STOP | Refuse restore | SAFE_STOP | CONFIGURED |
| EC-032 | Missing state | no state file | PersistenceError | PAUSE | Operator decision | SAFE_STOP | CONFIGURED |
| EC-033 | Incompatible model | model_version mismatch | version check | Refuse | ERROR + stop | SAFE_STOP | CONFIGURED |
| EC-034 | Stale state | age > threshold (24h) | RecoveryPolicy | SAFE_STOP | Refuse (gap unknowable) | SAFE_STOP | CONFIGURED |
| EC-035 | Gateway unavailable | connection lost | transport check | Continue local | Log + retry | unchanged | CONFIGURED |
| EC-036 | Duplicate event | event_id already seen | idempotency ledger | Ignore | Log DUPLICATE_EVENT | unchanged | CONFIGURED |

## Execution Edge Cases

| # | Case | Input | Detection | Decision | Action | State | Status |
|---|---|---|---|---|---|---|---|
| EC-040 | Order rejected | broker rejects | adapter response | Log + risk count | ORDER_REJECTED | unchanged | CONFIGURED |
| EC-041 | Partial fill | filled_lot < requested_lot | adapter response | Use filled_lot | Position with actual lot | unchanged | CONFIGURED |
| EC-042 | Order timeout | no response in timeout | adapter timeout | Log + safe path | ERROR + assess | UNCERTAIN | CONFIGURED |
| EC-043 | Close failure | close order rejected/timeout | adapter response | MODEL_UNCERTAINTY | Log + retry assessment | UNCERTAIN | CONFIGURED |
| EC-044 | Adapter exception | adapter raises | try/except | SAFE_STOP | ERROR event | SAFE_STOP | CONFIGURED |

## Data Persistence Edge Cases

| # | Case | Input | Detection | Decision | Action | State | Status |
|---|---|---|---|---|---|---|---|
| EC-050 | Persistence failure | write error | StateStore.save | Log + continue | ERROR event | unchanged | CONFIGURED |
| EC-051 | Disk full | write fails (ENOSPC) | OSError | Log + SAFE_STOP | Stop safely | SAFE_STOP | CONFIGURED |
| EC-052 | State file tampered | external modification | checksum verify | StateCorruptionError | SAFE_STOP | SAFE_STOP | CONFIGURED |
