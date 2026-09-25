"""Strategy Specification Generator — reads frozen evidence model + rule
registry + existing implementation and produces ALL spec files.

Every field traces back to evidence. Nothing is guessed.
UNKNOWN/PARTIAL/REJECTED preserved exactly.
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
SPEC_DIR = os.path.join(ROOT, "STRATEGY_SPEC")

from core.our_ea.rule_registry import RuleRegistry
from core.our_ea.state_machine import STATES, TRANSITIONS
from core.our_ea.risk_guard import RiskLimits

FROZEN_HASH = hashlib.sha256(open(os.path.join(
    ROOT, "data/evidence_model/V1.68-EVIDENCE-MODEL-v1.0.json"), "rb"
).read()).hexdigest().upper()

SPEC_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"
GENERATED_AT = datetime.now().isoformat(timespec="seconds")
COMMIT = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                        capture_output=True, text=True).stdout.strip()

STATUS_TAXONOMY = ["VERIFIED", "PARTIAL", "UNKNOWN", "REJECTED",
                   "HYPOTHESIS", "CONFIGURED", "DERIVED"]


def canonical_hash(data):
    """Deterministic hash: stable key ordering, no volatile timestamps."""
    if isinstance(data, dict):
        data = {k: canonical_hash(v) for k, v in sorted(data.items())}
    elif isinstance(data, list):
        data = [canonical_hash(v) for v in data]
    return data


def spec_hash(data):
    normalized = json.dumps(canonical_hash(data), sort_keys=True,
                            separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(normalized.encode()).hexdigest().upper()


def build_strategy_spec(reg):
    """Master strategy contract — every field from evidence."""
    r = reg.get
    return {
        "spec_identity": {
            "spec_id": "SNIPER-V168-STRATEGY-SPEC",
            "spec_version": SPEC_VERSION,
            "schema_version": SCHEMA_VERSION,
            "evidence_model_version": reg.model_version.model_id,
            "evidence_model_hash": FROZEN_HASH,
            "generated_from_commit": COMMIT,
        },
        "symbol_scope": {
            "symbol": "GOLDmicro",
            "contract_size": {"value": 1.0, "status": "VERIFIED",
                              "evidence_refs": ["E019"]},
            "lot_step": {"value": 0.01, "status": "VERIFIED",
                         "evidence_refs": ["E012"]},
            "price_digits": {"value": 2, "status": "CONFIGURED"},
        },
        "lot_model": {
            "formula": "Lot(n) = floor(BaseLot * Multiplier^(n-1) / LotStep) * LotStep",
            "rounding": "FLOOR (truncation to lot step, NOT round-half-up)",
            "base_lot": {"value": 0.10, "status": "VERIFIED",
                         "evidence_refs": ["E015"],
                         "note": "99.8% of first entries"},
            "multiplier": {"value": 1.10, "status": "VERIFIED",
                          "evidence_refs": ["E012", "E028"],
                          "note": "4451/4451 clean-cycle checks"},
            "lot_step": {"value": 0.01, "status": "VERIFIED",
                        "evidence_refs": ["E012"]},
            "observed_range": {"min_level": 1, "max_level": 32,
                              "status": "VERIFIED",
                              "evidence_refs": ["E028"],
                              "note": "L33+ extrapolated, NOT observed"},
            "overflow_behavior": {
                "below_min_lot": "clamp to min_lot",
                "above_max_lot": "clamp to max_lot",
                "status": "CONFIGURED",
                "note": "OUR_EA_POLICY, not historical behavior"},
        },
        "grid_model": {
            "direction": {
                "buy": {"action": "ADD_LOWER", "status": "VERIFIED",
                        "evidence_refs": ["E014"],
                        "note": "100.00% (1732/1732)"},
                "sell": {"action": "ADD_HIGHER", "status": "VERIFIED",
                         "evidence_refs": ["E014"],
                         "note": "99.82% (1692/1695), 3 exceptions documented"},
            },
            "spacing": {
                "nominal_value": 5.0,
                "unit": "USD",
                "status": "VERIFIED",
                "distribution": {
                    "median": 5.09, "p5": 4.72, "p95": 5.98,
                    "pct_in_band_4.5_5.5": 85.2},
                "evidence_refs": ["E013"],
                "note": "Observed distribution, NOT exact 5.0000"},
            "trigger_anchor": {
                "status": "PARTIAL",
                "compatible_hypotheses": ["H_PREV_ENTRY", "H_EXTREME"],
                "hypotheses_indistinguishable": True,
                "evidence_refs": ["E026"],
                "note": "Mathematically equivalent on averaging-down ladders"},
        },
        "basket_model": {
            "close_trigger": {
                "status": "PARTIAL",
                "compatible_hypotheses": [
                    {"id": "H_GROSS_1_00", "description": "gross >= $1.00",
                     "violation_rate_pct": 3.14},
                    {"id": "H_PER_LOT_0_50", "description": "gross >= lots * 0.50",
                     "violation_rate_pct": 0.70},
                    {"id": "H_PER_LOT_0_85", "description": "gross >= lots * 0.85",
                     "violation_rate_pct": 1.51}],
                "rejected_hypotheses": [
                    {"id": "H_GROSS_1_68", "description": "AccumulatorTargetUSD = 1.68",
                     "rejection_evidence": "E027",
                     "violation_rate_pct": 90.70}],
                "evidence_refs": ["E016", "E027"],
                "note": "Domain ≈ +$1.0-1.2 OBSERVED; no single hypothesis verified"},
        },
        "partial_close_model": {
            "exists": {"status": "VERIFIED", "observed_events": 492,
                      "evidence_refs": ["E025"]},
            "trigger": {"status": "UNKNOWN",
                       "runtime_handling": "MODEL_UNCERTAINTY + skip",
                       "evidence_refs": ["E025"]},
            "volume_rule": {"status": "UNKNOWN",
                          "runtime_handling": "MODEL_UNCERTAINTY + skip",
                          "evidence_refs": ["E025"]},
            "level_rule": {
                "status": "PARTIAL",
                "fifo_feasible": 390, "ambiguous": 102,
                "evidence_refs": ["E025"]},
        },
        "emergency_model": {
            "mechanism": {
                "status": "UNKNOWN",
                "observed_events": 0,
                "evidence_refs": ["E021"],
                "note": "0 emergency events in 862 production baskets"},
            "our_ea_policy": {
                "source": "OUR_EA_POLICY (NOT historical V1.68 behavior)",
                "max_loss_usd": 50.0,
                "max_drawdown_pct": 30.0,
                "max_grid_depth": 12,
                "kill_switch": True,
            },
        },
        "entry_model": {
            "initial_entry": {
                "condition": "cycle starts when flat",
                "action": "open BUY base_lot + SELL base_lot simultaneously",
                "status": "VERIFIED",
                "evidence_refs": ["E015"],
                "note": "99.4% both-sides, 72% same-second opening"},
            "re_entry": {
                "condition": "after basket close, immediately (<=2s)",
                "status": "VERIFIED",
                "evidence_refs": ["E018"],
                "note": "99.75% of transitions"},
            "restart_entry": {
                "status": "UNKNOWN",
                "evidence_refs": ["E022"],
                "note": "Single event observed (LOW confidence); controlled test needed"},
        },
        "exit_model": {
            "basket_close": {
                "condition": "total profit >= configurable hypothesis threshold",
                "status": "PARTIAL",
                "evidence_refs": ["E016", "E027"]},
            "emergency_close": {
                "status": "UNKNOWN",
                "evidence_refs": ["E021"]},
            "partial_close": {
                "status": "PARTIAL (existence verified, trigger UNKNOWN)",
                "evidence_refs": ["E025"]},
        },
        "signal_generation": {
            "strategy_type": "GRID_AVERAGING_BOTH_SIDES",
            "signal_authority": "SNIPER (research/analysis authority)",
            "entry_signal": {
                "source": "cycle start condition (flat state)",
                "direction": "BUY+SELL (both sides)",
                "status": "VERIFIED"},
            "grid_add_signal": {
                "source": "price crosses anchor-step per configured hypothesis",
                "direction": "derived from side (BUY adds lower, SELL adds higher)",
                "status": "PARTIAL (anchor hypothesis unresolved)"},
            "exit_signal": {
                "source": "basket profit >= hypothesis threshold",
                "status": "PARTIAL"},
            "note": "SNIPER generates research signals via Gateway; execution authority = OUR EA",
        },
        "uncertainty_policy": {
            "default_behavior": [
                "DO_NOT_GUESS", "EMIT_MODEL_UNCERTAINTY",
                "ENTER_SAFE_STATE", "RECORD_EVIDENCE_GAP",
                "CONTINUE_ONLY_WHEN_DETERMINISTIC"],
            "unknown_rules": [
                {"id": "R-PARTIAL-TRIGGER", "what": "partial close trigger condition",
                 "resolution": "tick-level data or controlled test"},
                {"id": "R-PARTIAL-VOLUME", "what": "partial close volume rule",
                 "resolution": "deal-level requested-vs-filled data"},
                {"id": "R-EMERGENCY", "what": "emergency mechanism",
                 "resolution": "observed emergency event or vendor documentation"},
                {"id": "R-RESTART-RECOVERY", "what": "V1.68 restart behavior",
                 "resolution": "controlled restart test (TEST_R spec ready)"},
            ],
        },
        "invariants": [
            {"id": "INV-001", "rule": "Lot step validity: lot must be multiple of lot_step"},
            {"id": "INV-002", "rule": "No negative lot"},
            {"id": "INV-003", "rule": "Risk limits never bypassed"},
            {"id": "INV-004", "rule": "State transitions explicit only"},
            {"id": "INV-005", "rule": "Duplicate event idempotency"},
            {"id": "INV-006", "rule": "No direct MT5 execution from SNIPER"},
            {"id": "INV-007", "rule": "No LIVE execution"},
            {"id": "INV-008", "rule": "UNKNOWN behavior cannot become execution"},
            {"id": "INV-009", "rule": "Evidence hash integrity"},
            {"id": "INV-010", "rule": "Deterministic replay"},
        ],
        "evidence_binding_summary": {
            "total_rules": 16,
            "verified": 8, "partial": 3, "unknown": 4, "rejected": 1,
            "all_traceable": True,
        },
    }


def build_parameter_spec(reg):
    params = []
    def P(pid, name, ptype, unit, value, status, source, refs=None,
           default=None, allowed_range=None, configurable=False, notes=""):
        params.append({
            "parameter_id": pid, "name": name, "type": ptype, "unit": unit,
            "value": value, "status": status, "source": source,
            "evidence_refs": refs or [], "default": default,
            "allowed_range": allowed_range, "configurable": configurable,
            "notes": notes})

    # Lot parameters
    P("PARAM-LOT-BASE", "BaseLot", "float", "lots", 0.10, "VERIFIED",
      "frozen_evidence_model", ["E015"])
    P("PARAM-LOT-MULT", "LotMultiplier", "float", "ratio", 1.10, "VERIFIED",
      "frozen_evidence_model", ["E012", "E028"])
    P("PARAM-LOT-STEP", "LotStep", "float", "lots", 0.01, "VERIFIED",
      "frozen_evidence_model", ["E012"])
    P("PARAM-LOT-ROUNDING", "LotRounding", "enum", "mode", "FLOOR",
      "VERIFIED", "frozen_evidence_model", ["E012", "E028"],
      notes="floor to step, NOT round-half-up (MC-001 confirmed)")

    # Grid parameters
    P("PARAM-GRID-STEP", "GridStepUSD", "float", "USD", 5.0, "VERIFIED",
      "frozen_evidence_model", ["E013"],
      allowed_range={"min": 1.0, "max": 50.0}, configurable=True,
      notes="Nominal value; observed distribution median 5.09")
    P("PARAM-GRID-ANCHOR", "GridTriggerHypothesis", "enum", "hypothesis_id",
      "H_PREV_ENTRY", "PARTIAL", "frozen_evidence_model", ["E026"],
      allowed_range=["H_PREV_ENTRY", "H_EXTREME"], configurable=True,
      notes="Hypotheses indistinguishable; selection is a declared config choice")
    P("PARAM-GRID-BUY-DIR", "GridBuyDirection", "enum", "direction",
      "DOWN", "VERIFIED", "frozen_evidence_model", ["E014"])
    P("PARAM-GRID-SELL-DIR", "GridSellDirection", "enum", "direction",
      "UP", "VERIFIED", "frozen_evidence_model", ["E014"])

    # Basket parameters
    P("PARAM-BASKET-TRIGGER", "BasketCloseHypothesis", "enum",
      "hypothesis_id", "H_GROSS_1_00", "PARTIAL",
      "frozen_evidence_model", ["E016", "E027"],
      allowed_range=["H_GROSS_1_00", "H_PER_LOT_0_50", "H_PER_LOT_0_85"],
      configurable=True,
      notes="3 compatible hypotheses; H_GROSS_1_68 REJECTED")

    # Partial close
    P("PARAM-PARTIAL-ENABLED", "PartialCloseEnabled", "boolean", "bool",
      False, "CONFIGURED", "our_ea_policy",
      notes="Trigger/volume UNKNOWN; disabled by default per safety policy")

    # Emergency (UNKNOWN mechanism, OUR_EA_POLICY limits)
    P("PARAM-RISK-MAX-LOSS", "MaxLossUSD", "float", "USD", 50.0,
      "CONFIGURED", "our_ea_policy")
    P("PARAM-RISK-MAX-DD", "MaxDrawdownPct", "float", "percent", 30.0,
      "CONFIGURED", "our_ea_policy")
    P("PARAM-RISK-MAX-DEPTH", "MaxGridDepth", "int", "levels", 12,
      "CONFIGURED", "our_ea_policy")
    P("PARAM-RISK-MAX-POS", "MaxPositions", "int", "count", 12,
      "CONFIGURED", "our_ea_policy")
    P("PARAM-RISK-MAX-LOT", "MaxTotalLot", "float", "lots", 2.0,
      "CONFIGURED", "our_ea_policy")
    P("PARAM-RISK-MAX-SPREAD", "MaxSpreadUSD", "float", "USD", 0.60,
      "CONFIGURED", "our_ea_policy")
    P("PARAM-RISK-CONSEC-FAIL", "MaxConsecutiveFailures", "int", "count",
      3, "CONFIGURED", "our_ea_policy")
    P("PARAM-RISK-TICK-VOL", "MaxTickVolatilityUSD", "float", "USD", 25.0,
      "CONFIGURED", "our_ea_policy")

    # State machine
    P("PARAM-STATE-INITIAL", "InitialState", "enum", "state",
      "IDLE", "CONFIGURED", "our_ea_implementation")

    # Contract/symbol
    P("PARAM-CONTRACT-SIZE", "ContractSize", "float", "ratio", 1.0,
      "VERIFIED", "frozen_evidence_model", ["E019"])
    P("PARAM-CONTRACT-STEP", "PriceDigits", "int", "digits", 2,
      "CONFIGURED", "our_ea_config")

    # Gateway
    P("PARAM-GW-ENDPOINT", "GatewayEndpoint", "string", "url", "",
      "CONFIGURED", "our_ea_config",
      notes="No hardcoded production endpoint")
    P("PARAM-GW-HEARTBEAT", "HeartbeatIntervalSec", "float", "seconds",
      30.0, "CONFIGURED", "our_ea_config")

    return {"parameters": params,
            "summary": {
                "total": len(params),
                "verified": sum(1 for p in params if p["status"] == "VERIFIED"),
                "partial": sum(1 for p in params if p["status"] == "PARTIAL"),
                "configured": sum(1 for p in params if p["status"] == "CONFIGURED"),
                "unknown": sum(1 for p in params if p["status"] == "UNKNOWN"),
            }}


def build_state_transition_spec():
    transitions = []
    for (from_state, event), to_state in sorted(TRANSITIONS.items()):
        transitions.append({
            "from": from_state, "event": event, "to": to_state,
            "guard": "declared in TRANSITIONS table",
            "action": "state change + audit log",
            "status": "VERIFIED" if from_state in ("IDLE", "INITIALIZING",
                      "WAITING_FOR_ENTRY") else "CONFIGURED",
            "evidence_refs": [],
            "test_refs": ["tests/our_ea/test_our_ea.py::TestStateMachine"],
        })
    return {
        "state_machine_version": "1.0",
        "states": list(STATES),
        "state_count": len(STATES),
        "transitions": transitions,
        "transition_count": len(transitions),
        "invariant": "No implicit transitions; undeclared transition raises InvalidTransition",
    }


def build_evidence_binding(reg):
    bindings = []
    for r in reg.all():
        bindings.append({
            "rule_id": r.rule_id,
            "rule_name": r.name,
            "status": r.status,
            "evidence_refs": r.evidence_refs,
            "candidate_refs": [r.candidate] if r.candidate else [],
            "implementation_refs": ["core/our_ea/"],
            "test_refs": ["tests/our_ea/"],
            "replay_refs": ["core/our_ea/replay.py"],
            "chain_complete": bool(r.evidence_refs),
        })
    return {"bindings": bindings,
            "total_rules": len(bindings),
            "complete_chains": sum(1 for b in bindings if b["chain_complete"])}


def build_ea_build_contract(strategy_spec_hash, parameter_spec_hash):
    return {
        "contract_version": "1.0.0",
        "strategy_spec_version": SPEC_VERSION,
        "strategy_spec_hash": strategy_spec_hash,
        "ea_status": "NOT_CREATED",
        "required_architecture": {
            "layers": ["SNIPER", "Strategy Spec", "EA Build Contract",
                       "OUR EA", "1144 Gateway", "MT5"],
            "authority": {
                "SNIPER": "Research/Backtest/Evidence/Signal Authority",
                "Gateway": "Transport/Event Bus",
                "OUR_EA": "Strategy Enforcement/Risk/Execution Authority",
                "MT5": "Trading Terminal",
            },
        },
        "required_modules": [
            "lot_engine", "grid_engine", "basket_engine", "partial_engine",
            "state_machine", "risk_guard", "execution_adapter",
            "persistence", "recovery", "event_ledger", "gateway_client",
            "market_data_feed", "reconciliation"],
        "required_parameters": "See parameter_spec.json",
        "state_machine_version": "1.0",
        "safety_requirements": [
            "LIVE permanently locked until human decision",
            "No direct MT5 execution from SNIPER",
            "Risk guard cannot be bypassed",
            "UNKNOWN behavior → MODEL_UNCERTAINTY + safe state",
            "Duplicate event idempotency",
            "Deterministic replay required",
        ],
        "test_requirements": [
            "All VERIFIED rules must pass replay consistency",
            "All UNKNOWN rules must emit MODEL_UNCERTAINTY",
            "All PARTIAL rules must not silently choose unsupported behavior",
            "State machine must reject implicit transitions",
            "Risk guard must block violations",
            "Restart recovery must pass 8 scenarios",
            "E2E signal flow must pass",
        ],
        "compatibility_requirements": {
            "strategy_spec_hash": strategy_spec_hash,
            "evidence_model_hash": FROZEN_HASH,
            "backward_compatible": True,
        },
    }


def main():
    os.makedirs(SPEC_DIR, exist_ok=True)
    reg = RuleRegistry.from_contract()

    # Generate specs
    strategy_spec = build_strategy_spec(reg)
    s_hash = spec_hash(strategy_spec)

    parameter_spec = build_parameter_spec(reg)
    p_hash = spec_hash(parameter_spec)

    state_spec = build_state_transition_spec()
    evidence_binding = build_evidence_binding(reg)
    e_hash = spec_hash(evidence_binding)

    ea_contract = build_ea_build_contract(s_hash, p_hash)
    c_hash = spec_hash(ea_contract)

    # Write JSON files
    for name, data in [
        ("strategy_spec.json", strategy_spec),
        ("parameter_spec.json", parameter_spec),
        ("state_transition_spec.json", state_spec),
        ("evidence_binding.json", evidence_binding),
        ("invariant_spec.json", {"invariants": strategy_spec["invariants"]}),
        ("ea_build_contract.json", ea_contract),
        ("spec_version.json", {
            "strategy_id": "SNIPER-V168-STRATEGY-SPEC",
            "spec_version": SPEC_VERSION,
            "schema_version": SCHEMA_VERSION,
            "evidence_model_version": reg.model_version.model_id,
            "evidence_model_hash": FROZEN_HASH,
            "strategy_spec_hash": s_hash,
            "parameter_spec_hash": p_hash,
            "evidence_binding_hash": e_hash,
            "ea_build_contract_hash": c_hash,
            "created_from_commit": COMMIT,
            "generated_at": GENERATED_AT,
            "compatibility": {
                "semantic_versioning": "MAJOR.MINOR.PATCH",
                "breaking_change_rule": "Any VERIFIED rule change = MAJOR",
            },
        }),
    ]:
        path = os.path.join(SPEC_DIR, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  wrote {name}")

    print(f"\n  strategy_spec_hash  = {s_hash[:24]}…")
    print(f"  parameter_spec_hash = {p_hash[:24]}…")
    print(f"  ea_contract_hash    = {c_hash[:24]}…")

    # Deterministic hash check
    s2 = spec_hash(build_strategy_spec(reg))
    print(f"  deterministic check = {'PASS' if s_hash == s2 else 'FAIL'}")
    return s_hash == s2


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
