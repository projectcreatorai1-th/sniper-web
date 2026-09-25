# SNIPER Gateway Architecture

## Authority (LOCKED)
- SNIPER = Research / Analysis / Signal / Evidence Authority
- 1144 Trading Gateway = Transport / Event Bus / State Sync
- 1144 Trading OS = Control Plane / GUI / Monitoring
- OUR EA = Strategy / Risk / Execution Authority
- MT5 = Trading Terminal
- Broker = Execution Venue

## Data Flow
```
SNIPER Analyzer
  ↓ Signal (research output, never execution)
1144 Trading Gateway
  ↓ Event Bus
OUR EA
  ↓ Risk evaluation → Execution decision
MT5 → Broker
  ↓ Execution result
1144 Trading Gateway
  ↓ Event
SNIPER Analyzer (receives execution feedback for research)
```

## Components
- `core/gateway/contracts.py` — Signal/Event/Contract/Evidence schemas
- `core/gateway/client.py` — GatewayClient (connect, heartbeat, publish, subscribe, reconnect, reconciliation, audit)
- `core/gateway/signal_builder.py` — Build Signal + EvidencePackage from SNIPER analysis
- `web/backend/gateway_api.py` — REST endpoints `/api/gateway/*`
- `tests/gateway/test_gateway.py` — 29 tests covering all §28 categories

## Safety
- SNIPER NEVER sends orders to MT5
- Signals are research/strategy outputs with evidence provenance
- No MT5 import, no order_send, no live trading in gateway code
- LIVE remains LOCKED
- Transport uses LoopbackTransport for testing (clearly labelled TEST)

## Current Status
- IMPLEMENTED: Gateway Client (connect/heartbeat/signal/event/reconnect/audit)
- ENVIRONMENT-BLOCKED: Real gateway connection (no 1144 Gateway server running)
- E2E verified via LoopbackTransport simulation
