"""Parameter validation (VALIDATION section of the spec).

Checks EA config against broker/symbol constraints (configurable via
SymbolProfile) and account settings. Returns structured issues with severity:

  ERROR   - value makes the configuration unusable / order invalid
  WARNING - configuration works but carries risk or contradicts itself
  INFO    - neutral notes

Never raises on bad input - the GUI must not crash on wrong values.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from core.config import EAConfig, TIME_FIELDS
from core.symbol_profile import SymbolProfile, AccountSettings

ERROR = "ERROR"
WARNING = "WARNING"
INFO = "INFO"

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    parameter: str = ""
    assumption: str = ""       # related assumption id (if any)

    def to_dict(self) -> dict:
        return {
            "severity": self.severity, "code": self.code, "message": self.message,
            "parameter": self.parameter, "assumption": self.assumption,
        }


def validate_time(value: str) -> bool:
    return bool(_TIME_RE.match(value or ""))


def validate_config(config: EAConfig, profile: SymbolProfile,
                    account: AccountSettings,
                    capital: float = 0.0) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    def err(code, msg, param="", assumption=""):
        issues.append(ValidationIssue(ERROR, code, msg, param, assumption))

    def warn(code, msg, param="", assumption=""):
        issues.append(ValidationIssue(WARNING, code, msg, param, assumption))

    def info(code, msg, param=""):
        issues.append(ValidationIssue(INFO, code, msg, param))

    # --- hard numeric checks ------------------------------------------------
    if config.GridStepUSD <= 0:
        err("GRID_STEP_POSITIVE", "GridStepUSD must be > 0", "GridStepUSD")
    if config.LotMultiplier <= 0:
        err("MULTIPLIER_POSITIVE", "LotMultiplier must be > 0", "LotMultiplier")
    if config.BaseLot <= 0:
        err("BASELOT_POSITIVE", "BaseLot must be > 0", "BaseLot")
    if config.BasketCloseAllUSD < 0:
        err("BASKET_TARGET_NON_NEGATIVE", "BasketCloseAllUSD must be >= 0", "BasketCloseAllUSD")
    if not (0 <= config.ProfitPartialPercent <= 100):
        err("PARTIAL_PERCENT_RANGE", "ProfitPartialPercent must be within 0-100", "ProfitPartialPercent")
    if config.ProfitPartialTriggerUSD < 0:
        err("PARTIAL_TRIGGER_NON_NEGATIVE", "ProfitPartialTriggerUSD must be >= 0", "ProfitPartialTriggerUSD")
    if config.MainTrailStartProfitUSD < 0 or config.MainTrailLockUSD < 0:
        err("TRAILING_NON_NEGATIVE", "Trailing USD values must be >= 0", "MainSideTrailing")
    if config.EmergencyDistanceFromCycleUSD < 0:
        err("EMERGENCY_DISTANCE_NON_NEGATIVE", "EmergencyDistanceFromCycleUSD must be >= 0",
            "EmergencyDistanceFromCycleUSD")
    if config.AccumTargetUSD < 0:
        err("ACCUM_TARGET_NON_NEGATIVE", "AccumTargetUSD must be >= 0", "AccumTargetUSD")

    # --- time fields ----------------------------------------------------------
    for tf in TIME_FIELDS:
        if not validate_time(getattr(config, tf, "")):
            err("TIME_FORMAT", f"{tf} must be HH:MM (24h)", tf)

    # --- broker lot constraints ---------------------------------------------
    if config.BaseLot < profile.lot_min:
        warn("BASELOT_BELOW_MIN", f"BaseLot {config.BaseLot} is below broker minimum lot "
                                  f"{profile.lot_min}", "BaseLot", "LOT_STEP_BOUNDARY_ASSUMPTION_001")
    if config.BaseLot > profile.lot_max:
        err("BASELOT_ABOVE_MAX", f"BaseLot {config.BaseLot} is above broker maximum lot "
                                 f"{profile.lot_max}", "BaseLot")
    step = profile.lot_step
    if step > 0 and abs(round(config.BaseLot / step) * step - config.BaseLot) > 1e-9:
        warn("BASELOT_NOT_ON_STEP", f"BaseLot {config.BaseLot} is not a multiple of lot step "
                                    f"{step} (broker will round it)", "BaseLot",
             "LOT_NORMALIZATION_ASSUMPTION_001")
    if account.leverage <= 0:
        err("LEVERAGE_POSITIVE", "Leverage must be > 0", "leverage")
    if profile.contract_size <= 0:
        err("CONTRACT_SIZE_POSITIVE", "Contract size must be > 0", "contract_size")
    if profile.lot_step <= 0:
        err("LOT_STEP_POSITIVE", "Lot step must be > 0", "lot_step")

    # --- consistency / risk warnings -----------------------------------------
    if config.UseProfitPartialClose and config.UseBasketCloseAll \
            and config.ProfitPartialTriggerUSD > config.BasketCloseAllUSD:
        warn("PARTIAL_NEVER_FIRES", "ProfitPartialTriggerUSD is above BasketCloseAllUSD - "
                                    "the basket will close before the partial close triggers",
             "ProfitPartialTriggerUSD")
    if config.UseMainSideTrailing and config.MainTrailLockUSD > config.MainTrailStartProfitUSD:
        warn("TRAIL_LOCK_ABOVE_START", "MainTrailLockUSD is above MainTrailStartProfitUSD - "
                                       "trailing would close immediately on start",
             "MainTrailLockUSD")
    if not (config.UseGridBuy or config.UseGridSell):
        warn("NO_GRID_SIDE", "Both UseGridBuy and UseGridSell are false - the EA has nothing to do")
    if config.LotMultiplier >= 2.0 and config.UsePositionSizeOptimization:
        warn("EXTREME_MULTIPLIER", f"LotMultiplier {config.LotMultiplier} grows lots very fast "
                                   "(>= 2.0)", "LotMultiplier")
    if config.UsePositionSizeOptimization and config.LotMultiplier < 1.0:
        info("MULTIPLIER_BELOW_ONE", "LotMultiplier < 1.0 shrinks lots each level", "LotMultiplier")
    if config.GridStepUSD < 5 * profile.tick_size:
        warn("EXTREME_SMALL_STEP", f"GridStepUSD {config.GridStepUSD} is extremely small "
                                   f"(< 5 x tick size)", "GridStepUSD")
    if config.EnableEmergencyStop is False:
        info("EMERGENCY_OFF", "EnableEmergencyStop=false - first run has no emergency brake "
                              "(all protective features are off by default)", "EnableEmergencyStop")
    if config.UseBasketCloseAll is False:
        warn("BASKET_CLOSE_OFF", "UseBasketCloseAll=false - main profit-taking mechanism disabled",
             "UseBasketCloseAll")
    if config.UseProfitPartialClose and config.ProfitPartialPercent <= 0:
        warn("PARTIAL_PERCENT_ZERO", "ProfitPartialPercent=0 - partial close closes nothing",
             "ProfitPartialPercent")
    if config.AccumTargetUSD > 0 and not config.EnablePauseAfterAccumTargetHit:
        info("ACCUM_PAUSE_OFF", "AccumTargetUSD set but EnablePauseAfterAccumTargetHit=false",
             "AccumTargetUSD")

    # --- insufficient capital (margin for first grid level) -------------------
    from core import calculations as calc  # local import to avoid cycle at module load
    if capital is None:
        capital = 0.0
    if capital < 0:
        err("CAPITAL_POSITIVE", "Capital must be > 0", "capital")
    if capital > 0:
        m1 = calc.margin_used(config.BaseLot, profile.reference_price, profile, account)
        if m1 > capital:
            err("INSUFFICIENT_CAPITAL",
                f"Margin for the first order (~{m1:.2f}) exceeds capital {capital}",
                "capital", "MARGIN_ASSUMPTION_001")

    return issues


def has_errors(issues: List[ValidationIssue]) -> bool:
    return any(i.severity == ERROR for i in issues)


def worst_severity(issues: List[ValidationIssue]) -> str:
    if any(i.severity == ERROR for i in issues):
        return ERROR
    if any(i.severity == WARNING for i in issues):
        return WARNING
    return INFO
