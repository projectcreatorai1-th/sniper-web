"""SNIPER Analyzer Gateway Client — signal builder + evidence package (§7, §15).

Builds Signal objects from SNIPER analysis results with full provenance
(strategy version, dataset version, backtest reference, evidence hash).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.gateway.contracts import (
    EvidencePackage, Signal, new_id, utc_now_iso, canonical_hash)


def build_signal(
    strategy_id: str = "SNIPER-V168",
    strategy_version: str = "1.0",
    symbol: str = "GOLDmicro",
    timeframe: str = "M15",
    direction: str = "NEUTRAL",
    signal_type: str = "ANALYSIS",
    entry_reference: float = 0.0,
    stop_reference: float = 0.0,
    target_reference: float = 0.0,
    confidence: float = 0.0,
    analysis_version: str = "V1.68-EVIDENCE-MODEL-v1.0",
    dataset_version: str = "replay_dataset_v1",
    backtest_id: str = "",
    evidence_id: str = "",
    evidence_hash: str = "",
    expires_seconds: int = 3600,
    correlation_id: str = "",
) -> Signal:
    from datetime import datetime, timedelta, timezone
    created = utc_now_iso()
    expires = (datetime.now(timezone.utc) +
               timedelta(seconds=expires_seconds)).isoformat(
        timespec="milliseconds")
    return Signal(
        signal_id=new_id("SIG"),
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        symbol=symbol,
        timeframe=timeframe,
        direction=direction,
        signal_type=signal_type,
        entry_reference=entry_reference,
        stop_reference=stop_reference,
        target_reference=target_reference,
        confidence=confidence,
        created_at=created,
        expires_at=expires,
        analysis_version=analysis_version,
        dataset_version=dataset_version,
        backtest_id=backtest_id,
        evidence_id=evidence_id,
        evidence_hash=evidence_hash,
        correlation_id=correlation_id or new_id("COR"))


def build_evidence_package(
    signal: Signal,
    analysis_id: str = "",
    dataset_id: str = "replay_dataset_v1",
    metrics: Optional[Dict[str, Any]] = None,
    parameters: Optional[Dict[str, Any]] = None,
) -> EvidencePackage:
    metrics = metrics or {}
    parameters = parameters or {}
    evidence = EvidencePackage(
        signal_id=signal.signal_id,
        analysis_id=analysis_id or new_id("ANL"),
        strategy_id=signal.strategy_id,
        strategy_version=signal.strategy_version,
        dataset_id=dataset_id,
        dataset_version=signal.dataset_version,
        backtest_id=signal.backtest_id,
        metrics=metrics,
        parameters=parameters,
        created_at=utc_now_iso(),
        evidence_hash="")
    # evidence hash over the full package
    d = evidence.to_dict()
    d.pop("evidence_hash")
    return EvidencePackage(
        signal_id=evidence.signal_id,
        analysis_id=evidence.analysis_id,
        strategy_id=evidence.strategy_id,
        strategy_version=evidence.strategy_version,
        dataset_id=evidence.dataset_id,
        dataset_version=evidence.dataset_version,
        backtest_id=evidence.backtest_id,
        metrics=evidence.metrics,
        parameters=evidence.parameters,
        created_at=evidence.created_at,
        evidence_hash=canonical_hash(d))
