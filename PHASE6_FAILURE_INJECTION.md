# Phase 6 — Failure injection (§33)

Injected: order reject, timeout, duplicate tick, basket-close failure,
process restart (state restore), state corruption. Requirements met:
fail safely (SAFE_STOP/UNCERTAIN paths), no duplicate execution
(idempotency ledger + per-level grid gating), state consistent,
root cause logged. Two real defects found and fixed during testing:
rejected-entry state recovery and close-failure realized accounting.
