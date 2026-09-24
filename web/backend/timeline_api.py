"""Phase 4 API handlers: timeline simulation + observation picker + exports."""
from __future__ import annotations

from typing import Optional

from core.config import EAConfig
from core.model_rules import ModelVersionStore
from core.observation import ObservationSessionStore
from core.symbol_profile import AccountSettings, SymbolProfile
from core.timeline_simulation import (
    OBSERVED_SERIES,
    SCENARIOS,
    SCENARIO,
    build_trace,
    compare_model_simulation,
    generate_scenario,
    simulate_timeline,
    worst_case_timeline,
)
from web.backend.parsers import RequestError

_DISALLOWED_EVIDENCE_TYPES = ("SYNTHETIC", "SCENARIO")


def list_scenarios() -> dict:
    return {"scenarios": list(SCENARIOS),
            "input_modes": [SCENARIO, OBSERVED_SERIES],
            "note": "All scenarios are SYNTHETIC / TEST DATA — never evidence."}


def run_simulation(body: dict) -> dict:
    config = EAConfig.from_dict(body.get("config") or EAConfig().to_dict())
    profile = SymbolProfile.from_dict(body.get("symbol_profile") or
                                      SymbolProfile().to_dict())
    account = AccountSettings.from_dict(body.get("account") or
                                        AccountSettings().to_dict())
    rules = ModelVersionStore().active_rules()
    if body.get("model_rules"):
        from core.model_rules import SimulationModelRules
        rules = SimulationModelRules.from_dict(body["model_rules"])

    scenario = body.get("scenario", "NORMAL_DOWN")
    if scenario not in SCENARIOS:
        raise RequestError(f"unknown scenario: {scenario}")
    start_price = body.get("start_price", profile.reference_price)
    bars = int(body.get("bars", 60))
    if not (10 <= bars <= 5000):
        raise RequestError("'bars' must be 10-5000")
    step = body.get("step", 1.0)
    side = body.get("side", "BUY")
    if side not in ("BUY", "SELL"):
        raise RequestError("'side' must be BUY or SELL")
    capital = body.get("capital", 500.0)

    series = generate_scenario(scenario, float(start_price), bars=bars,
                               step=float(step))
    sim = simulate_timeline(config, profile, account, rules, series,
                            side=side, capital=float(capital),
                            input_mode=SCENARIO)
    trace = build_trace(sim)
    result = compare_model_simulation([], sim, config, profile, rules)
    return {"simulation": sim.to_dict(),
            "trace": trace.to_dict(),
            "model_vs_simulation": result,
            "disclaimer": "SYNTHETIC / TEST DATA — scenario input, NOT observed evidence"}


def worst_case(body: dict) -> dict:
    config = EAConfig.from_dict(body.get("config") or EAConfig().to_dict())
    profile = SymbolProfile.from_dict(body.get("symbol_profile") or
                                      SymbolProfile().to_dict())
    account = AccountSettings.from_dict(body.get("account") or
                                        AccountSettings().to_dict())
    rules = ModelVersionStore().active_rules()
    capital = body.get("capital", 500.0)
    move = body.get("move", 50.0)
    scenario = body.get("scenario", "BOTH_SIDES")
    from core.worst_case import SCENARIOS as WC_SCENARIOS
    if scenario not in WC_SCENARIOS:
        raise RequestError(f"scenario must be one of {list(WC_SCENARIOS)}")
    tl = worst_case_timeline(config, profile, account, rules,
                             float(capital), float(move), scenario)
    return {"timeline": tl,
            "disclaimer": "Timeline is a visualization over the original worst-case engine (SSOT)"}


# ---------------------------------------------------------------------------
# Observation picker: validate that observation_id/event exist for real
# ---------------------------------------------------------------------------
def observation_picker(body: dict) -> dict:
    """List observation sessions + their events for the picker UI."""
    store = ObservationSessionStore()
    sessions = []
    for sid in store.list_sessions():
        s = store.load(sid)
        sessions.append({
            "session_id": sid,
            "symbol": s.symbol, "timeframe": s.timeframe,
            "source_type": s.source_type,
            "event_count": len(s.events),
            "events": [{"index": i, "event": e.event, "timestamp": e.timestamp,
                        "side": e.side, "lot": e.lot, "price": e.price}
                       for i, e in enumerate(s.events)],
        })
    return {"sessions": sessions, "count": len(sessions)}


def validate_observation_link(body: dict) -> dict:
    """REJECT references to sessions/events that don't exist (no fake refs)."""
    obs_id = (body.get("observation_id") or "").strip()
    event_index = body.get("event_index")
    if not obs_id:
        raise RequestError("'observation_id' is required")
    store = ObservationSessionStore()
    try:
        session = store.load(obs_id)
    except KeyError:
        raise RequestError(f"observation session not found: {obs_id}",
                           code="REJECT")
    if event_index is not None:
        idx = int(event_index)
        if not (0 <= idx < len(session.events)):
            raise RequestError(
                f"event index {idx} out of range (0-{len(session.events) - 1})",
                code="REJECT")
    return {"valid": True,
            "session_id": obs_id,
            "event_count": len(session.events),
            "event_index": event_index}


# ---------------------------------------------------------------------------
# Simulation export (JSON/CSV/HTML)
# ---------------------------------------------------------------------------
def export_simulation(body: dict):
    from web.backend.api import FileResponse
    fmt = body.get("format", "json")
    if fmt not in ("json", "csv", "html"):
        raise RequestError("'format' must be json/csv/html")
    result = run_simulation(body)
    sim = result["simulation"]
    if fmt == "json":
        import json
        payload = json.dumps(
            {"simulation": sim, "trace": result["trace"],
             "model_vs_simulation": result["model_vs_simulation"]},
            ensure_ascii=False, indent=2)
        return FileResponse("timeline-simulation.json",
                            "application/json; charset=utf-8",
                            payload.encode("utf-8"))
    if fmt == "csv":
        import csv, io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["timestamp", "event", "side", "level", "lot", "price",
                    "distance", "floating_pnl", "total_lots", "position_count",
                    "equity", "margin", "exposure", "drawdown", "cycle_id",
                    "label"])
        for e in sim["events"]:
            w.writerow([e["timestamp"], e["event"], e["side"], e["level"],
                        e["lot"], e["price"], e["distance_from_reference"],
                        e["floating_pnl"], e["total_lots"], e["position_count"],
                        e["equity"], e["margin"], e["exposure"], e["drawdown"],
                        e["cycle_id"], e["label"]])
        return FileResponse("timeline-simulation.csv", "text/csv; charset=utf-8",
                            buf.getvalue().encode("utf-8"))
    # HTML
    import html as H
    rows = "".join(
        f"<tr><td>{e['timestamp']}</td><td>{e['event']}</td>"
        f"<td>{e['side']}</td><td>{e['level']}</td><td>{e['lot']}</td>"
        f"<td>{e['price']}</td><td>{e['floating_pnl']}</td>"
        f"<td>{e['equity']}</td><td>{e['margin']}</td>"
        f"<td>{e['drawdown']}</td><td>{H.escape(e['label'])}</td></tr>"
        for e in sim["events"])
    page = f"""<html><head><meta charset='utf-8'><title>Timeline Simulation</title>
<style>body{{font-family:Segoe UI;margin:20px}}table{{border-collapse:collapse;font-size:12px}}
th,td{{border:1px solid #ccc;padding:4px 8px}}th{{background:#16213e;color:#fff}}
.banner{{background:#fff3cd;padding:8px;border-radius:6px}}</style></head><body>
<h1>Timeline Simulation</h1>
<div class='banner'><b>SYNTHETIC / TEST DATA — scenario input, NOT observed evidence.</b>
All events are MODEL ASSUMPTION — simulation follows the model by construction,
never evidence of verified EA behavior.</div>
<p>Model version: {sim['model_version']} · Status: {sim['status']} ·
Events: {len(sim['events'])}</p>
<table><tr><th>Time</th><th>Event</th><th>Side</th><th>Level</th><th>Lot</th>
<th>Price</th><th>Float P/L</th><th>Equity</th><th>Margin</th><th>DD%</th>
<th>Label</th></tr>{rows}</table></body></html>"""
    return FileResponse("timeline-simulation.html", "text/html; charset=utf-8",
                        page.encode("utf-8"))
