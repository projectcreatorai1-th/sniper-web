"""Parameter facts registry (Phase 1).

Separates CODE NAMES from VERIFIED parameter identity, and separates
EA DEFAULT / RECOMMENDED PRESET / OBSERVED VALUE / USER VALUE so distinct
concepts can never merge silently (audit finding: EmergencyDistance
observed 90.0 vs preset 50.0 existed as one value).

Nothing here changes EAConfig, presets, or simulation behavior.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional

SCHEMA = "SNIPER_PARAM_FACTS_V1"

UNKNOWN = "UNKNOWN"
UNVERIFIED_CANDIDATE = "UNVERIFIED CANDIDATE"
DOCUMENTED = "DOCUMENTED"
OBSERVED = "OBSERVED"

# value-record kinds
EA_DEFAULT = "EA DEFAULT"
RECOMMENDED_PRESET = "RECOMMENDED PRESET"
OBSERVED_VALUE = "OBSERVED VALUE"
USER_VALUE = "USER VALUE"


@dataclass
class ParameterValueRecord:
    kind: str                     # EA_DEFAULT / RECOMMENDED_PRESET / OBSERVED_VALUE / USER_VALUE
    value: float
    source: str
    status: str                   # DOCUMENTED / OBSERVED / MODEL / UNKNOWN
    evidence_id: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParameterFact:
    parameter_id: str             # e.g. PARAM_21 (position in the 27-row manual list)
    code_name: str = ""           # name used in this codebase ("" if none)
    manual_label: str = ""        # row label from the seller manual, when known
    meaning: str = UNKNOWN
    status: str = UNKNOWN         # identity status of the mapping
    value_records: List[ParameterValueRecord] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = SCHEMA
        return d


def emergency_distance_facts() -> ParameterFact:
    """EmergencyDistanceFromCycleUSD (#18): observed 90.0 and preset 50.0
    stored as SEPARATE records. The simulation model default (50.0 in
    EAConfig) is intentionally unchanged - it is a model/preset value,
    not the observed EA default."""
    return ParameterFact(
        parameter_id="PARAM_18",
        code_name="EmergencyDistanceFromCycleUSD",
        manual_label="EmergencyDistanceFromCycleUSD (seller manual row #18)",
        meaning="Price distance from the trading frame beyond which the "
                "emergency behavior engages (see EMERGENCY_DOC_001).",
        status=DOCUMENTED,
        value_records=[
            ParameterValueRecord(
                kind=OBSERVED_VALUE, value=90.0,
                source="Installation Video — วิธีติดตั้ง EA SNIPER.mp4",
                status=OBSERVED, evidence_id="E007",
                notes="Observed default during installation workflow; not proof "
                      "of internal EA logic. NOT interpreted as a formula."),
            ParameterValueRecord(
                kind=RECOMMENDED_PRESET, value=50.0,
                source="$500 preset (builtin_presets: Seller preset - Capital $500)",
                status=DOCUMENTED, evidence_id="E008",
                notes="Documented recommendation for the $500 preset. NOT the "
                      "internal EA default."),
            ParameterValueRecord(
                kind=EA_DEFAULT, value=50.0,
                source="EAConfig default (core/config.py) - MODEL PRESET VALUE",
                status="MODEL",
                notes="The simulation model keeps 50.0 as its default so existing "
                      "results stay identical; this is a model choice, NOT a claim "
                      "about the EX5 default."),
        ],
        evidence_ids=["E007", "E008"],
        notes="90.0 (OBSERVED) and 50.0 (RECOMMENDED/MODEL) are distinct records "
              "and must never be merged. Neither value is preferred.")


def parameter_21_fact() -> ParameterFact:
    """Parameter #21: the manual row containing 'ใส่ 0 = ปิดใช้งาน'.

    The codebase uses the name AccumTargetUSD at this position, but NO
    evidence proves the mapping - so the identity stays UNKNOWN and the
    code name is an UNVERIFIED CANDIDATE. The code name is NOT renamed."""
    return ParameterFact(
        parameter_id="PARAM_21",
        code_name="AccumTargetUSD",
        manual_label="UNKNOWN - manual row containing 'ใส่ 0 = ปิดใช้งาน'",
        meaning=UNKNOWN,
        status=UNKNOWN,
        value_records=[],           # no verified values for an unverified parameter
        evidence_ids=[],
        notes=("CODE NAME 'AccumTargetUSD' = UNVERIFIED CANDIDATE mapping only. "
               "Do not display or document it as a verified EA parameter. "
               "Position in core/config.py parameter order: #21."))


def parameter_facts() -> List[ParameterFact]:
    return [emergency_distance_facts(), parameter_21_fact()]


def find_fact(parameter_id: str) -> Optional[ParameterFact]:
    for f in parameter_facts():
        if f.parameter_id == parameter_id:
            return f
    return None
