# Strategy Decision Tree

*Implementation-independent flow — ทุก branch ระบุสถานะ evidence ตามจริง*

## Overview

```
Market Data (tick)
        │
        ▼
┌───────────────────┐
│ Data Valid?       │ CONFIGURED (invalid → skip + log)
└───────┬───────┬───┘
      YES      NO → skip tick
        │
        ▼
┌───────────────────┐
│ Kill Switch?     │ CONFIGURED (OUR_EA_POLICY)
└───────┬───────┬───┘
      NO       YES → SAFE_STOP
        │
        ▼
┌───────────────────┐
│ Current State?   │ VERIFIED (17-state machine)
└───────┬───────┬───┘
        │
   ┌────┴────────────────────┐
   │                         │
FLAT                    POSITIONS OPEN
   │                         │
   ▼                         ▼
┌──────────────────┐  ┌──────────────────────┐
│ Open New Cycle   │  │ Evaluate Grid        │
│ (entry model)    │  │ (grid model)         │
└──────────────────┘  └──────────┬───────────┘
                                 │
                          ┌──────┴──────┐
                          │             │
                    Trigger hit?   No trigger
                          │             │
                          ▼             ▼
                  ┌──────────────┐  ┌──────────────┐
                  │ Risk Check   │  │ Basket Close │
                  │ (risk guard) │  │ Check        │
                  └──────┬───────┘  └──────┬───────┘
                         │                  │
                   ┌─────┴─────┐      ┌────┴────┐
                 PASS       FAIL   Trigger  No trigger
                   │           │      hit?
                   ▼           ▼      │
             ┌──────────┐  ┌──────┐   │
             │ GRID_ADD │  │SKIP +│   │
             │ (open    │  │RISK_ │   │
             │ position)│  │BLOCK │   │
             └──────────┘  └──────┘   │
                   │                  ▼
                   │         ┌────────────────┐
                   │         │Close All       │
                   │         │Positions       │
                   │         │(basket close)  │
                   │         └────────┬───────┘
                   │                  │
                   ▼                  ▼
             ┌────────────────────────────┐
             │ State Transition +         │
             │ Event + Audit              │
             └────────────────────────────┘
```

## Entry Model [VERIFIED — E015]

```
FLAT state
  ↓
Open BUY base_lot + SELL base_lot simultaneously
  ↓
Transition: WAITING_FOR_ENTRY → BOTH_SIDES_ACTIVE
```

**Evidence**: 99.4% of cycles start with both sides. 72% open in the same second.

**Re-entry [VERIFIED — E018]**: After basket close → next cycle opens ≤2s later (99.75%).

**Initial entry timing**: Not specified separately from cycle start condition (flat = start).
**Restart entry**: UNKNOWN (E022, single LOW-confidence event).

## Grid Add Decision [VERIFIED direction + spacing — E013/E014; PARTIAL anchor — E026]

```
For each side (BUY, SELL) with open positions:
  anchor = <PARTIAL: H_PREV_ENTRY or H_EXTREME — indistinguishable>
  trigger_price = anchor - GridStepUSD   (BUY)
                  anchor + GridStepUSD   (SELL)
  if market_price <= trigger_price (BUY) or >= trigger_price (SELL):
    → RISK CHECK
    → if pass: open new position at next ladder lot
    → lot = Lot(next_level) [VERIFIED — E012/E028]
```

**Direction**: BUY adds LOWER (100.00%), SELL adds HIGHER (99.82%).
**Spacing**: ~5 USD (median 5.09, P5 4.72, P95 5.98).
**Anchor**: PARTIAL — two hypotheses mathematically equivalent on averaging-down ladders.

## Risk Check [CONFIGURED — OUR_EA_POLICY, NOT historical V1.68]

```
Check all limits:
  max_positions → block if exceeded
  max_grid_depth → block if exceeded
  max_total_lot → block if exceeded
  max_spread_usd → block if exceeded
  max_loss_usd → SAFE_STOP if exceeded
  max_drawdown_pct → SAFE_STOP if exceeded
  consecutive_failures → block if >= threshold
  tick_volatility → block if > threshold
  kill_switch → block if engaged
```

**Important**: These are OUR EA safety policy, NOT verified V1.68 behavior.

## Basket Close Check [PARTIAL — E016/E027]

```
total_profit = sum(floating + realized) for all open positions in basket
threshold = <PARTIAL: configurable hypothesis>
  H_GROSS_1_00: threshold = $1.00
  H_PER_LOT_0_50: threshold = total_lots × 0.50
  H_PER_LOT_0_85: threshold = total_lots × 0.85

if total_profit >= threshold:
  → Close ALL positions in basket
  → Transition: → BASKET_CLOSE_PENDING → CLOSING → CLOSED
  → Next cycle opens ≤2s later [VERIFIED — E018]
```

**REJECTED**: AccumulatorTargetUSD = 1.68 (96.32% violations on OOS).

## Partial Close [PARTIAL existence — E025; UNKNOWN trigger/volume]

```
IF partial_close enabled (default: DISABLED):
  WHEN trigger condition met:
    → UNKNOWN (no evidence for trigger condition)
    → MODEL_UNCERTAINTY emitted
    → Safe skip (do not guess)
```

**Known**: 492 deal-level partial closes exist in evidence.
**Unknown**: What triggers them, how much volume closes.
**FIFO level rule**: PARTIAL (390 FIFO-feasible, 102 ambiguous).

## Emergency [UNKNOWN — E021]

```
Emergency mechanism:
  → UNKNOWN (0 events observed in 862 production baskets)
  → Deep grid (32 levels, 20.07 lots) survived to +21.80 profit
  → V1.68 emergency threshold NOT identified

OUR_EA_POLICY fallback:
  max_loss → SAFE_STOP
  max_drawdown → SAFE_STOP
  max_grid_depth → block new entries
  kill_switch → SAFE_STOP
```

## Lot Assignment [VERIFIED — E012/E028]

```
Lot(n) = floor(0.10 × 1.10^(n-1) / 0.01) × 0.01

Level 1: 0.10
Level 2: 0.11
Level 3: 0.12
Level 4: 0.13
Level 5: 0.14  (NOT 0.15 — floor, not round)
Level 7: 0.17  (NOT 0.18)
Level 10: 0.23 (NOT 0.24)
...
Level 32: 1.91 (max observed)

Beyond L32: EXTRAPOLATED (not observed)
```
