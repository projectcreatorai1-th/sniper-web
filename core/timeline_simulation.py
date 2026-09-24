"""Timeline Simulator (Phase 4): price-time simulation built on the SAME core.

    Price Series + Model Version + Parameters + Environment
        -> TimelineEventEngine -> Canonical Events -> Timelines

Honesty rules:
- every event carries assumption_ids and a MODEL ASSUMPTION label — the
  simulator NEVER presents model rules as verified EA behavior
- synthetic scenarios are labeled SYNTHETIC / TEST DATA and can never enter
  the Evidence Registry
- all numbers come from core.calculations (SSOT); this module orchestrates
- simulations are immutable once stored: the model version and parameters
  are snapshotted at creation time
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core import calculations as c
from core.config import EAConfig
from core.model_rules import SimulationModelRules
from core.symbol_profile import SymbolProfile, AccountSettings

SCHEMA = "SNIPER_TIMELINE_SIMULATION_V1"
TRACE_SCHEMA = "SNIPER_SIMULATION_TRACE_V1"

# statuses
READY = "READY"
RUNNING = "RUNNING"
COMPLETE = "COMPLETE"
INCOMPLETE = "INCOMPLETE"
ERROR = "ERROR"
SIM_STATUSES = (READY, RUNNING, COMPLETE, INCOMPLETE, ERROR)

# input modes
OBSERVED_SERIES = "OBSERVED_SERIES"
SYNTHETIC_SERIES = "SYNTHETIC_SERIES"
SCENARIO = "SCENARIO"
INPUT_MODES = (OBSERVED_SERIES, SYNTHETIC_SERIES, SCENARIO)

# scenario presets (all SYNTHETIC)
SCENARIO_UP = "NORMAL_UP"
SCENARIO_DOWN = "NORMAL_DOWN"
SCENARIO_RANGE = "RANGE"
SCENARIO_LONG_DECLINE = "LONG_DECLINE"
SCENARIO_LONG_RISE = "LONG_RISE"
SCENARIO_SHARP_REVERSAL = "SHARP_REVERSAL"
SCENARIO_V_SHAPE = "V_SHAPE"
SCENARIO_GAP_DOWN = "GAP_DOWN"
SCENARIO_GAP_UP = "GAP_UP"
SCENARIOS = (SCENARIO_UP, SCENARIO_DOWN, SCENARIO_RANGE, SCENARIO_LONG_DECLINE,
             SCENARIO_LONG_RISE, SCENARIO_SHARP_REVERSAL, SCENARIO_V_SHAPE,
             SCENARIO_GAP_DOWN, SCENARIO_GAP_UP)

SYNTHETIC_LABEL = "SYNTHETIC / TEST DATA"

# assumption bundles attached to every simulated event
SIM_ASSUMPTIONS = [
    "LOT_FORMULA_ASSUMPTION_001",
    "LOT_NORMALIZATION_ASSUMPTION_001",
    "GRID_TRIGGER_ASSUMPTION_001",
    "GRID_DIRECTION_ASSUMPTION_001",
    "BASKET_CLOSE_DOC_001",
    "PARTIAL_CLOSE_ASSUMPTION_001",
    "PL_CONVERSION_ASSUMPTION_001",
    "MARGIN_ASSUMPTION_001",
]

UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Price series
# ---------------------------------------------------------------------------
@dataclass
class PriceBar:
    timestamp: str
    mid: float
    bid: Optional[float] = None      # None = UNKNOWN (never fabricated)
    ask: Optional[float] = None
    spread: Optional[float] = None   # derived ONLY when bid+ask exist

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PriceBar":
        return cls(timestamp=d.get("timestamp", ""),
                   mid=float(d.get("mid", 0)),
                   bid=d.get("bid"), ask=d.get("ask"), spread=d.get("spread"))


def make_bar(timestamp: str, price: float, bid: Optional[float] = None,
             ask: Optional[float] = None) -> PriceBar:
    spread = round(ask - bid, 10) if (bid is not None and ask is not None) else None
    mid = price if bid is None or ask is None else (bid + ask) / 2
    return PriceBar(timestamp, mid, bid, ask, spread)


def observed_series(timestamps: List[str], prices: List[float]) -> List[PriceBar]:
    """Build an OBSERVED series from single prices: bid/ask/spread UNKNOWN."""
    return [make_bar(ts, p) for ts, p in zip(timestamps, prices)]


# ---------------------------------------------------------------------------
# Scenario engine (SYNTHETIC only)
# ---------------------------------------------------------------------------
def generate_scenario(scenario: str, start_price: float, bars: int = 60,
                      step: float = 1.0, start_time: str = "2026-01-02 10:00:00",
                      interval_seconds: int = 300) -> List[PriceBar]:
    """Generate a SYNTHETIC price path. Labeled SYNTHETIC — never evidence."""
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario}")
    t0 = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    out: List[PriceBar] = []

    def ts(i: int) -> str:
        return (t0 + timedelta(seconds=i * interval_seconds)).strftime(
            "%Y-%m-%d %H:%M:%S")

    for i in range(bars):
        p = start_price
        frac = i / max(bars - 1, 1)
        if scenario == SCENARIO_UP:
            p = start_price + i * step
        elif scenario == SCENARIO_DOWN:
            p = start_price - i * step
        elif scenario == SCENARIO_RANGE:
            p = start_price + step * math.sin(i * 0.5) * 2
        elif scenario == SCENARIO_LONG_DECLINE:
            p = start_price - i * step * 0.5
        elif scenario == SCENARIO_LONG_RISE:
            p = start_price + i * step * 0.5
        elif scenario == SCENARIO_SHARP_REVERSAL:
            p = start_price + (i * step if i < bars // 2 else
                               (bars // 2) * step - (i - bars // 2) * step * 3)
        elif scenario == SCENARIO_V_SHAPE:
            p = start_price - (i * step if i < bars // 2 else
                               -(bars // 2) * step + (i - bars // 2) * step)
            p = start_price - (bars // 2) * step + abs(i - bars // 2) * step \
                if i >= bars // 2 else start_price - i * step
        elif scenario == SCENARIO_GAP_DOWN:
            p = start_price - (i * step * 0.2 if i < bars // 3 else
                               i * step * 0.2 + step * 30)
        elif scenario == SCENARIO_GAP_UP:
            p = start_price + (i * step * 0.2 if i < bars // 3 else
                               i * step * 0.2 + step * 30)
        out.append(make_bar(ts(i), round(p, 6)))
    return out


# ---------------------------------------------------------------------------
# Events / timelines
# ---------------------------------------------------------------------------
@dataclass
class SimEvent:
    timestamp: str
    event: str                  # CYCLE_START/ENTRY/GRID/PARTIAL/BASKET_CLOSE/EMERGENCY/CYCLE_END
    side: str = ""
    level: Optional[int] = None
    lot: Optional[float] = None
    price: Optional[float] = None
    distance_from_reference: Optional[float] = None
    floating_pnl: Optional[float] = None
    price_pnl: Optional[float] = None
    commission: Optional[float] = None
    swap: Optional[float] = None
    spread_cost: Optional[float] = None
    net_pnl: Optional[float] = None
    total_lots: Optional[float] = None
    position_count: Optional[int] = None
    cumulative_lot: Optional[float] = None
    equity: Optional[float] = None
    margin: Optional[float] = None
    free_margin: Optional[float] = None
    margin_level: Optional[float] = None
    exposure: Optional[float] = None
    drawdown: Optional[float] = None
    cycle_id: str = ""
    assumption_ids: List[str] = field(default_factory=lambda: list(SIM_ASSUMPTIONS))
    label: str = "MODEL ASSUMPTION"

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Timeline Simulation
# ---------------------------------------------------------------------------
@dataclass
class TimelineSimulation:
    simulation_id: str = ""
    symbol: str = ""
    timeframe: str = ""
    start_time: str = ""
    end_time: str = ""
    initial_price: float = 0.0
    price_series: List[PriceBar] = field(default_factory=list)
    parameters: Dict[str, object] = field(default_factory=dict)
    environment_profile_id: str = ""
    model_version: str = ""
    cycle_id: str = ""
    events: List[SimEvent] = field(default_factory=list)
    status: str = READY
    input_mode: str = SCENARIO
    synthetic: bool = True
    created_at: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = SCHEMA
        d["price_series"] = [b.to_dict() for b in self.price_series]
        d["events"] = [e.to_dict() for e in self.events]
        return d


# ---------------------------------------------------------------------------
# TimelineEventEngine — orchestrates core.calculations over a price path
# ---------------------------------------------------------------------------
class TimelineEventEngine:
    """Walks the price series and emits canonical events using ONLY
    core.calculations formulas. Every event is labeled MODEL ASSUMPTION."""

    def __init__(self, config: EAConfig, profile: SymbolProfile,
                 account: AccountSettings, rules: SimulationModelRules,
                 capital: float = 500.0):
        self.config = config
        self.profile = profile
        self.account = account
        self.rules = rules
        self.capital = capital

    def run(self, series: List[PriceBar], side: str = "BUY") -> List[SimEvent]:
        cfg, prof, acct = self.config, self.profile, self.account
        events: List[SimEvent] = []
        if not series:
            return events

        p0 = series[0].mid
        cycle = 0
        positions: List[tuple] = []        # (side, entry, lot)
        levels = 0
        ref_price = p0
        partial_done = False
        realized = 0.0
        equity0 = self.capital

        def snapshot(ts: str, ev: str, price: float, **kw) -> SimEvent:
            lots = sum(l for _, _, l in positions)
            pl = c.basket_pl(positions, price, prof)
            equity = equity0 + realized + pl
            margin = sum(c.margin_used(l, e, prof, acct) for _, e, l in positions)
            exposure = sum(c.notional_exposure(l, e, prof) for _, e, l in positions)
            defaults = {"price_pnl": round(pl, 2),
                        "commission": None, "swap": None,
                        "spread_cost": None, "net_pnl": None}
            defaults.update(kw)
            e = SimEvent(
                timestamp=ts, event=ev, side=side, price=price,
                floating_pnl=round(pl, 2),
                total_lots=round(lots, 4),
                position_count=len(positions),
                equity=round(equity, 2),
                margin=round(margin, 2),
                free_margin=round(equity - margin, 2),
                margin_level=round(equity / margin * 100, 2) if margin > 0 else None,
                exposure=round(exposure, 2),
                drawdown=round(c.drawdown_percent(pl, self.capital), 4),
                cycle_id=f"SIM-C{cycle}",
                **defaults)
            return e

        for bar in series:
            price = bar.mid
            # --- cycle start / first entry ---------------------------------
            if levels == 0:
                cycle += 1
                events.append(snapshot(bar.timestamp, "CYCLE_START", price,
                                       level=0, distance_from_reference=0.0))
                lot = c.lot_for_level(cfg, 1, self.rules, prof).value
                positions = [(side, p0, lot)]
                levels = 1
                ref_price = p0
                partial_done = False
                events.append(snapshot(bar.timestamp, "ENTRY", price,
                                       level=1, lot=lot,
                                       cumulative_lot=round(lot, 4),
                                       distance_from_reference=0.0))
                continue

            # --- basket close check ----------------------------------------
            pl = c.basket_pl(positions, price, prof)
            if cfg.UseBasketCloseAll and pl >= cfg.BasketCloseAllUSD:
                events.append(snapshot(bar.timestamp, "BASKET_CLOSE", price,
                                       level=levels))
                events.append(snapshot(bar.timestamp, "CYCLE_END", price,
                                       level=0))
                realized += pl
                positions = []
                levels = 0
                continue

            # --- partial close check ---------------------------------------
            if (cfg.UseProfitPartialClose and not partial_done
                    and pl >= cfg.ProfitPartialTriggerUSD):
                closed = c.partial_close_volume(
                    sum(l for _, _, l in positions), cfg.ProfitPartialPercent, prof)
                events.append(snapshot(
                    bar.timestamp, "PARTIAL", price, level=levels,
                    lot=round(closed, 4)))
                partial_done = True
                # model: pro-rata volume reduction (positions scaled down)
                positions = [(s, e, round(l * (1 - cfg.ProfitPartialPercent / 100), 8))
                             for s, e, l in positions]

            # --- emergency check -------------------------------------------
            adverse = abs(price - ref_price)
            if cfg.EnableEmergencyStop and adverse > cfg.EmergencyDistanceFromCycleUSD:
                events.append(snapshot(bar.timestamp, "EMERGENCY", price,
                                       level=levels,
                                       distance_from_reference=round(adverse, 2)))
                events.append(snapshot(bar.timestamp, "CYCLE_END", price, level=0))
                positions = []
                levels = 0
                continue

            # --- grid add check --------------------------------------------
            sign = -1 if side == "BUY" else 1
            last_entry = max((e for s, e, _ in positions), key=abs) \
                if side == "SELL" else min(e for _, e, _ in positions)
            dist_from_last = (last_entry - price) if side == "BUY" else (price - last_entry)
            if dist_from_last >= cfg.GridStepUSD:
                levels += 1
                lot = c.lot_for_level(cfg, levels, self.rules, prof).value
                entry = c.entry_price_for_level(p0, levels, side, cfg.GridStepUSD)
                positions.append((side, entry, lot))
                cum = round(sum(l for _, _, l in positions), 4)
                events.append(snapshot(
                    bar.timestamp, "GRID", price, level=levels, lot=lot,
                    cumulative_lot=cum,
                    distance_from_reference=round(abs(price - ref_price), 2)))

        # stream ended with an open cycle -> INCOMPLETE
        return events


def simulate_timeline(config: EAConfig, profile: SymbolProfile,
                       account: AccountSettings, rules: SimulationModelRules,
                       series: List[PriceBar], side: str = "BUY",
                       capital: float = 500.0,
                       input_mode: str = SCENARIO,
                       simulation_id: str = "",
                       environment_profile_id: str = "") -> TimelineSimulation:
    from datetime import datetime as _dt
    sim = TimelineSimulation(
        simulation_id=simulation_id or ("SIM-" + _dt.now().strftime("%Y%m%d%H%M%S")),
        symbol=profile.name, timeframe="",
        start_time=series[0].timestamp if series else "",
        end_time=series[-1].timestamp if series else "",
        initial_price=series[0].mid if series else 0.0,
        price_series=series,
        parameters=config.to_dict(),
        environment_profile_id=environment_profile_id,
        model_version=rules.model_version,
        input_mode=input_mode,
        synthetic=input_mode != OBSERVED_SERIES,
        created_at=_dt.now().isoformat(timespec="seconds"),
        notes=(SYNTHETIC_LABEL + " — scenario input, NOT observed evidence"
               if input_mode != OBSERVED_SERIES else
               "observed series input"))
    engine = TimelineEventEngine(config, profile, account, rules, capital)
    sim.events = engine.run(series, side)
    has_end = any(e.event == "CYCLE_END" for e in sim.events)
    sim.status = COMPLETE if has_end else INCOMPLETE
    return sim


# ---------------------------------------------------------------------------
# Worst Case timeline (SSOT preserved — this is a visualization layer)
# ---------------------------------------------------------------------------
def worst_case_timeline(config: EAConfig, profile: SymbolProfile,
                        account: AccountSettings, rules: SimulationModelRules,
                        capital: float, adverse_move: float,
                        scenario: str = "BOTH_SIDES",
                        start_price: Optional[float] = None) -> dict:
    """Build a timeline VIEW from the existing worst-case engine (SSOT)."""
    from core.worst_case import simulate_worst_case
    r = simulate_worst_case(config, profile, account, rules, capital,
                            adverse_move, scenario, start_price)
    p0 = r.end_price + adverse_move if scenario == "BUY_ADVERSE" else \
         r.end_price - adverse_move if scenario == "SELL_ADVERSE" else \
         (start_price or profile.reference_price)
    events = []
    positions, _ = c.build_side_positions(config, "BUY", p0,
                                          r.grid_levels, rules, profile)
    for i, (side, entry, lot) in enumerate(positions, start=1):
        events.append(SimEvent(
            timestamp=f"t+{(i - 1) * 5}m", event="ENTRY" if i == 1 else "GRID",
            side=side, level=i, lot=lot, price=entry,
            distance_from_reference=round((i - 1) * config.GridStepUSD, 2),
            cumulative_lot=round(sum(l for _, _, l in positions[:i]), 4),
            total_lots=r.total_lots, cycle_id="WC-C1").to_dict())
    events.append(SimEvent(
        timestamp=f"t+{(r.grid_levels - 1) * 5}m", event="FLOATING_SNAPSHOT",
        side="BOTH" if scenario == "BOTH_SIDES" else "", level=r.grid_levels,
        price=r.end_price, floating_pnl=r.floating_pl,
        equity=r.equity, margin=r.estimated_margin_used,
        drawdown=r.drawdown_pct, cycle_id="WC-C1").to_dict())
    return {
        "schema": "SNIPER_WORST_CASE_TIMELINE_V1",
        "summary": r.to_dict(),
        "events": events,
        "note": ("Timeline is a visualization layer over the ORIGINAL worst-case "
                 "engine (SSOT unchanged — regression pins intact)"),
        "label": "MODEL ASSUMPTION",
    }


# ---------------------------------------------------------------------------
# Simulation trace
# ---------------------------------------------------------------------------
@dataclass
class SimulationTrace:
    simulation_id: str
    model_version: str
    assumption_ids: List[str]
    evidence_ids: List[str]
    parameter_snapshot: Dict[str, object]
    environment_profile: str
    created_at: str
    input_mode: str = SCENARIO
    synthetic: bool = True

    def to_dict(self) -> dict:
        d = asdict(self)
        d["schema"] = TRACE_SCHEMA
        return d


def build_trace(sim: TimelineSimulation,
                evidence_ids: Optional[List[str]] = None) -> SimulationTrace:
    return SimulationTrace(
        simulation_id=sim.simulation_id,
        model_version=sim.model_version,
        assumption_ids=list(SIM_ASSUMPTIONS),
        evidence_ids=evidence_ids or [],
        parameter_snapshot=dict(sim.parameters),
        environment_profile=sim.environment_profile_id,
        created_at=sim.created_at,
        input_mode=sim.input_mode,
        synthetic=sim.synthetic)


# ---------------------------------------------------------------------------
# Model vs Simulation vs Observed comparator
# ---------------------------------------------------------------------------
def compare_model_simulation(records: List, sim: TimelineSimulation,
                             config: EAConfig, profile: SymbolProfile,
                             rules: SimulationModelRules) -> dict:
    """Three-way comparison per grid level. Simulation following the model is
    EXPECTED (same formulas) — it is never written as VERIFIED."""
    rows = []
    sim_grids = [e for e in sim.events if e.event in ("ENTRY", "GRID")]
    observed_entries = [r for r in records
                        if r.event in ("OPEN_POSITION", "ADD_GRID")] if records else []

    for i, ev in enumerate(sim_grids, start=1):
        model_lot = c.lot_for_level(config, i, rules, profile).value
        model_dist = (i - 1) * config.GridStepUSD
        obs_lot = observed_entries[i - 1].lot if i <= len(observed_entries) else None
        obs_dist = None
        if i <= len(observed_entries) and observed_entries[i - 1].price is not None \
                and i > 1 and observed_entries[i - 2].price is not None:
            obs_dist = abs(observed_entries[i - 1].price - observed_entries[i - 2].price)
        if obs_lot is None:
            status = "MODEL_ONLY"
        elif abs((obs_lot or 0) - (ev.lot or 0)) < 1e-9:
            status = "OBSERVED_MATCHES_SIMULATION"
        else:
            status = "OBSERVED_DIFFERS"
        rows.append({
            "level": i,
            "observed_lot": obs_lot, "observed_distance": obs_dist,
            "model_lot": round(model_lot, 4), "model_distance": model_dist,
            "simulation_lot": ev.lot,
            "simulation_distance": ev.distance_from_reference,
            "status": status,
        })
    return {
        "schema": "SNIPER_MODEL_VS_SIMULATION_V1",
        "rows": rows,
        "note": ("Simulation follows the model by construction (same core "
                 "formulas) — this is NEVER evidence of verified EA behavior. "
                 "Observed columns come only from real imported MT5 data."),
        "label": "MODEL ASSUMPTION",
    }
