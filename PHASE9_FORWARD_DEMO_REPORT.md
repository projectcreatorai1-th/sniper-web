# PHASE 9 — Extended Demo / Forward Test (§29-§30)

2026-09-25T03:28:38

## Extended forward demo: **ENVIRONMENT-LIMITED**

no broker connection/credentials in this environment — extended run is **not** claimed
completed. Harness, mode controller and monitoring collection are ready
for the real demo environment.

## Soak-smoke executed locally (60 s, labelled, synthetic feed)

```json
{
 "uptime_s": 60.0,
 "ticks": 10866,
 "heartbeats": 10866,
 "errors": 0,
 "cycles": 522,
 "events": 4993,
 "session_hash": "0505AB50395CD707FFD96EA144D33313E376B58E6CB34941697CB31CEE9C01C9",
 "mode": "OBSERVATION",
 "ticks_per_sec": 181.1
}
```

## Post-trade surveillance findings (§30)

```json
{
 "order_burst": false,
 "entries": 1716,
 "closes": 1713,
 "repeated_rejections": false,
 "unexpected_exposure_lot": 0.31,
 "max_single_lot_seen": 0.13,
 "position_accumulation_flag": false,
 "strategy_drift": false,
 "notes": "model_version uniform: True"
}
```

Surveillance verdict: NO ANOMALY

## Collected per §29
uptime · ticks · signals/decisions (events) · orders (fills) · positions ·
P/L (per basket) · drawdown guards · spread · errors · reconnects (0 in
smoke) · restarts (0 in smoke) · reconciliation (smoke: N/A single process)
· kill state (not engaged)
