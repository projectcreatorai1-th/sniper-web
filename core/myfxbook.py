"""Myfxbook importer (Phase 3).

    URL -> Fetch -> Parse -> Validate -> Canonical ExternalEvidence
        -> Evidence Registry + EvidenceSnapshot

Honesty rules:
- network access is injectable (tests provide content; production fetches)
- inaccessible/unparseable sources report IMPORT_FAILED / IMPORT BLOCKED
  WITH the reason - no fallback data that looks real
- metrics are OBSERVED_EXTERNAL_METRIC (performance context), never
  internal EA rules
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from core.external_evidence import (
    EXTRACTION_FAILED,
    EXTRACTION_IMPORTED,
    EXTRACTION_PARTIAL,
    ExternalEvidence,
    ExternalEvidenceError,
    ExternalEvidenceStore,
    ExternalMetric,
    SRC_MYFXBOOK,
    content_hash,
    evidence_quality,
    metrics_hash,
)
from core.external_evidence import EvidenceSnapshot

USER_AGENT = ("Mozilla/5.0 (compatible; SNIPER-CashFlow-Analyzer/"
              "evidence-importer; +local verification tool)")

_METRIC_PATTERNS: Dict[str, List[str]] = {
    "balance": [r"Balance[^0-9\-]{0,40}([\d,]+\.?\d*)"],
    "equity": [r"Equity[^0-9\-]{0,40}([\d,]+\.?\d*)"],
    "profit": [r"(?:Total\s+)?Profit[^0-9\-]{0,40}(-?[\d,]+\.?\d*)"],
    "profit_factor": [r"Profit\s*Factor[^0-9\-]{0,40}([\d.]+)"],
    "drawdown": [r"(?:Max(?:imum)?\s+)?Drawdown[^0-9\-]{0,40}([\d.]+)%?"],
    "trades": [r"(?:Total\s+)?Trades?[^0-9]{0,30}([\d,]+)"],
    "lots": [r"Lots?[^0-9]{0,30}([\d.]+)"],
    "long_trades": [r"Long[^0-9]{0,20}trades?[^0-9]{0,20}([\d,]+)",
                    r"(?:Won|Win)[^0-9]{0,20}long[^0-9]{0,20}([\d,]+)"],
    "short_trades": [r"Short[^0-9]{0,20}trades?[^0-9]{0,20}([\d,]+)",
                     r"(?:Won|Win)[^0-9]{0,20}short[^0-9]{0,20}([\d,]+)"],
    "average_trade_duration": [r"Average\s+(?:Trade\s+)?Duration[^0-9]{0,60}([\ddhms :]+)"],
}

_ENV_PATTERNS: Dict[str, List[str]] = {
    "broker": [r"Broker[:\s]+([A-Za-z0-9 .&\-]+?)(?=\s+(?:Platform|Symbol|Timeframe|Broker|Currency|Balance|Equity|Profit|Drawdown|Trades|Lots|Period)\b|$|,)"],
    "platform": [r"Platform[:\s]+([A-Za-z0-9 .\-]+?)(?=\s+(?:Platform|Symbol|Timeframe|Broker|Currency|Balance|Equity|Profit|Drawdown|Trades|Lots|Period)\b|$|,)"],
    "symbol": [r"Symbol[:\s]+([A-Za-z0-9.+\-]+?)(?=\s+(?:Platform|Symbol|Timeframe|Broker|Currency|Balance|Equity|Profit|Drawdown|Trades|Lots|Period)\b|$|,)"],
    "timeframe": [r"Timeframe[:\s]+([A-Za-z0-9]+?)(?=\s+(?:Platform|Symbol|Timeframe|Broker|Currency|Balance|Equity|Profit|Drawdown|Trades|Lots|Period)\b|$|,)"],
    "currency": [r"Currency[:\s]+([A-Za-z]{3})"],
}


_PERIOD_PATTERNS = [
    (r"(\d{4}-\d{2}-\d{2})\s*(?:to|-|–)\s*(\d{4}-\d{2}-\d{2})",
     "%Y-%m-%d", "%Y-%m-%d"),
    (r"(\d{2}/\d{2}/\d{4})\s*(?:to|-|–)\s*(\d{2}/\d{2}/\d{4})",
     "%m/%d/%Y", "%m/%d/%Y"),
    (r"(\d{4}\.\d{2}\.\d{2})\s*(?:to|-|–)\s*(\d{4}\.\d{2}\.\d{2})",
     "%Y.%m.%d", "%Y.%m.%d"),
]


def normalize_myfxbook_url(url: str) -> str:
    """Normalize scheme/host variants while keeping the original traceable."""
    u = (url or "").strip()
    if not u:
        raise ExternalEvidenceError("empty URL")
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    u = re.sub(r"^http://", "https://", u, flags=re.I)
    u = re.sub(r"^(https://)(www\.)?myfxbook\.com", r"\1www.myfxbook.com", u, flags=re.I)
    if "myfxbook.com" not in u.lower():
        raise ExternalEvidenceError(
            f"not a myfxbook URL: {url}")
    u = u.split("#", 1)[0].rstrip("/")
    return u


def _num(text: str) -> Optional[float]:
    t = text.replace(",", "").replace("%", "").strip()
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _first_match(patterns: List[str], text: str) -> Optional[str]:
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1).strip()
    return None


def parse_myfxbook_html(html: str) -> Tuple[Dict[str, float], Dict[str, str],
                                            Optional[str], Optional[str], List[str]]:
    """Extract metrics/environment/period from page text.

    Returns (metrics, env_fields, period_start, period_end, warnings).
    Anything not found is simply absent (UNKNOWN) - never invented.
    """
    warnings: List[str] = []
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)

    metrics: Dict[str, float] = {}
    for key, patterns in _METRIC_PATTERNS.items():
        raw = _first_match(patterns, text)
        val = _num(raw) if raw else None
        if val is not None:
            metrics[key] = val
    missing = [k for k in _METRIC_PATTERNS if k not in metrics]
    if missing:
        warnings.append("metrics not found on page: " + ", ".join(missing))

    env: Dict[str, str] = {}
    for key, patterns in _ENV_PATTERNS.items():
        raw = _first_match(patterns, text)
        if raw:
            env[key] = raw

    period_start = period_end = None
    for pat, f1, f2 in _PERIOD_PATTERNS:
        m = re.search(pat, text)
        if m:
            from datetime import datetime as _dt
            try:
                period_start = _dt.strptime(m.group(1), f1).strftime("%Y-%m-%d")
                period_end = _dt.strptime(m.group(2), f2).strftime("%Y-%m-%d")
            except ValueError:
                pass
            break
    if period_start is None:
        warnings.append("period not found - stored as UNKNOWN")
    return metrics, env, period_start, period_end, warnings


def default_fetch(url: str, timeout: int = 20) -> bytes:
    """Real network fetch (production path). Raises on HTTP/network errors."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "text/html,application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(2 * 1024 * 1024)   # 2MB cap


class MyfxbookImporter:
    def __init__(self, store: Optional[ExternalEvidenceStore] = None,
                 fetch: Optional[Callable[[str], bytes]] = None):
        self.store = store or ExternalEvidenceStore()
        self._fetch = fetch or default_fetch

    @staticmethod
    def _failed(normalized: str, original: str, reason: str,
                raw: bytes = b"") -> dict:
        """IMPORT_FAILED with an honest reason - never fallback data."""
        result = {"status": "IMPORT_FAILED", "reason": reason,
                  "url": original, "normalized_url": normalized}
        if raw:
            result["content_hash"] = content_hash(raw)
        return result

    def import_url(self, url: str, notes: str = "") -> dict:
        """Fetch + parse + persist. Returns a result dict (never fake data)."""
        try:
            normalized = normalize_myfxbook_url(url)
        except ExternalEvidenceError as exc:
            return {"status": "IMPORT_FAILED", "reason": str(exc), "url": url}

        try:
            raw = self._fetch(normalized)
        except urllib.error.HTTPError as exc:
            return self._failed(normalized, url,
                                f"HTTP {exc.code} {exc.reason}")
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            return self._failed(normalized, url, f"network error: {exc}")

        try:
            html = raw.decode("utf-8", errors="replace")
        except Exception as exc:            # pragma: no cover - decode guard
            return self._failed(normalized, url, f"decode error: {exc}")

        metrics, env, p_start, p_end, warnings = parse_myfxbook_html(html)
        if not metrics:
            return self._failed(
                normalized, url,
                "no recognizable metrics on page (page may be "
                "JavaScript-rendered or non-public) - no data invented",
                raw=raw)

        retrieved_at = datetime.now().isoformat(timespec="seconds")
        chash = content_hash(raw)
        mhash = metrics_hash(metrics)

        # duplicate / evolved-content handling
        existing = self.store.find_by_url(normalized)
        unchanged = [e for e in existing
                     if self.store.snapshots_for(e.evidence_id)
                     and self.store.snapshots_for(e.evidence_id)[-1].content_hash == chash]
        if unchanged:
            ev = unchanged[0]
            snap = EvidenceSnapshot(
                snapshot_id=f"S-{ev.evidence_id}-{len(self.store.snapshots_for(ev.evidence_id)) + 1:03d}",
                evidence_id=ev.evidence_id, retrieved_at=retrieved_at,
                content_hash=chash, metrics_hash=mhash,
                notes="duplicate import - content unchanged")
            self.store.add_snapshot(snap)
            return {"status": "IMPORTED", "duplicate": True, "unchanged": True,
                    "evidence": ev.to_dict(), "snapshot": snap.to_dict(),
                    "warnings": warnings}

        seq = len(self.store.all()) + 1
        ev = ExternalEvidence(
            evidence_id=f"EX-MF-{seq:03d}-{chash[:8]}",
            source_type=SRC_MYFXBOOK,
            source_url=url, normalized_url=normalized,
            source_name="Myfxbook",
            retrieved_at=retrieved_at,
            broker=env.get("broker", ""),
            platform=env.get("platform", ""),
            symbol=env.get("symbol", ""),
            timeframe=env.get("timeframe", ""),
            period_start=p_start or "",
            period_end=p_end or "",
            raw_reference=f"snapshot content_hash {chash}",
            extracted_metrics=[ExternalMetric(key=k, value=v,
                                              period_start=p_start,
                                              period_end=p_end)
                               for k, v in sorted(metrics.items())],
            extraction_status=EXTRACTION_IMPORTED if not warnings
            else EXTRACTION_PARTIAL,
            confidence="LOW",
            notes=(notes + " " if notes else "") + MYFXBOOK_LIMITATION_SAFE,
            quality=evidence_quality(SRC_MYFXBOOK),
        )
        self.store.save(ev)
        for old in existing:               # content changed -> supersede
            self.store.mark_superseded(old.evidence_id, ev.evidence_id)
        snap = EvidenceSnapshot(
            snapshot_id=f"S-{ev.evidence_id}-001",
            evidence_id=ev.evidence_id, retrieved_at=retrieved_at,
            content_hash=chash, metrics_hash=mhash)
        self.store.add_snapshot(snap)
        return {"status": "IMPORTED", "duplicate": False, "unchanged": False,
                "evidence": ev.to_dict(), "snapshot": snap.to_dict(),
                "warnings": warnings}


MYFXBOOK_LIMITATION_SAFE = ("OBSERVED_EXTERNAL_METRIC - performance "
                            "observation only, not an internal EA rule.")


# ---------------------------------------------------------------------------
# Environment comparison (external vs observed)
# ---------------------------------------------------------------------------
from core.environment import observed_test_environment  # noqa: E402


def compare_environments(external: ExternalEvidence,
                         observed=None) -> dict:
    """Field-by-field MATCH / PARTIAL_MATCH / MISMATCH / UNKNOWN.

    Different broker/platform means DIFFERENT environments - never assumed
    equal. Empty external fields are UNKNOWN, never guessed.
    """
    obs = observed or observed_test_environment()
    fields = {
        "platform": (external.platform, obs.platform),
        "broker": (external.broker, obs.broker),
        "symbol": (external.symbol, obs.symbol),
        "account_type": (external.account_type, obs.account_type),
        "timeframe": (external.timeframe, obs.timeframe),
    }
    rows = []
    for name, (ext, ob) in fields.items():
        ext = (ext or "").strip()
        ob = (ob or "").strip()
        if not ext:
            status = "UNKNOWN"
        elif ext.lower() == ob.lower():
            status = "MATCH"
        elif ext.lower() in ob.lower() or ob.lower() in ext.lower():
            status = "PARTIAL_MATCH"
        else:
            status = "MISMATCH"
        rows.append({"field": name, "external": ext or "UNKNOWN",
                     "observed": ob or "UNKNOWN", "status": status})
    if external.leverage is not None if hasattr(external, "leverage") else False:
        pass
    counts = {s: sum(1 for r in rows if r["status"] == s)
              for s in ("MATCH", "PARTIAL_MATCH", "MISMATCH", "UNKNOWN")}
    if counts["MISMATCH"]:
        overall = "MISMATCH"
    elif counts["MATCH"] and not counts["UNKNOWN"] and not counts["PARTIAL_MATCH"]:
        overall = "MATCH"
    elif counts["MATCH"] or counts["PARTIAL_MATCH"]:
        overall = "PARTIAL_MATCH"
    else:
        overall = "UNKNOWN"
    return {"schema": "SNIPER_ENV_COMPARISON_V1",
            "overall": overall, "counts": counts, "rows": rows,
            "note": ("Separate accounts keep separate environments; "
                     "differences are reported, never assumed away.")}
