# INCIDENT MANAGEMENT (§33)

Lifecycle: DETECT -> CLASSIFY -> CONTAIN -> RECOVER -> ROOT CAUSE ->
CORRECTIVE ACTION -> REGRESSION -> CLOSE

| Severity | Examples | Containment |
|---|---|---|
| SEV-1 | duplicate order, uncontrolled exposure, LIVE bypass, state corruption | GLOBAL_EMERGENCY_KILL (multi-layer board), halt, preserve state |
| SEV-2 | reconciliation unresolved, repeated order failure storm | ORDER_KILL + consecutive-failure block, SAFE_STOP |
| SEV-3 | data-quality storm, latency breach | volatility/stale guards, observation mode |
| SEV-4 | cosmetic/log issues | ticket, no trading impact |

Detection surfaces: risk guard violations (RISK_BLOCK events), kill
board, reconciliation (RECONCILIATION_FAILED blocks new orders),
surveillance findings (Phase 9), monitoring heartbeat.
Every incident must end with a regression test before CLOSE.
