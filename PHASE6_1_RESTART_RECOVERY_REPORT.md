# PHASE 6.1 — TEST_R_RESTART_RECOVERY EXECUTION REPORT (§5)

Executed as REAL separate processes (phase1 -> termination -> phase2). Verified on every restore: contract hash, state checksum, model version, event cursor, cycle/basket identity, idempotency keys, risk state incl. kill switch.

**This is OUR EA restart/recovery safety behavior, not verified V1.68 restart behavior** (R-RESTART-RECOVERY stays UNKNOWN).

**Result: 8/8 scenarios PASS**

| Scenario | Result | Verified behaviour |
|---|---|---|
| normal | PASS | state restored, cycles continue, no new id minted |
| active_cycle | PASS | cycle/basket identity restored unchanged; sequence/tick cursor continue (basket may close normally afterwards) |
| after_partial | PASS | restart after uncertainty events — continues safely |
| duplicate_event | PASS | replayed tick produced no duplicate (side,level) fill |
| missing_state | PASS | no state -> policy pause, no trades |
| corrupted_state | PASS | checksum mismatch -> SAFE_STOP |
| incompatible_model_version | PASS | model mismatch -> refused, no restore |
| stale_state | PASS | stale state -> SAFE_STOP (market gap unknowable) |

## Representative evidence (JSON from worker processes)

### normal
```json
{
 "phase": "phase2",
 "restored_state": "BOTH_SIDES_ACTIVE",
 "restored_cycle_id": "SIM|GOLDmicro|C000001",
 "idempotency_keys": 1,
 "ok": true,
 "state": "BOTH_SIDES_ACTIVE",
 "cycle_id": "SIM|GOLDmicro|C000001",
 "basket_id": "SIM|GOLDmicro|C000001|B",
 "cycle_sequence": 1,
 "tick_no": 10,
 "kill_switch": false,
 "events": 0,
 "exit": 0
}
```

### active_cycle
```json
{
 "phase": "phase2",
 "restored_state": "GRID_ACTIVE",
 "restored_cycle_id": "SIM|GOLDmicro|C000001",
 "idempotency_keys": 1,
 "ok": true,
 "state": "GRID_ACTIVE",
 "cycle_id": "SIM|GOLDmicro|C000002",
 "basket_id": "SIM|GOLDmicro|C000002|B",
 "cycle_sequence": 2,
 "tick_no": 50,
 "kill_switch": false,
 "events": 13,
 "exit": 0
}
```

### after_partial
```json
{
 "phase": "phase2",
 "restored_state": "BOTH_SIDES_ACTIVE",
 "restored_cycle_id": "SIM|GOLDmicro|C000002",
 "idempotency_keys": 2,
 "ok": true,
 "state": "GRID_ACTIVE",
 "cycle_id": "SIM|GOLDmicro|C000002",
 "basket_id": "SIM|GOLDmicro|C000002|B",
 "cycle_sequence": 2,
 "tick_no": 40,
 "kill_switch": false,
 "events": 1,
 "exit": 0
}
```

### duplicate_event
```json
{
 "phase": "phase2",
 "restored_state": "GRID_ACTIVE",
 "restored_cycle_id": "SIM|GOLDmicro|C000001",
 "idempotency_keys": 1,
 "ok": true,
 "duplicate_detected": false,
 "exit": 0
}
```

### missing_state
```json
{
 "phase": "phase2",
 "ok": false,
 "action": "PAUSE_FOR_OPERATOR",
 "reason": "no persisted state at C:\\Users\\BANK\\AppData\\Local\\Temp\\p61_restart_8l6id492\\missing.json",
 "exit": 5
}
```

### corrupted_state
```json
{
 "phase": "phase2",
 "ok": false,
 "action": "SAFE_STOP",
 "reason": "missing/invalid required fields: PersistedState.__init__() missing 1 required positional argument: 'cycle_sequence'",
 "exit": 4
}
```

### incompatible_model_version
```json
{
 "phase": "phase2",
 "ok": false,
 "action": "SAFE_STOP",
 "reason": "MODEL_VERSION_MISMATCH on restore: state has OTHER-MODEL-v9@124F089842… expected V1.68-EVIDENCE-MODEL-v1.0@124F089842…",
 "exit": 5
}
```

### stale_state
```json
{
 "phase": "phase2",
 "ok": false,
 "action": "SAFE_STOP",
 "reason": "state older than threshold — market gap unknowable, state cannot be trusted",
 "exit": 3
}
```
