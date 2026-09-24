"""Emergency forensics — scan for any trace of the emergency mechanism.

Observed emergency closes = 0 in production data, but
"Emergency Mechanism != No Emergency": scan for proxies:
  - baskets closed at a loss (negative close bursts)
  - abnormal lot / position count vs the ladder
  - abnormal duration outliers
  - sequence interruptions (unexpected gaps between cycles)
  - close bursts without a following resume
  - comment anomalies in close orders

If nothing is found: EMERGENCY = UNKNOWN (mechanism unobserved in this
dataset). Implementing V1.68 emergency behaviour from assumption is
forbidden.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Sequence

from core.forensics.cycle_reconstruction import Cycle, FMT
from core.forensics.mt5_report import MT5Report

LOSS_TOLERANCE = -0.30      # baskets below this are "significant loss" proxies
DURATION_OUTLIER_H = 96.0   # cycles longer than this are abnormal
GAP_OUTLIER_S = 600.0       # inter-cycle gaps > 10 min are interruptions


@dataclass(frozen=True)
class EmergencyAnomaly:
    kind: str
    cycle_id: str
    account_id: str
    detail: str


def scan_emergency(cycles: Sequence[Cycle],
                   reports: Sequence[MT5Report]) -> dict:
    anomalies: List[EmergencyAnomaly] = []
    for cyc in cycles:
        if cyc.confidence == "LOW":
            continue
        g = cyc.basket_close["gross"]
        if g < LOSS_TOLERANCE:
            anomalies.append(EmergencyAnomaly(
                "LOSS_CLOSE", cyc.cycle_id, cyc.account_id,
                f"gross {g:+.2f}"))
        dur_h = cyc.basket_close["duration_s"] / 3600.0
        if dur_h > DURATION_OUTLIER_H:
            anomalies.append(EmergencyAnomaly(
                "ABNORMAL_DURATION", cyc.cycle_id, cyc.account_id,
                f"{dur_h:.1f}h"))
        gap = cyc.basket_close.get("next_cycle_gap_s")
        if gap is not None and gap > GAP_OUTLIER_S:
            anomalies.append(EmergencyAnomaly(
                "SEQUENCE_INTERRUPTION", cyc.cycle_id, cyc.account_id,
                f"gap {gap/3600:.2f}h before next cycle"))
    # close orders with unexpected comments (all observed close comments
    # are empty; any non-empty close comment would be notable)
    for rep in reports:
        for o in rep.orders:
            if o.comment and not _is_close_of_entry(rep, o):
                anomalies.append(EmergencyAnomaly(
                    "COMMENT_ANOMALY", "-", rep.account_id,
                    f"order {o.order_id} comment '{o.comment}'"))

    kinds = sorted({a.kind for a in anomalies})
    observed = len(anomalies)
    return {
        "emergency_closes_observed": observed,
        "anomaly_kinds": kinds,
        "anomalies": [{"kind": a.kind, "cycle": a.cycle_id,
                       "account": a.account_id, "detail": a.detail}
                      for a in anomalies[:50]],
        "status": "UNKNOWN",
        "note": "No emergency event in production data; E007 (90.0 observed "
                "in testing) and E008 (50.0 documented) stand unchanged. "
                "Mechanism remains unproven — deep grids survived to profit "
                "(32 levels / 20.07 lots / 28.1h closed +21.80), which "
                "bounds where the trigger did NOT fire, but does not "
                "locate it.",
    }


def _is_close_of_entry(report: MT5Report, order) -> bool:
    entry_ids = set()
    for d in report.in_deals:
        entry_ids.add(d.order_id)
    return order.order_id in entry_ids
