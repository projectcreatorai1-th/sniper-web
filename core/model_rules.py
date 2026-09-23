"""Versioned Simulation Model Rules (Module 14 support).

The rules below define WHICH formula variant the simulation model uses.
They are versioned: every change (e.g. after the user clicks
"Apply Observed Rule" in Behavior Verification) is appended to a version
history so the model never changes silently from a single observation.

The active rules drive core.calculations - the single source of truth for
formula evaluation.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional

# lot formula variants
LOT_GEOMETRIC = "GEOMETRIC"            # BaseLot * multiplier^(level-1)   [default assumption]
LOT_ARITHMETIC_STEP = "ARITHMETIC"     # BaseLot + (level-1)*step_lots
LOT_FLAT = "FLAT"                      # BaseLot for every level

# grid spacing rule variants
GRID_FIXED_FROM_LAST = "FIXED_FROM_LAST"   # distance measured from last order price [default]
GRID_FIXED_FROM_AVERAGE = "FIXED_FROM_AVG" # distance measured from average entry

# basket scope variants
BASKET_COMBINED = "COMBINED"           # buy+sell counted as one basket [default]
BASKET_PER_SIDE = "PER_SIDE"           # each side closes independently

# partial close rule variants
PARTIAL_PRO_RATA_VOLUME = "PRO_RATA_VOLUME"  # reduce every position by pct [default]
PARTIAL_CLOSE_PROFITABLE_FIRST = "CLOSE_PROFITABLE_FIRST"

LOT_FORMULAS = (LOT_GEOMETRIC, LOT_ARITHMETIC_STEP, LOT_FLAT)
GRID_RULES = (GRID_FIXED_FROM_LAST, GRID_FIXED_FROM_AVERAGE)
BASKET_SCOPES = (BASKET_COMBINED, BASKET_PER_SIDE)
PARTIAL_RULES = (PARTIAL_PRO_RATA_VOLUME, PARTIAL_CLOSE_PROFITABLE_FIRST)


@dataclass
class SimulationModelRules:
    model_version: str = "SM-001"
    lot_formula: str = LOT_GEOMETRIC
    arithmetic_step_lots: float = 0.01
    grid_spacing_rule: str = GRID_FIXED_FROM_LAST
    basket_scope: str = BASKET_COMBINED
    partial_close_rule: str = PARTIAL_PRO_RATA_VOLUME
    notes: str = "Initial simulation model - all formulas are MODEL ASSUMPTION unless verified."

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SimulationModelRules":
        r = cls()
        for k, v in d.items():
            if hasattr(r, k) and v is not None:
                setattr(r, k, v)
        return r

    def validate(self) -> List[str]:
        errors = []
        if self.lot_formula not in LOT_FORMULAS:
            errors.append(f"lot_formula must be one of {LOT_FORMULAS}")
        if self.grid_spacing_rule not in GRID_RULES:
            errors.append(f"grid_spacing_rule must be one of {GRID_RULES}")
        if self.basket_scope not in BASKET_SCOPES:
            errors.append(f"basket_scope must be one of {BASKET_SCOPES}")
        if self.partial_close_rule not in PARTIAL_RULES:
            errors.append(f"partial_close_rule must be one of {PARTIAL_RULES}")
        return errors


@dataclass
class ModelVersionEntry:
    model_version: str
    timestamp: str
    source: str                      # "initial" | "observed-applied" | "manual-edit"
    changes: List[str]
    rules: dict
    notes: str = ""


class ModelVersionStore:
    """Persists model rule versions to a JSON file (data/model_versions.json)."""

    def __init__(self, path: Optional[str] = None):
        if path is None:
            base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
            path = os.path.join(base, "model_versions.json")
        self.path = path
        self.history: List[ModelVersionEntry] = []
        self._load()

    # -- persistence ---------------------------------------------------------
    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.history = [ModelVersionEntry(**e) for e in data.get("history", [])]
            except (json.JSONDecodeError, OSError, TypeError):
                self.history = []
        if not self.history:
            rules = SimulationModelRules()
            self.history = [ModelVersionEntry(
                model_version=rules.model_version,
                timestamp=datetime.now().isoformat(timespec="seconds"),
                source="initial",
                changes=["Initial simulation model"],
                rules=rules.to_dict(),
                notes=rules.notes,
            )]
            self._save()

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({
                "schema": "SNIPER_MODEL_VERSIONS",
                "history": [asdict(e) for e in self.history],
            }, f, ensure_ascii=False, indent=2)

    # -- api -------------------------------------------------------------------
    def active_rules(self) -> SimulationModelRules:
        return SimulationModelRules.from_dict(self.history[-1].rules)

    def all_versions(self) -> List[ModelVersionEntry]:
        return list(self.history)

    def apply_new_version(self, rules: SimulationModelRules, source: str,
                          changes: List[str], notes: str = "") -> SimulationModelRules:
        """Append a new version. NEVER called automatically from observations -
        the UI only calls this after explicit user confirmation."""
        errs = rules.validate()
        if errs:
            raise ValueError("; ".join(errs))
        # bump version number SM-### -> SM-###
        try:
            num = int(rules.model_version.split("-")[1]) + 1
        except (IndexError, ValueError):
            num = len(self.history) + 1
        existing = {e.model_version for e in self.history}
        new_ver = f"SM-{num:03d}"
        while new_ver in existing:
            num += 1
            new_ver = f"SM-{num:03d}"
        rules.model_version = new_ver
        self.history.append(ModelVersionEntry(
            model_version=new_ver,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            source=source,
            changes=changes,
            rules=rules.to_dict(),
            notes=notes,
        ))
        self._save()
        return rules
