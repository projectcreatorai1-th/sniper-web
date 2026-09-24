# PHASE 6 — State Machine (§14)

17 states; every transition declared in TRANSITIONS; undeclared raises
InvalidTransition (no implicit transitions). Safety events (DISCONNECT,
SAFE_STOP) valid from any active state; recovery paths
(ALL_ENTRIES_FAILED, UNCERTAIN->BASKET_INTENT/GRID_ADD) declared after
failure-injection testing. Each transition records state_before/event/
condition/state_after/reason/rule_id/model_version/trace_id.
