"""External Evidence v2 (Phase 3): real, traceable external evidence.

ExternalEvidence holds OBSERVED EXTERNAL DATA (e.g. Myfxbook performance).
It can never become proof of internal EA rules - metrics are stored as
OBSERVED_EXTERNAL_METRIC and quality is classified (DIRECT / INDIRECT /
CONTEXTUAL / UNKNOWN).

EvidenceSnapshot freezes WHAT the analyzer saw (content/metrics hashes) so
later source changes are detectable. Snapshots are append-only - history is
never overwritten. Re-imports with changed content create a NEW evidence
record and mark the previous one SUPERSEDED (with superseded_by).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional

SCHEMA = "SNIPER_EXTERNAL_EVIDENCE_V2"
SNAPSHOT_SCHEMA = "SNIPER_EVIDENCE_SNAPSHOT_V1"
LINK_SCHEMA = "SNIPER_EVIDENCE_LINK_V1"
CANDIDATE_SCHEMA = "SNIPER_MODEL_CANDIDATE_V1"

# --- source types (Phase 3) -------------------------------------------------
SRC_MYFXBOOK = "MYFXBOOK"
SRC_MT5_STATEMENT = "MT5_STATEMENT"
SRC_MT5_REPORT = "MT5_REPORT"
SRC_MANUAL = "MANUAL"
SRC_OTHER = "OTHER"
EXTERNAL_SOURCE_TYPES = (SRC_MYFXBOOK, SRC_MT5_STATEMENT, SRC_MT5_REPORT,
                         SRC_MANUAL, SRC_OTHER)

# --- evidence quality (classification, NOT a score) --------------------------
QUALITY_DIRECT = "DIRECT"          # e.g. MT5 journal event
QUALITY_INDIRECT = "INDIRECT"      # e.g. Myfxbook performance metric
QUALITY_CONTEXTUAL = "CONTEXTUAL"  # e.g. installation video screenshot
QUALITY_UNKNOWN = "UNKNOWN"
EVIDENCE_QUALITIES = (QUALITY_DIRECT, QUALITY_INDIRECT, QUALITY_CONTEXTUAL,
                      QUALITY_UNKNOWN)

SOURCE_QUALITY_DEFAULTS = {
    "MT5_JOURNAL": QUALITY_DIRECT, "MT5_CSV": QUALITY_DIRECT,
    "MT5_TEST": QUALITY_DIRECT, "MT5_STATEMENT": QUALITY_DIRECT,
    "MT5_REPORT": QUALITY_DIRECT,
    SRC_MYFXBOOK: QUALITY_INDIRECT,
    "VIDEO": QUALITY_CONTEXTUAL, "IMAGE": QUALITY_CONTEXTUAL,
}

# --- link relations ----------------------------------------------------------
REL_SUPPORTS = "supports"
REL_CONTRADICTS = "contradicts"
REL_CONTEXT_FOR = "context_for"
LINK_RELATIONS = (REL_SUPPORTS, REL_CONTRADICTS, REL_CONTEXT_FOR)
TARGET_ASSUMPTION = "ASSUMPTION"
TARGET_OBSERVATION = "OBSERVATION"
LINK_TARGET_TYPES = (TARGET_ASSUMPTION, TARGET_OBSERVATION)

# --- evidence statuses (Phase 3 adds SUPERSEDED) ------------------------------
SUPERSEDED = "SUPERSEDED"

# --- extraction statuses ------------------------------------------------------
EXTRACTION_IMPORTED = "IMPORTED"
EXTRACTION_FAILED = "IMPORT_FAILED"
EXTRACTION_BLOCKED = "IMPORT BLOCKED"
EXTRACTION_PARTIAL = "PARTIAL"

# --- metric classification -----------------------------------------------------
OBSERVED_EXTERNAL_METRIC = "OBSERVED_EXTERNAL_METRIC"
KNOWN_METRIC_KEYS = (
    "balance", "equity", "profit", "profit_factor", "drawdown", "trades",
    "lots", "long_trades", "short_trades", "average_trade_duration",
)

# formula/rule assumptions that INDIRECT evidence may not "support"
FORMULA_ASSUMPTION_IDS = (
    "LOT_FORMULA_ASSUMPTION_001", "GRID_TRIGGER_ASSUMPTION_001",
    "GRID_DIRECTION_ASSUMPTION_001", "BASKET_SCOPE_ASSUMPTION_001",
    "PARTIAL_CLOSE_ASSUMPTION_001", "EMERGENCY_FRAME_ASSUMPTION_001",
    "CYCLE_START_RULE_ASSUMPTION_001", "CYCLE_END_RULE_ASSUMPTION_001",
)

# Phase 1 marker kept for compatibility: a model that has not been imported
# yet reports INTERFACE READY (never fake data)
INTERFACE_READY = "INTERFACE READY"

MYFXBOOK_LIMITATION = ("External performance data does not prove internal "
                       "EA formulas.")


class ExternalEvidenceError(Exception):
    """Raised for import/validation problems (with an honest reason)."""


def content_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def metrics_hash(metrics: Dict[str, float]) -> str:
    stable = json.dumps(metrics, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest().upper()


def evidence_quality(source_type: str) -> str:
    return SOURCE_QUALITY_DEFAULTS.get(source_type, QUALITY_UNKNOWN)


@dataclass
class ExternalMetric:
    key: str                      # e.g. profit_factor
    value: float
    kind: str = OBSERVED_EXTERNAL_METRIC
    period_start: Optional[str] = None   # UNKNOWN stays None + unknown flag
    period_end: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExternalEvidence:
    evidence_id: str = ""
    source_type: str = SRC_OTHER
    source_url: str = ""                 # original_url (kept traceable)
    normalized_url: str = ""
    source_name: str = ""
    retrieved_at: str = ""
    published_at: str = ""               # "" = UNKNOWN
    account_type: str = ""               # NO account number, ever
    broker: str = ""
    platform: str = ""
    symbol: str = ""
    timeframe: str = ""
    period_start: str = ""               # "" = UNKNOWN
    period_end: str = ""
    raw_reference: str = ""              # where the raw content is tracked
    extracted_metrics: List[ExternalMetric] = field(default_factory=list)
    extraction_status: str = INTERFACE_READY
    confidence: str = "LOW"
    notes: str = ""
    quality: str = QUALITY_UNKNOWN
    linked_assumptions: List[str] = field(default_factory=list)
    linked_observations: List[str] = field(default_factory=list)
    status: str = "OBSERVED"             # OBSERVED (never auto-verified)
    superseded_by: str = ""

    def metric_dict(self) -> Dict[str, float]:
        return {m.key: m.value for m in self.extracted_metrics}

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = SCHEMA
        d["extracted_metrics"] = [m.to_dict() for m in self.extracted_metrics]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ExternalEvidence":
        e = cls()
        metrics = d.pop("extracted_metrics", []) if isinstance(d, dict) else []
        for k, v in d.items():
            if k == "schema" or not hasattr(e, k) or v is None:
                continue
            setattr(e, k, v)
        e.extracted_metrics = [ExternalMetric(**m) for m in metrics
                               if isinstance(m, dict)]
        return e


@dataclass
class EvidenceSnapshot:
    snapshot_id: str
    evidence_id: str
    retrieved_at: str
    content_hash: str
    metrics_hash: str
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = SNAPSHOT_SCHEMA
        return d


@dataclass
class EvidenceLink:
    link_id: str
    evidence_id: str
    target_type: str                  # ASSUMPTION | OBSERVATION
    target_id: str
    relation: str                     # supports | contradicts | context_for
    created_at: str = ""
    confirmed_by: str = ""            # human confirmation ("" = unconfirmed)
    confirmed_at: str = ""
    confirmation_note: str = ""

    def confirmed(self) -> bool:
        return bool(self.confirmed_by)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = LINK_SCHEMA
        return d


@dataclass
class Conflict:
    target_type: str
    target_id: str
    supports: List[str]
    contradicts: List[str]
    resolved: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Append-only stores (JSON files under data/)
# ---------------------------------------------------------------------------
def _load_json_list(path: str) -> List[dict]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_json(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


class ExternalEvidenceStore:
    """data/external_evidence.json + data/evidence_snapshots.json (append-only)."""

    def __init__(self, directory: Optional[str] = None):
        if directory is None:
            base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
            directory = base
        self.evidence_path = os.path.join(directory, "external_evidence.json")
        self.snapshot_path = os.path.join(directory, "evidence_snapshots.json")

    # -- evidence -------------------------------------------------------------
    def all(self) -> List[ExternalEvidence]:
        items = _load_json_list(self.evidence_path)
        return [ExternalEvidence.from_dict(d) for d in items]

    def get(self, evidence_id: str) -> ExternalEvidence:
        for e in self.all():
            if e.evidence_id == evidence_id:
                return e
        raise KeyError(evidence_id)

    def find_by_url(self, normalized_url: str) -> List[ExternalEvidence]:
        return [e for e in self.all() if e.normalized_url == normalized_url
                and e.status != SUPERSEDED]

    def save(self, evidence: ExternalEvidence) -> None:
        items = _load_json_list(self.evidence_path)
        items = [i for i in items if i.get("evidence_id") != evidence.evidence_id]
        items.append(evidence.to_dict())
        _save_json(self.evidence_path, items)

    def mark_superseded(self, evidence_id: str, superseded_by: str) -> None:
        items = _load_json_list(self.evidence_path)
        for i in items:
            if i.get("evidence_id") == evidence_id:
                i["status"] = SUPERSEDED
                i["superseded_by"] = superseded_by
        _save_json(self.evidence_path, items)

    # -- snapshots (append-only; history never overwritten) --------------------
    def add_snapshot(self, snap: EvidenceSnapshot) -> None:
        items = _load_json_list(self.snapshot_path)
        items.append(snap.to_dict())
        _save_json(self.snapshot_path, items)

    def snapshots_for(self, evidence_id: str) -> List[EvidenceSnapshot]:
        items = _load_json_list(self.snapshot_path)
        return [EvidenceSnapshot(**{k: v for k, v in i.items() if k != "schema"})
                for i in items if i.get("evidence_id") == evidence_id]


class EvidenceLinkStore:
    """data/evidence_links.json - links + human confirmations."""

    def __init__(self, directory: Optional[str] = None):
        if directory is None:
            base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
            directory = base
        self.path = os.path.join(directory, "evidence_links.json")

    def _items(self) -> List[dict]:
        return _load_json_list(self.path)

    def add(self, evidence_id: str, target_type: str, target_id: str,
            relation: str) -> EvidenceLink:
        if relation not in LINK_RELATIONS:
            raise ValueError(f"relation must be one of {LINK_RELATIONS}")
        if target_type not in LINK_TARGET_TYPES:
            raise ValueError(f"target_type must be one of {LINK_TARGET_TYPES}")
        for l in self._items():
            if (l["evidence_id"] == evidence_id and l["target_type"] == target_type
                    and l["target_id"] == target_id and l["relation"] == relation):
                raise KeyError("link already exists")
        link = EvidenceLink(
            link_id=f"L-{len(self._items()) + 1:04d}",
            evidence_id=evidence_id, target_type=target_type,
            target_id=target_id, relation=relation,
            created_at=datetime.now().isoformat(timespec="seconds"))
        items = self._items()
        items.append(link.to_dict())
        _save_json(self.path, items)
        return link

    def remove(self, link_id: str) -> bool:
        items = self._items()
        kept = [i for i in items if i.get("link_id") != link_id]
        if len(kept) == len(items):
            return False
        _save_json(self.path, kept)
        return True

    def all(self) -> List[EvidenceLink]:
        return [EvidenceLink(**{k: v for k, v in i.items() if k != "schema"})
                for i in self._items()]

    def confirm(self, link_id: str, confirmed_by: str,
                note: str = "") -> EvidenceLink:
        if not confirmed_by or not confirmed_by.strip():
            raise ValueError("confirmation requires a human reviewer name")
        items = self._items()
        for i in items:
            if i.get("link_id") == link_id:
                i["confirmed_by"] = confirmed_by
                i["confirmed_at"] = datetime.now().isoformat(timespec="seconds")
                i["confirmation_note"] = note
                _save_json(self.path, items)
                return EvidenceLink(**{k: v for k, v in i.items() if k != "schema"})
        raise KeyError(link_id)

    # -- conflict detection (no auto-resolution) --------------------------------
    def conflicts(self) -> List[Conflict]:
        out: List[Conflict] = []
        groups: Dict[tuple, Dict[str, List[str]]] = {}
        for l in self.all():
            if not l.confirmed():
                continue
            key = (l.target_type, l.target_id)
            groups.setdefault(key, {}).setdefault(l.relation, []).append(l.evidence_id)
        for (ttype, tid), rels in groups.items():
            sup = rels.get(REL_SUPPORTS, [])
            con = rels.get(REL_CONTRADICTS, [])
            if sup and con:
                out.append(Conflict(ttype, tid, sup, con))
        return out


def indirect_support_gate(evidence: ExternalEvidence, relation: str,
                          target_type: str, target_id: str) -> Optional[str]:
    """INDIRECT evidence may not 'support' formula/rule assumptions.

    Returns a rejection reason string, or None when allowed. Myfxbook
    performance can provide context or even contradiction, but never direct
    support for internal formula assumptions.
    """
    if relation != REL_SUPPORTS:
        return None
    quality = evidence.quality if evidence.quality != QUALITY_UNKNOWN         else evidence_quality(evidence.source_type)
    if quality != QUALITY_INDIRECT:
        return None
    if target_type == TARGET_ASSUMPTION and target_id in FORMULA_ASSUMPTION_IDS:
        return (f"INDIRECT evidence ({evidence.source_type}) cannot 'support' "
                f"formula/rule assumption {target_id} - use 'context_for' "
                f"instead. {MYFXBOOK_LIMITATION}")
    return None
