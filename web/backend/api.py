"""API handlers for the SNIPER CashFlow Analyzer web backend.

Every number returned by these handlers is computed by core/* - this module
contains NO formulas. It parses/validates the request, calls the core
functions the desktop app also calls, and serializes their structured
results (which already carry assumption IDs) to JSON.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import fields as dc_fields
from typing import Any, Dict, List, Optional

from core import calculations as c
from core.assumptions import ALL_STATUSES, default_registry
from core.backtest_analysis import analyze_backtest
from core.backtest_io import BacktestSummary, parse_backtest_file
from core.basket import simulate_basket
from core.config import EAConfig, builtin_presets
from core.grid import build_grid_table
from core.model_rules import ModelVersionStore
from core.report import ReportBundle, export_report_csv, export_report_html
from core.risk import RiskThresholds, build_risk_summary
from core.setbuilder import (
    MAX_COMBINATIONS,
    BuilderFilters,
    apply_filters,
    build_combinations,
    evaluate_set,
)
from core.symbol_profile import AccountSettings, SymbolProfile, builtin_profiles
from core.validation import ERROR, INFO, WARNING, has_errors, validate_config
from core.worst_case import (
    DEFAULT_MOVE_PRESETS,
    SCENARIOS,
    simulate_moves,
    simulate_worst_case,
)

from web.backend.parsers import (
    RequestError,
    build_account,
    build_config,
    build_profile,
    build_rules,
    build_thresholds,
    get_object,
    optional_number,
    parse_multipart,
    read_bounded,
    require_choice,
    require_int,
    require_number,
    require_number_list,
    safe_upload_filename,
)

EA_VERSION = "1.68"
DISCLAIMER = "Simulation Model — not verified internal EA formula"
UPLOAD_EXTENSIONS = (".csv", ".html", ".htm", ".txt")
MAX_EVALUATED_COMBOS = 300          # keep set-builder requests bounded
MAX_GRID_LEVELS = 500               # same cap as the desktop UI
MAX_MOVES_PER_REQUEST = 12


class FileResponse:
    """Non-JSON response (report download)."""

    def __init__(self, filename: str, content_type: str, body: bytes):
        self.filename = filename
        self.content_type = content_type
        self.body = body


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------
def _ctx(body: dict):
    """Build (config, profile, account, rules) from the request body."""
    return build_config(body), build_profile(body), build_account(body), build_rules(body)


def _gate(config: EAConfig, profile: SymbolProfile, account: AccountSettings,
          capital: float = 0.0) -> List[dict]:
    """Run core validation; ERRORs abort with 400, the rest are returned."""
    issues = validate_config(config, profile, account, capital)
    if has_errors(issues):
        raise RequestError(
            "EA configuration failed validation",
            code="CONFIG_INVALID",
            details=[f"{i.severity} {i.code}: {i.message}" for i in issues
                     if i.severity == ERROR])
    return [i.to_dict() for i in issues if i.severity in (WARNING, INFO)]


def _assumption_block(assumption_ids: List[str]) -> dict:
    ids = list(dict.fromkeys(assumption_ids))
    return {
        "assumptions": ids,
        "assumption_details": default_registry().describe(ids),
    }


def _grid_table_dict(table) -> dict:
    """Serialize a core GridTable (same shape core.report uses)."""
    return {
        "side": table.side,
        "start_price": round(table.start_price, 6),
        "grid_step": table.grid_step,
        "rows": table.to_dicts(),
        "total_lot": round(table.total_lot, 4),
        "total_exposure": round(table.total_exposure, 2),
        "total_margin": round(table.total_margin, 2),
        "final_floating_pl": round(table.final_floating_pl, 2),
        "avg_entry": round(table.avg_entry, 6) if table.avg_entry is not None else None,
        "assumptions": table.assumptions,
    }


# ---------------------------------------------------------------------------
# GET endpoints
# ---------------------------------------------------------------------------
def health() -> dict:
    rules = ModelVersionStore().active_rules()
    return {
        "status": "ok",
        "service": "SNIPER CashFlow Analyzer Web",
        "ea_version": EA_VERSION,
        "model_version": rules.model_version,
        "core": "core/ (single source of truth)",
        "disclaimer": DISCLAIMER,
    }


def get_config() -> dict:
    return {
        "ea_version": EA_VERSION,
        "defaults": EAConfig().to_dict(),
        "parameter_meta": EAConfig.parameter_meta(),
        "parameter_count": EAConfig().parameter_count(),
        "presets": {name: cfg.to_dict() for name, cfg in builtin_presets().items()},
        "profiles": [p.to_dict() for p in builtin_profiles()],
        "account_default": AccountSettings().to_dict(),
        "risk_thresholds_default": RiskThresholds().to_dict(),
        "model_rules": ModelVersionStore().active_rules().to_dict(),
        "move_presets": list(DEFAULT_MOVE_PRESETS),
        "assumption_statuses": list(ALL_STATUSES),
        "disclaimer": DISCLAIMER,
    }


def get_assumptions() -> dict:
    reg = default_registry()
    return {
        "assumptions": [{
            "assumption_id": a.assumption_id, "status": a.status, "title": a.title,
            "detail": a.detail, "source": a.source, "evidence": a.evidence,
        } for a in reg.all()],
        "statuses": list(ALL_STATUSES),
        "disclaimer": DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# POST endpoints
# ---------------------------------------------------------------------------
def validate(body: dict) -> dict:
    config, profile, account, _rules = _ctx(body)
    capital = optional_number(body, "capital", minimum=0.0)
    issues = validate_config(config, profile, account, capital if capital else 0.0)
    resolved = [i.to_dict() for i in issues]
    severities = [i["severity"] for i in resolved]
    return {
        "issues": resolved,
        "has_errors": ERROR in severities,
        "worst_severity": (ERROR if ERROR in severities
                           else WARNING if WARNING in severities else INFO),
        "parameter_count": config.parameter_count(),
    }


def grid_calculate(body: dict) -> dict:
    config, profile, account, rules = _ctx(body)
    levels = require_int(body, "levels", 1, MAX_GRID_LEVELS)
    side = require_choice(body, "side", (c.BUY, c.SELL), default=c.BUY)
    start_price = optional_number(body, "start_price", minimum=0.0)
    capital = optional_number(body, "capital", minimum=0.0)
    validation = _gate(config, profile, account, capital if capital else 0.0)
    table = build_grid_table(config, profile, account, rules, levels, side,
                             start_price if start_price else None)
    data = {
        "grid": _grid_table_dict(table),
        "validation": validation,
        "disclaimer": DISCLAIMER,
    }
    data.update(_assumption_block(table.assumptions))
    return data


def worst_case_simulate(body: dict) -> dict:
    config, profile, account, rules = _ctx(body)
    capital = require_number(body, "capital", minimum=0.000001)
    moves = require_number_list(body, "moves", 1, MAX_MOVES_PER_REQUEST, minimum=0.0)
    scenarios_raw = body.get("scenarios", list(SCENARIOS))
    if not isinstance(scenarios_raw, list) or not scenarios_raw:
        raise RequestError("'scenarios' must be a non-empty array")
    for s in scenarios_raw:
        if s not in SCENARIOS:
            raise RequestError(f"'scenarios' values must be one of {list(SCENARIOS)}")
    start_price = optional_number(body, "start_price", minimum=0.0)
    validation = _gate(config, profile, account, capital)

    results = []
    all_ids: List[str] = []
    for mv in moves:
        for scenario in scenarios_raw:
            r = simulate_worst_case(config, profile, account, rules, capital,
                                    mv, scenario,
                                    start_price if start_price else None)
            results.append(r.to_dict())
            all_ids.extend(r.assumptions)
    data = {
        "capital": capital,
        "moves": moves,
        "scenarios": scenarios_raw,
        "results": results,
        "validation": validation,
        "disclaimer": DISCLAIMER,
    }
    data.update(_assumption_block(all_ids))
    return data


def risk_calculate(body: dict) -> dict:
    config, profile, account, rules = _ctx(body)
    capital = require_number(body, "capital", minimum=0.000001)
    thresholds = build_thresholds(body)
    side = require_choice(body, "side", (c.BUY, c.SELL), default=c.BUY)
    validation = _gate(config, profile, account, capital)
    summary = build_risk_summary(config, profile, account, rules, capital,
                                 thresholds, side)
    data = {
        "summary": summary.to_dict(),
        "thresholds": thresholds.to_dict(),
        "validation": validation,
        "disclaimer": DISCLAIMER,
    }
    data.update(_assumption_block(summary.assumptions))
    return data


def basket_simulate(body: dict) -> dict:
    config, profile, _account, rules = _ctx(body)
    side = require_choice(body, "side", (c.BUY, c.SELL), default=c.BUY)
    levels = require_int(body, "levels", 1, MAX_GRID_LEVELS)
    start_price = optional_number(body, "start_price", minimum=0.0)
    current_price = optional_number(body, "current_price", minimum=0.0)
    already = body.get("partial_already_done", False)
    if not isinstance(already, bool):
        raise RequestError("'partial_already_done' must be a boolean")
    result = simulate_basket(config, profile, rules, side, levels,
                             start_price if start_price else None,
                             current_price if current_price else None, already)
    data = {
        "basket": result.to_dict(),
        "disclaimer": DISCLAIMER,
    }
    data.update(_assumption_block(result.assumptions))
    return data


def _as_number_list(val: Any, key: str, minimum: Optional[float] = None) -> List[float]:
    """Accept [..] list or a single number for set-builder value lists."""
    if isinstance(val, list):
        if not (1 <= len(val) <= 50):
            raise RequestError(f"'{key}' must contain 1-50 values")
        out = []
        for v in val:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise RequestError(f"'{key}' values must be numbers")
            vf = float(v)
            if minimum is not None and vf < minimum:
                raise RequestError(f"'{key}' values must be >= {minimum}")
            out.append(vf)
        return out
    return _as_number_list([val], key, minimum)


def set_builder_generate(body: dict) -> dict:
    config, profile, account, rules = _ctx(body)
    values_in = get_object(body, "values")
    if not values_in:
        raise RequestError("'values' is required")

    values: Dict[str, List[float]] = {
        "grid_step": _as_number_list(
            require_choice_key(values_in, "grid_step"), "grid_step", minimum=0.000001),
        "base_lot": _as_number_list(
            require_choice_key(values_in, "base_lot"), "base_lot", minimum=0.000001),
        "multiplier": _as_number_list(
            require_choice_key(values_in, "multiplier"), "multiplier", minimum=0.000001),
    }
    if "capital" in values_in:
        values["capital"] = _as_number_list(values_in["capital"], "capital", minimum=0.000001)
    elif optional_number(body, "capital", minimum=0.000001):
        values["capital"] = [optional_number(body, "capital", minimum=0.000001)]
    else:
        raise RequestError("'values.capital' or 'capital' is required")
    values["basket_target"] = _as_number_list(
        values_in.get("basket_target", config.BasketCloseAllUSD), "basket_target",
        minimum=0.0)
    max_grid_raw = values_in.get("max_grid", 11)
    mg_list = _as_number_list(max_grid_raw, "max_grid", minimum=1)
    values["max_grid"] = []
    for v in mg_list:
        if not float(v).is_integer() or not (1 <= v <= 200):
            raise RequestError("'max_grid' values must be integers 1-200")
        values["max_grid"].append(float(int(v)))
    unknown = [k for k in values_in
               if k not in ("grid_step", "base_lot", "multiplier", "capital",
                            "basket_target", "max_grid")]
    if unknown:
        raise RequestError(f"Unknown values key(s): {', '.join(sorted(unknown))}")

    try:
        combos = build_combinations(values)
    except ValueError as exc:
        raise RequestError(str(exc), "TOO_MANY_COMBINATIONS")
    if len(combos) > MAX_EVALUATED_COMBOS:
        raise RequestError(
            f"Too many combinations to evaluate ({len(combos)} > {MAX_EVALUATED_COMBOS}) "
            f"- reduce the value lists", "TOO_MANY_COMBINATIONS")

    filters_raw = get_object(body, "filters")
    if filters_raw:
        allowed = {f.name for f in dc_fields(BuilderFilters)}
        unknown = [k for k in filters_raw if k not in allowed]
        if unknown:
            raise RequestError(f"Unknown filters key(s): {', '.join(sorted(unknown))}")
    filters = BuilderFilters.from_dict(filters_raw)

    rows: List[dict] = []
    all_ids: List[str] = []
    passed_count = 0
    for combo in combos:
        try:
            metrics = evaluate_set(
                config, profile, account, rules,
                capital=combo["capital"], grid_step=combo["grid_step"],
                base_lot=combo["base_lot"], multiplier=combo["multiplier"],
                basket_target=combo["basket_target"], max_grid=int(combo["max_grid"]))
        except ValueError as exc:
            raise RequestError(f"Evaluation failed for {combo}: {exc}")
        passed, reasons = apply_filters(metrics, filters)
        passed_count += 1 if passed else 0
        all_ids.extend(metrics.assumptions)
        rows.append({
            "capital": combo["capital"],
            "grid_step": combo["grid_step"],
            "base_lot": combo["base_lot"],
            "multiplier": combo["multiplier"],
            "basket_target": combo["basket_target"],
            "max_grid": int(combo["max_grid"]),
            "metrics": metrics.to_dict(),
            "passed": passed,
            "filter_reasons": reasons,
        })
    data = {
        "combinations": rows,
        "total": len(rows),
        "passed_count": passed_count,
        "filtered_count": len(rows) - passed_count,
        "filters": filters.to_dict(),
        "note": "Results are in generation order - sets are not ranked or scored.",
        "disclaimer": DISCLAIMER,
    }
    data.update(_assumption_block(all_ids))
    return data


def require_choice_key(values_in: dict, key: str) -> Any:
    if key not in values_in:
        raise RequestError(f"'values.{key}' is required")
    return values_in[key]


def backtest_analyze(environ: dict, max_upload_bytes: int) -> dict:
    content_type = environ.get("CONTENT_TYPE", "")
    if "multipart/form-data" not in content_type:
        raise RequestError("Content-Type must be multipart/form-data with a 'file' field")
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        raise RequestError("Invalid Content-Length")
    # read/drain the body first so an oversized upload still gets its 413
    # response instead of a connection reset while the client is sending
    body = read_bounded(environ, max_upload_bytes + 1)
    if length > max_upload_bytes or len(body) > max_upload_bytes:
        raise RequestError(f"Upload too large (> {max_upload_bytes} bytes)",
                           "PAYLOAD_TOO_LARGE")
    fields = parse_multipart(body, content_type)
    if "file" not in fields:
        raise RequestError("multipart field 'file' is required")
    raw_filename, content = fields["file"]
    filename = safe_upload_filename(raw_filename, UPLOAD_EXTENSIONS)
    if not content.strip():
        raise RequestError("Uploaded file is empty")

    ext = os.path.splitext(filename)[1].lower()
    tmp = tempfile.NamedTemporaryFile(prefix="sniper_bt_", suffix=ext, delete=False)
    try:
        tmp.write(content)
        tmp.close()
        summary = parse_backtest_file(tmp.name)
    finally:
        os.unlink(tmp.name)
    summary.source_file = filename
    analysis = analyze_backtest(summary)
    return {
        "summary": summary.to_dict(),
        "analysis": analysis.to_dict(),
        "allowed_extensions": list(UPLOAD_EXTENSIONS),
        "disclaimer": ("Imported backtest data - fields not present in the file "
                       "are shown as N/A. Nothing is extrapolated."),
    }


def report(body: dict) -> FileResponse:
    fmt = require_choice(body, "format", ("json", "csv", "html"))
    config, profile, account, rules = _ctx(body)
    capital = require_number(body, "capital", minimum=0.000001)
    start_price = optional_number(body, "start_price", minimum=0.0)
    p0 = start_price if start_price else None

    include_grid = bool(body.get("include_grid", True))
    include_worst = bool(body.get("include_worst_case", True))
    include_risk = bool(body.get("include_risk", True))
    include_basket = bool(body.get("include_basket", True))

    validation = _gate(config, profile, account, capital)

    grid_tables = []
    if include_grid:
        levels = require_int(body, "levels", 1, MAX_GRID_LEVELS) \
            if "levels" in body else 11
        side = require_choice(body, "side", (c.BUY, c.SELL), default=c.BUY)
        grid_tables.append(build_grid_table(config, profile, account, rules,
                                            levels, side, p0))
    worst_cases = []
    if include_worst:
        moves = require_number_list(body, "moves", 1, MAX_MOVES_PER_REQUEST,
                                    minimum=0.0) if "moves" in body \
            else [10.0, 30.0, 50.0, 100.0]
        worst_cases = simulate_moves(config, profile, account, rules, capital,
                                     moves, p0)
    risk_summary = None
    if include_risk:
        risk_summary = build_risk_summary(config, profile, account, rules, capital,
                                          build_thresholds(body))
    basket_sims = []
    if include_basket:
        b_side = require_choice(body, "basket_side", (c.BUY, c.SELL), default=c.BUY)
        b_levels = require_int(body, "basket_levels", 1, MAX_GRID_LEVELS) \
            if "basket_levels" in body else 5
        basket_sims.append(simulate_basket(config, profile, rules, b_side,
                                           b_levels, p0))

    backtest_summary = None
    if body.get("backtest_summary"):
        bs_raw = body["backtest_summary"]
        if not isinstance(bs_raw, dict):
            raise RequestError("'backtest_summary' must be an object "
                               "(as returned by /api/backtest/analyze)")
        backtest_summary = BacktestSummary.from_dict(json.loads(json.dumps(bs_raw)))

    bundle = ReportBundle(
        config=config, profile=profile, account=account, capital=capital,
        grid_tables=grid_tables, worst_cases=worst_cases,
        risk_summary=risk_summary, basket_sims=basket_sims,
        backtest_summary=backtest_summary,
        extra_warnings=[f"{i['severity']}: {i['message']}" for i in validation],
    )

    if fmt == "json":
        payload = json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2)
        return FileResponse("sniper-report.json", "application/json; charset=utf-8",
                            payload.encode("utf-8"))
    tmp = tempfile.NamedTemporaryFile(prefix="sniper_rep_", suffix=f".{fmt}",
                                      delete=False)
    try:
        tmp.close()
        if fmt == "csv":
            export_report_csv(bundle, tmp.name)
            ctype = "text/csv; charset=utf-8"
        else:
            export_report_html(bundle, tmp.name)
            ctype = "text/html; charset=utf-8"
        with open(tmp.name, "rb") as f:
            content = f.read()
    finally:
        os.unlink(tmp.name)
    return FileResponse(f"sniper-report.{fmt}", ctype, content)
