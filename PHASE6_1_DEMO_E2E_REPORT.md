# PHASE 6.1 — Demo E2E Report (§9-§10, §17)

Controlled environment · no real money · no live account · 2026-09-25T03:01:53

**Result: PASS (14/14 steps)**

| # | Step | Result | Detail |
|---|---|---|---|
| 1 startup | PASS |  |
| 2 configuration (demo safety limits) | PASS |  |
| 3 model verification (contract hash) | PASS | 124F08984284E880… |
| 4 state initialization | PASS | WAITING_FOR_ENTRY |
| 5 signal/event processing | PASS |  |
| 6 strategy decisions (entries/grid/closes) | PASS | cycles=14 |
| 7 risk guard evaluated | PASS | risk_blocks=0 |
| 8 execution adapter (demo fills) | PASS |  |
| 9 demo-broker responses simulated | PASS |  |
| 10 persistence (checksum verified) | PASS |  |
| 11 audit trail | PASS | 133 events; config_version on every event: True |
| 12 restart (separate process, checksum+model verified) | PASS |  |
| 13 shutdown (SAFE_STOP) | PASS |  |
| live lock active during demo | PASS |  |

## Demo safety limits (ALL OUR_EA_POLICY — not V1.68 behavior)

```json
{
 "max_lot_per_order": 0.5,
 "max_open_orders": 12,
 "max_total_exposure_lot": 2.0,
 "max_basket_depth": 12,
 "max_drawdown_pct": 20.0,
 "daily_loss_limit_usd": 30.0,
 "session_loss_limit_usd": 30.0,
 "max_consecutive_failures": 3,
 "disconnect_timeout_s": 30.0,
 "stale_data_timeout_s": 10.0,
 "order_timeout_s": 5.0,
 "duplicate_event_protection": true,
 "kill_switch": true,
 "SOURCE": "OUR_EA_POLICY"
}
```

## Live lock verification in demo context
- resolve_mode("LIVE") -> LiveLockError (REFUSED)
- config execution_mode="LIVE" -> ConfigInvalid (REFUSED)
- LiveAdapter() instantiation -> LiveLockError (REFUSED)
