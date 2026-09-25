# Signal Lifecycle

CREATED → VALIDATING → VALIDATED → PUBLISHED → RECEIVED_BY_GATEWAY
→ ACCEPTED_BY_EA / REJECTED_BY_RISK → EXECUTION_REQUESTED → EXECUTED
→ EXPIRED / CANCELLED

SNIPER owns: CREATED through PUBLISHED
Gateway owns: RECEIVED_BY_GATEWAY notification
EA owns: ACCEPTED/REJECTED, EXECUTION decisions
SNIPER records: all lifecycle transitions from gateway events

Signal contract: signal_id, strategy_id, symbol, direction (BUY/SELL/NEUTRAL),
signal_type (ENTRY/EXIT/FILTER/ALERT/ANALYSIS), confidence [0-1],
entry/stop/target references, created_at, expires_at, correlation_id,
evidence_id + evidence_hash (provenance), analysis_version, dataset_version.
