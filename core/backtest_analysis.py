"""Backtest Analyzer (Module 7).

Analyzes an imported BacktestSummary (when deal data is available) and
reports performance/risk/drawdown/trade statistics plus grid-specific
metrics: max grid depth, max lot, floating-style drawdown and worst losing
cycle from the balance series.

No predictions about future performance are produced - descriptive
statistics only. Fields without underlying data report None -> N/A.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

from core.backtest_io import BacktestSummary, DealRecord

_DT_FORMATS = ("%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M:%S",
               "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M")


def _parse_dt(s: str) -> Optional[datetime]:
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


@dataclass
class DrawdownEpisode:
    peak_time: str
    trough_time: str
    recovery_time: Optional[str]
    peak_balance: float
    trough_balance: float
    depth: float
    depth_percent: float
    duration_label: str

    def to_dict(self) -> dict:
        return {
            "peak_time": self.peak_time, "trough_time": self.trough_time,
            "recovery_time": self.recovery_time,
            "peak_balance": self.peak_balance, "trough_balance": self.trough_balance,
            "depth": round(self.depth, 2), "depth_percent": round(self.depth_percent, 4),
            "duration_label": self.duration_label,
        }


@dataclass
class BacktestAnalysis:
    has_deal_data: bool
    # trade statistics
    total_deals: Optional[int] = None
    entry_deals: Optional[int] = None
    exit_deals: Optional[int] = None
    # lot statistics
    max_lot: Optional[float] = None
    avg_lot: Optional[float] = None
    total_volume: Optional[float] = None
    # grid depth (max simultaneous open positions)
    max_grid_depth_total: Optional[int] = None
    max_grid_depth_buy: Optional[int] = None
    max_grid_depth_sell: Optional[int] = None
    # drawdown / worst period
    max_drawdown_episode: Optional[DrawdownEpisode] = None
    longest_recovery_episode: Optional[DrawdownEpisode] = None
    worst_losing_streak_deals: Optional[int] = None
    worst_losing_streak_amount: Optional[float] = None
    # equity curve (balance after each deal) when available
    balance_curve: List[float] = field(default_factory=list)
    curve_labels: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "has_deal_data": self.has_deal_data,
            "total_deals": self.total_deals,
            "entry_deals": self.entry_deals,
            "exit_deals": self.exit_deals,
            "max_lot": self.max_lot,
            "avg_lot": round(self.avg_lot, 4) if self.avg_lot is not None else None,
            "total_volume": round(self.total_volume, 4) if self.total_volume is not None else None,
            "max_grid_depth_total": self.max_grid_depth_total,
            "max_grid_depth_buy": self.max_grid_depth_buy,
            "max_grid_depth_sell": self.max_grid_depth_sell,
            "max_drawdown_episode": self.max_drawdown_episode.to_dict() if self.max_drawdown_episode else None,
            "longest_recovery_episode": self.longest_recovery_episode.to_dict() if self.longest_recovery_episode else None,
            "worst_losing_streak_deals": self.worst_losing_streak_deals,
            "worst_losing_streak_amount": self.worst_losing_streak_amount,
            "balance_curve": self.balance_curve,
            "curve_labels": self.curve_labels,
            "notes": self.notes,
        }
        return d


def analyze_backtest(summary: BacktestSummary) -> BacktestAnalysis:
    analysis = BacktestAnalysis(has_deal_data=bool(summary.deals))
    if not summary.deals:
        analysis.notes.append("No deal-level data imported - grid depth / lot statistics "
                              "need a deals CSV or an HTML report containing the Deals table (N/A).")
        analysis.balance_curve = list(summary.balance_curve)
        return analysis

    deals: List[DealRecord] = summary.deals
    analysis.total_deals = len(deals)
    entries = [d for d in deals if d.type in ("buy", "sell") and d.direction in ("in", "inout")]
    exits = [d for d in deals if d.type in ("buy", "sell") and d.direction in ("out", "inout")]
    analysis.entry_deals = len(entries)
    analysis.exit_deals = len(exits)

    vols = [d.volume for d in entries if d.volume > 0]
    if vols:
        analysis.max_lot = round(max(vols), 4)
        analysis.avg_lot = round(sum(vols) / len(vols), 4)
        analysis.total_volume = round(sum(vols), 4)

    # --- grid depth: track open position count from in/out deals -----------
    open_total = 0
    open_buy = 0
    open_sell = 0
    max_total = max_buy = max_sell = 0
    for d in deals:
        if d.type not in ("buy", "sell"):
            continue
        if d.direction == "in":
            open_total += 1
            if d.type == "buy":
                open_buy += 1
            else:
                open_sell += 1
        elif d.direction == "out":
            open_total = max(open_total - 1, 0)
            if d.type == "buy":
                open_buy = max(open_buy - 1, 0)
            else:
                open_sell = max(open_sell - 1, 0)
        max_total = max(max_total, open_total)
        max_buy = max(max_buy, open_buy)
        max_sell = max(max_sell, open_sell)
    analysis.max_grid_depth_total = max_total
    analysis.max_grid_depth_buy = max_buy
    analysis.max_grid_depth_sell = max_sell
    if max_total == 0 and entries:
        analysis.notes.append("Grid depth could not be tracked (direction column missing "
                              "or not recognized) - showing N/A confidence note")

    # --- balance drawdown episodes ------------------------------------------
    bal_deals = [(d.time, d.balance) for d in deals if d.balance is not None]
    if len(bal_deals) >= 2:
        peak_val, peak_time = bal_deals[0][1], bal_deals[0][0]
        cur: Optional[DrawdownEpisode] = None
        deepest: Optional[DrawdownEpisode] = None
        longest: Optional[DrawdownEpisode] = None

        def finish(ep: DrawdownEpisode, recovered_at: Optional[str]) -> DrawdownEpisode:
            ep.recovery_time = recovered_at
            start, end = recovered_at or ep.trough_time, ep.peak_time
            dt_s, dt_e = _parse_dt(ep.peak_time), _parse_dt(end)
            if dt_s and dt_e:
                mins = (dt_e - dt_s).total_seconds() / 60.0
                ep.duration_label = f"{mins:.0f} min ({ep.peak_time} -> {end})"
            else:
                ep.duration_label = f"{ep.peak_time} -> {end}"
            return ep

        for t, b in bal_deals[1:]:
            if b >= peak_val:
                if cur is not None:
                    cur = finish(cur, t)
                    if deepest is None or cur.depth > deepest.depth:
                        deepest = cur
                    if longest is None or _episode_minutes(cur) > _episode_minutes(longest):
                        longest = cur
                    cur = None
                peak_val, peak_time = b, t
            else:
                if cur is None:
                    cur = DrawdownEpisode(peak_time, t, None, peak_val, b,
                                          peak_val - b,
                                          (peak_val - b) / peak_val * 100 if peak_val else 0,
                                          f"{peak_time} -> {t}")
                else:
                    if b < cur.trough_balance:
                        cur.trough_balance = b
                        cur.trough_time = t
                    # depth is peak-to-TROUGH (deepest point), independent of
                    # any later partial recovery within the same episode
                    cur.depth = cur.peak_balance - cur.trough_balance
                    cur.depth_percent = (cur.depth / cur.peak_balance * 100
                                         if cur.peak_balance else 0)
        if cur is not None:  # episode never recovered within the report
            cur = finish(cur, None)
            if deepest is None or cur.depth > deepest.depth:
                deepest = cur
            if longest is None or _episode_minutes(cur) > _episode_minutes(longest):
                longest = cur
        analysis.max_drawdown_episode = deepest
        analysis.longest_recovery_episode = longest
        analysis.balance_curve = [b for _, b in bal_deals]
        analysis.curve_labels = [t for t, _ in bal_deals]
    else:
        analysis.notes.append("Balance column unavailable - drawdown episodes N/A")

    # --- losing streak ------------------------------------------------------
    profits = [(d.profit + d.commission + d.swap) for d in exits]
    if profits:
        streak_count, streak_sum = 0, 0.0
        worst_count, worst_sum = 0, 0.0
        for p in profits:
            if p < 0:
                streak_count += 1
                streak_sum += p
                if streak_count > worst_count or (streak_count == worst_count and streak_sum < worst_sum):
                    worst_count, worst_sum = streak_count, streak_sum
            else:
                streak_count, streak_sum = 0, 0.0
        analysis.worst_losing_streak_deals = worst_count or None
        analysis.worst_losing_streak_amount = round(worst_sum, 2) if worst_count else None

    return analysis


def _episode_minutes(ep: DrawdownEpisode) -> float:
    """Episode duration in minutes; -1 when timestamps are not parseable."""
    start = _parse_dt(ep.peak_time)
    end = _parse_dt(ep.recovery_time or ep.trough_time)
    if start is None or end is None:
        return -1.0
    return (end - start).total_seconds() / 60.0
