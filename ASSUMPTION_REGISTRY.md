# ASSUMPTION REGISTRY — SNIPER CashFlow V1.68

> 🤖 สร้างอัตโนมัติจาก Core source of truth (`python tools/generate_registry_docs.py`) — ห้ามแก้ไขมือเปลี่ยน แก้ที่ core แล้วรันใหม่เสมอ


ทั้งหมด **39 รายการ** — MODEL_ASSUMPTION: 17 · UNKNOWN: 16 · VERIFIED_FROM_DOCUMENTATION: 6

สถานะ: `VERIFIED_FROM_DOCUMENTATION` (ระบุในเอกสารผู้ขาย) · `OBSERVED_FROM_TESTING` (ยืนยันจาก MT5 จริง) · `MODEL_ASSUMPTION` (สมมติฐานโมเดล) · `UNKNOWN` (ไม่มีข้อมูล — ไม่เดา)

| ID | หมวด | สถานะ | ความมั่นใจ | หัวข้อ | โมดูลที่เกี่ยวข้อง | แหล่งอ้างอิง |
|---|---|---|---|---|---|---|
| `BASKET_CLOSE_DOC_001` | — | `VERIFIED_FROM_DOCUMENTATION` | — | All orders close when total net basket profit reaches BasketCloseAllUSD | — | Manual p.4 sections 8-9. |
| `EMERGENCY_DOC_001` | — | `VERIFIED_FROM_DOCUMENTATION` | — | Emergency engages when price runs EmergencyDistanceFromCycleUSD beyond the trading frame | — | — |
| `GRID_DISTANCE_DOC_001` | — | `VERIFIED_FROM_DOCUMENTATION` | — | GridStepUSD is a price-distance between grid orders | — | Manual p.2 section 4; Full Report section 4 param #4. |
| `PARTIAL_ONCE_DOC_001` | — | `VERIFIED_FROM_DOCUMENTATION` | — | At most one partial close per cycle when ProfitPartialOnlyOnce=true | — | — |
| `THAI_TIME_DOC_001` | — | `VERIFIED_FROM_DOCUMENTATION` | — | All time parameters use Thai time (ICT, UTC+7) | — | — |
| `USEMARTINGALE_NAMING_NOTE_001` | — | `VERIFIED_FROM_DOCUMENTATION` | — | UseMartingale (infographic) == UsePositionSizeOptimization (PDF manual) | — | — |
| `BASKET_SCOPE_ASSUMPTION_001` | — | `MODEL_ASSUMPTION` | — | Basket P/L scope = combined (both sides) by default | — | — |
| `BOTH_SIDES_OPEN_AT_START_ASSUMPTION_001` | — | `MODEL_ASSUMPTION` | — | With UseGridBuy & UseGridSell both true, level-1 orders open on both sides at cycle start | — | — |
| `CONTRACT_SIZE_ASSUMPTION_001` | Symbol specification | `MODEL_ASSUMPTION` | MEDIUM | Contract size is configurable per symbol (XAUUSD=100 modeled) | core/symbol_profile.py | See XAUUSD_CONTRACT_ASSUMPTION_001. |
| `CYCLE_END_RULE_ASSUMPTION_001` | Lifecycle | `MODEL_ASSUMPTION` | MEDIUM | Cycle ends at the configured terminal event (basket/emergency/time stop) | core/cycle.py | — |
| `CYCLE_START_RULE_ASSUMPTION_001` | Lifecycle | `MODEL_ASSUMPTION` | MEDIUM | Cycle begins at the first position/open event of a burst | core/cycle.py | — |
| `EMERGENCY_FRAME_ASSUMPTION_001` | — | `MODEL_ASSUMPTION` | — | Trading frame modeled as the price range from cycle start price to the last grid order | — | — |
| `EXPOSURE_ASSUMPTION_001` | — | `MODEL_ASSUMPTION` | — | Exposure = notional value (lots x contract_size x price) | — | — |
| `GRID_DIRECTION_ASSUMPTION_001` | — | `MODEL_ASSUMPTION` | — | Grid adds only on ADVERSE move (averaging) | — | — |
| `GRID_TRIGGER_ASSUMPTION_001` | — | `MODEL_ASSUMPTION` | — | Next grid order triggers GridStepUSD away from the LAST order's price | — | — |
| `LOT_FORMULA_ASSUMPTION_001` | — | `MODEL_ASSUMPTION` | — | Lot progression = BaseLot x LotMultiplier^(level-1) | — | Manual sections 5-7 describe the behavior, not the formula. |
| `LOT_NORMALIZATION_ASSUMPTION_001` | — | `MODEL_ASSUMPTION` | — | Lots normalized (round) to broker lot step | — | — |
| `LOT_STEP_BOUNDARY_ASSUMPTION_001` | — | `MODEL_ASSUMPTION` | — | No automatic clamping to broker lot min/max inside the model | — | — |
| `MARGIN_ASSUMPTION_001` | — | `MODEL_ASSUMPTION` | — | Margin = lots x contract_size x price / leverage x margin_rate | — | — |
| `PARTIAL_CLOSE_ASSUMPTION_001` | — | `MODEL_ASSUMPTION` | — | Partial close reduces total volume by ProfitPartialPercent%, applied pro-rata | — | — |
| `PL_CONVERSION_ASSUMPTION_001` | — | `MODEL_ASSUMPTION` | — | P/L(USD) = price difference x lots x contract_size; no spread/commission/swap | — | — |
| `TRAILING_LOGIC_ASSUMPTION_001` | — | `MODEL_ASSUMPTION` | — | Trailing model: start at MainTrailStartProfitUSD, lock MainTrailLockUSD | — | — |
| `XAUUSD_CONTRACT_ASSUMPTION_001` | — | `MODEL_ASSUMPTION` | — | XAUUSD contract size = 100 oz (0.1 lot moves ~$10 per $1 price move) | — | Full Report section 6 calculation note. |
| `BID_ASK_ASSUMPTION_001` | Execution | `UNKNOWN` | LOW | The EA's use of bid/ask prices is unknown | core/calculations.py | — |
| `BROKER_MARGIN_ASSUMPTION_001` | Accounting | `UNKNOWN` | LOW | Real broker margin rules (hedged/tiered) are unknown | core/calculations.py | See MARGIN_ASSUMPTION_001. |
| `COMMISSION_ASSUMPTION_001` | Cost model | `UNKNOWN` | LOW | Commission model/value is unknown (model excludes commission) | core/calculations.py | — |
| `EA_BEHAVIOR_NOT_VERIFIED_001` | — | `UNKNOWN` | — | Internal EX5 logic cannot be verified without decompiling (prohibited) | — | — |
| `MAGIC_NUMBER_ASSUMPTION_001` | Execution | `UNKNOWN` | LOW | The EA's magic number / order identification scheme is unknown | — | — |
| `MAX_GRID_DEPTH_UNKNOWN_001` | — | `UNKNOWN` | — | Maximum number of grid levels inside the EX5 is not documented | — | — |
| `ORDER_EXECUTION_ASSUMPTION_001` | Execution | `UNKNOWN` | LOW | Order execution model (market/limit, partial fills) is unknown | core/worst_case.py | — |
| `PRICE_GAP_ASSUMPTION_001` | Grid behavior | `UNKNOWN` | LOW | Behavior when price gaps over multiple grid levels is unknown | core/grid.py, core/worst_case.py | — |
| `SLIPPAGE_ASSUMPTION_001` | Cost model | `UNKNOWN` | LOW | Slippage is not modeled and its magnitude is unknown | core/calculations.py | — |
| `SPREAD_ASSUMPTION_001` | Cost model | `UNKNOWN` | LOW | Spread magnitude is unknown (model excludes spread entirely) | core/calculations.py | — |
| `SWAP_ASSUMPTION_001` | Cost model | `UNKNOWN` | LOW | Swap model/value is unknown (model excludes swap) | core/calculations.py | — |
| `SYMBOL_INPUT_NAME_UNKNOWN_001` | — | `UNKNOWN` | — | Actual MT5 input name of parameter #1 (trade symbol) is unknown | — | — |
| `TICK_BAR_TIMER_ASSUMPTION_001` | Execution | `UNKNOWN` | LOW | The EA's trigger basis (tick / bar open / timer) is unknown | core/grid.py | — |
| `TICK_SIZE_ASSUMPTION_001` | Symbol specification | `UNKNOWN` | LOW | Real broker tick size per symbol is not captured | core/symbol_profile.py | — |
| `TICK_VALUE_ASSUMPTION_001` | Symbol specification | `UNKNOWN` | LOW | Tick value (money per tick per lot) is not captured | core/symbol_profile.py | — |
| `VOLUME_STEP_ASSUMPTION_001` | Lot sizing | `UNKNOWN` | LOW | Volume step / lot rounding semantics of the EX5 are unknown | core/calculations.py | — |

รายละเอียดเต็มของแต่ละรายการอยู่ใน `core/assumptions.py` (และดูได้ผ่าน `GET /api/assumptions`)
