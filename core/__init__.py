"""Core package - SNIPER CashFlow Analyzer.

The core is GUI-free by design: a future web version can import `core.*`
and reuse every calculation unchanged.
"""
from core.config import EAConfig, SCHEMA, builtin_presets
from core.symbol_profile import SymbolProfile, AccountSettings, builtin_profiles
from core.model_rules import SimulationModelRules, ModelVersionStore
from core.risk import RiskThresholds

__all__ = [
    "EAConfig", "SCHEMA", "builtin_presets",
    "SymbolProfile", "AccountSettings", "builtin_profiles",
    "SimulationModelRules", "ModelVersionStore", "RiskThresholds",
]
