"""OUR EA — evidence-backed strategy core (Phase 6).

Architecture (MASTER COMMAND §7):
    V1.68 Evidence (frozen, read-only)
      -> Frozen Behavioral Model (contract)
        -> Strategy Core (this package)
          -> Risk Guard (OUR_EA_POLICY)
            -> Execution Intent -> Adapter (SIMULATION/PAPER/DEMO; LIVE LOCKED)

Constraints honoured by this package:
  * NEVER imports Analyzer runtime (core.forensics / core.evidence /
    core.cycle / core.basket / core.calculations ...). The only Analyzer
    artifact consumed is the immutable frozen evidence model JSON plus
    the immutable replay dataset exported for Phase 6.
  * UNKNOWN rules stay UNKNOWN -> MODEL_UNCERTAINTY (uncertainty.py)
  * OUR EA policy (risk guard, emergency stop, recovery) is labelled
    SOURCE=OUR_EA_POLICY and never written back to the evidence model.
"""
MODEL_ID = "V1.68-EVIDENCE-MODEL-v1.0"
