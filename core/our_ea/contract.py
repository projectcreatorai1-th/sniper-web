"""Frozen evidence contract + immutable model version (§3, §8).

The ONLY Analyzer artifact OUR EA reads:
    data/evidence_model/V1.68-EVIDENCE-MODEL-v1.0.json  (+ .sha256.txt)

Hash is verified on load; mismatch -> ModelContractError and execution
must stop (MASTER COMMAND §3, §40). The contract is never written to.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List

MODEL_ID = "V1.68-EVIDENCE-MODEL-v1.0"
_CONTRACT_RELPATH = os.path.join("data", "evidence_model",
                                 "V1.68-EVIDENCE-MODEL-v1.0.json")


class ModelContractError(RuntimeError):
    """Frozen contract missing / corrupted / hash mismatch -> STOP."""


@dataclass(frozen=True)
class ModelVersion:
    """Immutable model version binding (§8). Runtime cannot change it."""
    model_id: str
    model_hash: str

    def assert_matches(self, other: "ModelVersion") -> None:
        if (self.model_id, self.model_hash) != (other.model_id, other.model_hash):
            raise ModelVersionMismatch(self, other)


class ModelVersionMismatch(RuntimeError):
    def __init__(self, expected: ModelVersion, actual: ModelVersion):
        super().__init__(
            f"MODEL_VERSION_MISMATCH: expected {expected.model_id}"
            f"@{expected.model_hash[:12]}… got "
            f"{actual.model_id}@{actual.model_hash[:12]}…")


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_contract(repo_root: str = None) -> Dict[str, Any]:
    """Load + hash-verify the frozen evidence model (READ ONLY)."""
    root = repo_root or _repo_root()
    path = os.path.join(root, _CONTRACT_RELPATH)
    sidecar = path[:-len(".json")] + ".sha256.txt"
    if not os.path.exists(path) or not os.path.exists(sidecar):
        raise ModelContractError(f"frozen model missing: {path}")
    with open(path, "rb") as f:
        blob = f.read()
    actual = hashlib.sha256(blob).hexdigest().upper()
    expected = open(sidecar).read().strip().upper()
    if actual != expected:
        raise ModelContractError(
            f"FROZEN MODEL HASH MISMATCH: {actual[:16]}… != {expected[:16]}… — STOP")
    doc = json.loads(blob.decode("utf-8"))
    if doc.get("model_id") != MODEL_ID:
        raise ModelContractError(f"unexpected model_id: {doc.get('model_id')}")
    return doc


def contract_version(repo_root: str = None) -> ModelVersion:
    root = repo_root or _repo_root()
    load_contract(root)                     # verifies hash before binding
    return ModelVersion(model_id=MODEL_ID,
                        model_hash=_file_hash(os.path.join(root, _CONTRACT_RELPATH)))


def _file_hash(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest().upper()


def rules_from_contract(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(doc.get("rules", []))
