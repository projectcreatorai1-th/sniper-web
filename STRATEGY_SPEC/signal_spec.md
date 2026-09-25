# Signal Generation Specification

*SNIPER = Signal Authority. Gateway = Transport. EA = Execution Authority.*

## Authority Split

```
SNIPER CashFlow Analyzer
  = Strategy / Research / Signal / Evidence Authority
  → สร้าง Signal จาก analysis/replay/backtest evidence

1144 Trading Gateway
  = Transport Authority
  → ส่ง Signal ไปยัง EA (ไม่ตัดสินใจ)

OUR EA
  = Strategy Enforcement + Risk + Execution Authority
  → รับ Signal → Risk check → Execute (ผ่าน MT5)
```

## Signal Generation Logic

### When SNIPER generates signals

SNIPER generates signals when the **runtime strategy core** (OUR EA simulation) produces a decision:

```
Tick arrives → Strategy Core evaluates → Decision made
  → if decision is actionable (entry/grid_add/close)
    → Signal created with full provenance
    → Published via Gateway Client
```

### Signal types and conditions

| Signal Type | Trigger Condition | Direction | Status |
|---|---|---|---|
| ENTRY | Cycle start (flat → both-sides) | BUY + SELL | VERIFIED (E015) |
| ENTRY (grid add) | Price crosses anchor ± step | BUY (down) or SELL (up) | PARTIAL (anchor E026) |
| EXIT (basket close) | Basket profit >= hypothesis threshold | Close all | PARTIAL (hypothesis E016/E027) |
| ALERT | Risk limit approaching | Context-dependent | CONFIGURED |
| ANALYSIS | Post-trade analysis complete | NEUTRAL | CONFIGURED |

### Signal schema

```json
{
  "signal_id": "SIG-XXXXXXXXXXXX",
  "strategy_id": "SNIPER-V168",
  "strategy_version": "1.0",
  "symbol": "GOLDmicro",
  "timeframe": "M15",
  "direction": "BUY|SELL|NEUTRAL",
  "signal_type": "ENTRY|EXIT|FILTER|ALERT|ANALYSIS",
  "entry_reference": 4400.0,
  "stop_reference": 4390.0,
  "target_reference": 4420.0,
  "confidence": 0.85,
  "created_at": "2026-09-25T09:00:00.000Z",
  "expires_at": "2026-09-25T10:00:00.000Z",
  "analysis_version": "V1.68-EVIDENCE-MODEL-v1.0",
  "dataset_version": "replay_dataset_v1",
  "backtest_id": "",
  "evidence_id": "E012",
  "evidence_hash": "…",
  "correlation_id": "COR-XXXXXXXXXXXX",
  "schema_version": "1.0.0"
}
```

### Evidence provenance

ทุก Signal ต้องมี:
- `analysis_version` = Evidence Model version
- `evidence_id` = อ้างอิง rule ที่ทำให้เกิด decision
- `evidence_hash` = hash ของ evidence package
- `correlation_id` = สำหรับ trace จาก analysis → signal → gateway → EA → execution

## Signal Validation (before publish)

```
1. Schema validation (required fields, types)
2. Symbol validation (in allowed_symbols)
3. Direction validation (BUY/SELL/NEUTRAL)
4. Signal type validation (ENTRY/EXIT/FILTER/ALERT/ANALYSIS)
5. Confidence validation (0.0 <= confidence <= 1.0)
6. Expiry validation (not expired)
7. Correlation ID validation (present)
8. Duplicate signal check (signal_id unique)
9. Evidence reference validation (evidence_id exists)
```

## Signal Lifecycle

```
SNIPER (owns):
  CREATED → VALIDATING → VALIDATED → PUBLISHED

GATEWAY (transport):
  RECEIVED_BY_GATEWAY

EA (owns):
  ACCEPTED_BY_EA / REJECTED_BY_RISK
  → EXECUTION_REQUESTED → EXECUTED

SNIPER (receives):
  ← Execution result event
  ← Updates signal lifecycle trace
```

## Signal Gateway Contract

SNIPER publishes signals via `core/gateway/client.py::GatewayClient.publish_signal()`:
- Transport: pluggable (WebSocket when gateway exists; LoopbackTransport for testing)
- Contract version: checked at handshake (must match 1.x)
- Idempotency: duplicate signal_id blocked
- Evidence package attached to every signal

## Important Notes

1. **Signal ≠ Order**: Signals are research outputs. They do NOT contain order parameters (volume, order_type, magic).
2. **UNKNOWN behavior**: If a decision depends on UNKNOWN rules (partial trigger, emergency), the signal includes `MODEL_UNCERTAINTY` metadata instead of guessing.
3. **Historical signal generation rules**: V1.68 does NOT have a documented signal generation system separate from its tick-driven grid execution. Our signal spec derives from the behavioral model, not from a separate V1.68 signal engine.
