# Uncertainty Matrix

*ทุก UNKNOWN/PARTIAL — runtime behavior มาตรฐาน: DO_NOT_GUESS*

| ID | What is Unknown | Why | Compatible Hypotheses | Evidence Needed | Runtime Behavior | Safety Behavior | EA Rule |
|---|---|---|---|---|---|---|---|
| UNC-001 | Partial close trigger condition | Close-side data cannot observe evaluation instant | N/A | Tick-level data showing watched quantity at fire time | MODEL_UNCERTAINTY + skip partial close | No ambiguous execution | Emit uncertainty; do not execute partial |
| UNC-002 | Partial close volume rule | Deal-level requested-vs-filled not available | N/A | Controlled test with deal-level data | MODEL_UNCERTAINTY + skip | No volume guess | Emit uncertainty; do not guess volume |
| UNC-003 | Emergency mechanism | 0 events in 862 production baskets; deep grid survived | N/A | Observed emergency event or vendor docs | OUR_EA_POLICY fallback (loss/dd/depth limits) | SAFE_STOP on policy breach | Implement OUR_EA_POLICY only; label as policy |
| UNC-004 | V1.68 restart recovery | Single LOW-confidence event; no controlled test | ADOPTS_STATE vs STARTS_NEW | Execute TEST_R_RESTART_RECOVERY | Safe stop + operator confirmation | No silent unsafe resume | Recovery = OUR_EA_POLICY; label as policy |
| UNC-005 | Grid trigger anchor | H_PREV_ENTRY ≡ H_EXTREME on averaging-down ladders | H_PREV_ENTRY, H_EXTREME | Tick-level data separating anchor hypotheses | Configurable hypothesis_id | No silent winner | Both allowed; must record hypothesis_id |
| UNC-006 | Basket close exact trigger | 3 hypotheses compatible with observed data | H_GROSS_1_00, H_PER_LOT_0_50, H_PER_LOT_0_85 | Tick-level observation of close evaluation instant | Configurable hypothesis | No silent winner | Must record hypothesis_id; 1.68 REJECTED |
| UNC-007 | Partial close level rule | 390 FIFO-feasible / 102 ambiguous attribution | FIFO | Unambiguous deal-level position attribution | MODEL_UNCERTAINTY (when ambiguous) | No forced level selection | Emit uncertainty when ambiguous |

## Default Runtime Policy (ALL UNKNOWN)

```
DO NOT GUESS
DO NOT EXECUTE AMBIGUOUS BEHAVIOR
EMIT MODEL_UNCERTAINTY
RECORD EVIDENCE GAP
ENTER SAFE STATE
CONTINUE ONLY WHEN DETERMINISTIC CONDITIONS ARE SATISFIED
```

## NOT Unknown (confirmed NOT unknown)

| Item | Status | Note |
|---|---|---|
| Lot formula | VERIFIED | floor(0.1×1.1^(n-1)/0.01)×0.01 — 100% match |
| Grid direction | VERIFIED | BUY down 100%, SELL up 99.82% |
| Base lot | VERIFIED | 0.10 — 99.8% |
| Both-sides entry | VERIFIED | 99.4% |
| Contract size | VERIFIED | 1.0 — median stdev 0.0091 |
| Normal resume | VERIFIED | ≤2s — 99.75% |
| AccumulatorTargetUSD=1.68 | REJECTED | 96.32% violations |
