# STRESS + CAPACITY REPORT (§27-§28)

2026-09-25T03:31:14 — all numbers measured on this machine; envelope derived ONLY from
measurements (no invented benchmarks).

## Stress scenarios (each: DETECT -> CONTROL -> RECOVER -> VERIFY)

```json
{
 "HIGH_VOLATILITY": {
  "events": 591,
  "ticks": 2000,
  "cycles": 50,
  "safe_stops": 1,
  "risk_blocks": 0,
  "wall_s": 0.038,
  "final_state": "SAFE_STOP"
 },
 "GAP": {
  "events": 4,
  "ticks": 2000,
  "cycles": 1,
  "safe_stops": 0,
  "risk_blocks": 0,
  "wall_s": 0.029,
  "final_state": "GRID_ACTIVE"
 },
 "FAST_MOVE": {
  "events": 6,
  "ticks": 2000,
  "cycles": 1,
  "safe_stops": 0,
  "risk_blocks": 0,
  "wall_s": 0.034,
  "final_state": "GRID_ACTIVE"
 },
 "SPREAD_WIDENING": {
  "events": 15,
  "ticks": 2000,
  "cycles": 1,
  "safe_stops": 1,
  "risk_blocks": 1,
  "wall_s": 0.012,
  "final_state": "SAFE_STOP"
 },
 "TREND_DOWN": {
  "events": 15,
  "ticks": 2000,
  "cycles": 1,
  "safe_stops": 1,
  "risk_blocks": 1,
  "wall_s": 0.013,
  "final_state": "SAFE_STOP"
 },
 "DEEP_GRID": {
  "events": 15,
  "ticks": 2000,
  "cycles": 1,
  "safe_stops": 1,
  "risk_blocks": 1,
  "wall_s": 0.012,
  "final_state": "SAFE_STOP"
 }
}
```

Every scenario ends in a safe state (WAITING/GRID/SAFE_STOP/UNCERTAIN)
— no crash, no unsafe continuation.

## Capacity measurements

```json
{
 "ticks_per_sec": 45785.0,
 "events_per_sec": 21489.0,
 "python": "3.12.10",
 "event_emit_per_sec": 299221.0
}
```

## Performance envelope (from measured data)

```json
{
 "NORMAL": ">= 22892 ticks/s",
 "WARNING": "11446-22892 ticks/s",
 "CRITICAL": "< 11446 ticks/s",
 "SAFE-DEGRADE": "risk guard blocks entries; SAFE_STOP on policy breach (already implemented)"
}
```
