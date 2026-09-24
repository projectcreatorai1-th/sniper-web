"""Evidence Registry (Phase 1).

Central, structured evidence records. Principles (per spec):

    Evidence -> Claim -> Status -> Assumption / Model

Evidence NEVER changes a formula automatically. External performance data
(Myfxbook/backtests) can never confirm internal EA formulas - at most it is
OBSERVED EXTERNAL DATA kept strictly separate from the SIMULATION MODEL.

Statuses: DOCUMENTED / OBSERVED / MODEL / UNKNOWN
Source types: DOCUMENTATION / IMAGE / VIDEO / MT5_BACKTEST / MT5_JOURNAL /
              MT5_CSV / MANUAL_OBSERVATION / MYFXBOOK / OTHER
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

SCHEMA = "SNIPER_EVIDENCE_V1"

# evidence statuses (separate from assumption statuses on purpose)
DOCUMENTED = "DOCUMENTED"
OBSERVED = "OBSERVED"
MODEL = "MODEL"
UNKNOWN = "UNKNOWN"
EVIDENCE_STATUSES = (DOCUMENTED, OBSERVED, MODEL, UNKNOWN)

# source types
DOCUMENTATION = "DOCUMENTATION"
IMAGE = "IMAGE"
VIDEO = "VIDEO"
MT5_BACKTEST = "MT5_BACKTEST"
MT5_JOURNAL = "MT5_JOURNAL"
MT5_CSV = "MT5_CSV"
MANUAL_OBSERVATION = "MANUAL_OBSERVATION"
MYFXBOOK = "MYFXBOOK"
OTHER = "OTHER"
SOURCE_TYPES = (DOCUMENTATION, IMAGE, VIDEO, MT5_BACKTEST, MT5_JOURNAL,
                MT5_CSV, MANUAL_OBSERVATION, MYFXBOOK, OTHER)

CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")

# interfaces without real importers yet keep this marker (never fake data)
INTERFACE_READY = "INTERFACE READY"

VIDEO_INSTALL = "Installation Video — วิธีติดตั้ง EA SNIPER.mp4"
NOT_PROOF_NOTE = ("Observed platform/default value during installation workflow; "
                  "not proof of internal EA logic.")


@dataclass
class EvidenceRecord:
    evidence_id: str
    source_type: str
    source_name: str
    source_reference: str = ""
    claim: str = ""
    observed_value: Optional[str] = None      # kept as text: values may be non-numeric
    ea_version: str = ""
    parameter: str = ""                       # related EA parameter, if any
    status: str = UNKNOWN
    confidence: str = "LOW"
    timestamp: str = ""                       # when the evidence was observed/recorded
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = SCHEMA
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "EvidenceRecord":
        r = cls(evidence_id=d.get("evidence_id", "UNKNOWN"),
                source_type=d.get("source_type", OTHER),
                source_name=d.get("source_name", ""))
        for k, v in d.items():
            if k == "schema" or not hasattr(r, k) or v is None:
                continue
            setattr(r, k, v)
        return r


def _baseline() -> List[EvidenceRecord]:
    """Seeds with only evidence that actually exists today (spec E001-E010)."""
    def rec(eid, stype, sname, claim, observed=None, status=UNKNOWN,
            confidence="LOW", parameter="", reference="", notes=""):
        return EvidenceRecord(
            evidence_id=eid, source_type=stype, source_name=sname,
            source_reference=reference, claim=claim, observed_value=observed,
            ea_version="1.68", parameter=parameter, status=status,
            confidence=confidence, timestamp="", notes=notes)

    return [
        rec("E001", DOCUMENTATION, "EA file name / seller manual",
            "EA version = 1.68", observed="1.68",
            status=DOCUMENTED, confidence="HIGH",
            reference="SNIPER CashFlow V 1.68.ex5 (filename); seller PDF manual"),
        rec("E002", VIDEO, VIDEO_INSTALL,
            "Observed platform = MT5", observed="MT5",
            status=OBSERVED, confidence="MEDIUM", notes=NOT_PROOF_NOTE),
        rec("E003", VIDEO, VIDEO_INSTALL,
            "Observed broker = XM Global", observed="XM Global",
            status=OBSERVED, confidence="MEDIUM", notes=NOT_PROOF_NOTE),
        rec("E004", VIDEO, VIDEO_INSTALL,
            "Observed account type = Hedge", observed="Hedge",
            status=OBSERVED, confidence="MEDIUM", notes=NOT_PROOF_NOTE),
        rec("E005", VIDEO, VIDEO_INSTALL,
            "Observed symbol = GOLDmicro", observed="GOLDmicro",
            status=OBSERVED, confidence="MEDIUM",
            notes=NOT_PROOF_NOTE + " Not a universal symbol requirement."),
        rec("E006", VIDEO, VIDEO_INSTALL,
            "Observed timeframe = M15", observed="M15",
            status=OBSERVED, confidence="MEDIUM",
            notes=NOT_PROOF_NOTE + " OBSERVED TEST ENVIRONMENT - not a required timeframe."),
        rec("E007", VIDEO, VIDEO_INSTALL,
            "EmergencyDistanceFromCycleUSD observed default = 90.0",
            observed="90.0", status=OBSERVED, confidence="MEDIUM",
            parameter="EmergencyDistanceFromCycleUSD",
            notes=NOT_PROOF_NOTE),
        rec("E008", DOCUMENTATION, "Seller preset image / PDF ($500 recommended)",
            "$500 recommended EmergencyDistanceFromCycleUSD = 50.0",
            observed="50.0", status=DOCUMENTED, confidence="MEDIUM",
            parameter="EmergencyDistanceFromCycleUSD",
            reference="builtin_presets(): Seller preset - Capital $500"),
        rec("E009", DOCUMENTATION, "Seller preset image ($3000 recommended)",
            "$3000 recommended values as supplied; values requiring confirmation "
            "remain unverified", observed=None, status=DOCUMENTED, confidence="LOW",
            reference="builtin_presets(): Seller preset - Capital $3000",
            notes="Supplied recommendation only - not verified against the EX5."),
        rec("E010", OTHER, "Recorded external baseline (historical)",
            "EX5 SHA-256/MD5 historical baseline for SNIPER CashFlow V 1.68.ex5",
            observed=("sha256=31E5176E794C29BE265EBF1B449B1047F2125C57A1CD227B257F89A54BF9CE37; "
                      "md5=3972D8436537F36F08FDF1E35C45750A"),
            status=DOCUMENTED, confidence="MEDIUM",
            notes="RECORDED_EXTERNAL_BASELINE - provided historical record, "
                  "not recomputed from a file in this workspace. See "
                  "core/ex5_integrity.py for the live integrity check."),
    ]


class EvidenceRegistry:
    """In-memory registry with baseline seeds + JSON persistence for user additions."""

    def __init__(self, persist_path: Optional[str] = None):
        self._records: Dict[str, EvidenceRecord] = {r.evidence_id: r for r in _baseline()}
        self.persist_path = persist_path
        if persist_path and os.path.exists(persist_path):
            try:
                with open(persist_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("records", []):
                    rec = EvidenceRecord.from_dict(item)
                    self._records[rec.evidence_id] = rec
            except (json.JSONDecodeError, OSError):
                pass  # corrupted file -> fall back to baseline

    # -- CRUD ---------------------------------------------------------------
    def add(self, record: EvidenceRecord, allow_overwrite: bool = False) -> None:
        if record.status not in EVIDENCE_STATUSES:
            raise ValueError(f"Invalid evidence status: {record.status}")
        if record.source_type not in SOURCE_TYPES:
            raise ValueError(f"Invalid source type: {record.source_type}")
        if record.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"Invalid confidence: {record.confidence}")
        if record.evidence_id in self._records and not allow_overwrite:
            raise KeyError(f"evidence id already exists: {record.evidence_id}")
        self._records[record.evidence_id] = record
        self._save()

    def get(self, evidence_id: str) -> EvidenceRecord:
        return self._records[evidence_id]

    def find(self, **filters) -> List[EvidenceRecord]:
        out = []
        for r in sorted(self._records.values(), key=lambda x: x.evidence_id):
            if all(getattr(r, k, None) == v for k, v in filters.items()):
                out.append(r)
        return out

    def all(self) -> List[EvidenceRecord]:
        return sorted(self._records.values(), key=lambda x: x.evidence_id)

    def by_status(self, status: str) -> List[EvidenceRecord]:
        return [r for r in self.all() if r.status == status]

    # -- persistence ----------------------------------------------------------
    def _save(self) -> None:
        if not self.persist_path:
            return
        os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
        with open(self.persist_path, "w", encoding="utf-8") as f:
            json.dump({"schema": SCHEMA,
                       "records": [r.to_dict() for r in self.all()]},
                      f, ensure_ascii=False, indent=2)


_DEFAULT_REGISTRY: Optional[EvidenceRegistry] = None


def default_evidence_registry() -> EvidenceRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        _DEFAULT_REGISTRY = EvidenceRegistry(os.path.join(base, "evidence.json"))
    return _DEFAULT_REGISTRY


# ---------------------------------------------------------------------------
# External evidence (Myfxbook etc.) - DATA MODEL / INTERFACE ONLY.
# No importer is implemented in this phase; no fake data may be created.
# ---------------------------------------------------------------------------
@dataclass
class ExternalEvidence:
    source_url: str = ""
    source_name: str = ""
    platform: str = ""
    broker: str = ""
    symbol: str = ""
    timeframe: str = ""
    leverage: Optional[float] = None
    period: str = ""
    trade_count: Optional[int] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    drawdown: Optional[float] = None
    mae: Optional[float] = None
    mfe: Optional[float] = None
    trade_duration: Optional[float] = None
    deposits: List[float] = field(default_factory=list)
    withdrawals: List[float] = field(default_factory=list)
    commission: Optional[float] = None
    swap: Optional[float] = None
    events: List[dict] = field(default_factory=list)
    retrieved_at: str = ""
    import_status: str = INTERFACE_READY

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = "SNIPER_EXTERNAL_EVIDENCE_V1"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ExternalEvidence":
        e = cls()
        for k, v in d.items():
            if k == "schema" or not hasattr(e, k) or v is None:
                continue
            setattr(e, k, v)
        return e
