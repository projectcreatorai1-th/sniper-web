"""Patch: add Phase 4 Timeline page to web/frontend/app.js (idempotent)."""
import io

PATH = "web/frontend/app.js"
src = io.open(PATH, encoding="utf-8").read()

if "pageTimeline" in src:
    print("already patched")
    raise SystemExit(0)

src = src.replace('  ["#/evidence", "Evidence"],',
                  '  ["#/evidence", "Evidence"],\n  ["#/timeline", "Timeline"],')
src = src.replace('  "/evidence": pageEvidence,',
                  '  "/evidence": pageEvidence,\n  "/timeline": pageTimeline,')

PAGE = r'''
/* ---------- Timeline Simulator (Phase 4) ---------- */
function pageTimeline(page) {
  const resultBox = el("div");
  let scenarios = [];

  function statusBadge(s) {
    const cls = { COMPLETE: "pass-true", INCOMPLETE: "sev-WARNING",
                  ERROR: "pass-false" }[s] || "st-UNKNOWN";
    return el("span", { class: "badge " + cls }, s);
  }

  async function doSimulate(ev) {
    const b = ev.target;
    resultBox.replaceChildren();
    const body = calcBody({
      scenario: $("#tl_scenario").value,
      start_price: parseFloat($("#tl_start").value) || S.symbol_profile.reference_price,
      bars: parseInt($("#tl_bars").value) || 60,
      step: parseFloat($("#tl_step").value) || 1.0,
      side: $("#tl_side").value,
      capital: S.capital,
    });
    busy(b, true, "\\u0e08\\u0e33\\u0e25\\u0e2d\\u0e07\\u0e01\\u0e32\\u0e23...");
    try {
      const d = await apiPost("/api/timeline/simulate", body);
      renderSim(d);
    } catch (err) { resultBox.replaceChildren(errorBox(err)); }
    busy(b, false);
  }

  function renderSim(d) {
    const sim = d.simulation;
    const events = sim.events;
    S.ui.rerender = () => renderSim(d);

    resultBox.replaceChildren(
      el("div", { class: "card" },
        el("div", { style: "display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap" },
          el("h2", null, sim.simulation_id + " — " + sim.input_mode),
          statusBadge(sim.status)),
        el("div", { class: "banner", style: "margin:6px 0" },
          el("b", null, "SYNTHETIC / TEST DATA"), " — \\u0e40\\u0e1b\\u0e47\\u0e19 scenario input \\u0e44\\u0e21\\u0e48\\u0e43\\u0e0a\\u0e48 observed evidence"),
        el("div", { class: "metric-grid" },
          metric("Model Version", sim.model_version),
          metric("Events", String(events.length)),
          metric("Cycles", String(new Set(events.map(e => e.cycle_id)).size)),
          metric("Status", sim.status),
          metric("Synthetic", String(sim.synthetic))),
        el("h3", null, "Event Timeline"),
        events.length === 0 ? el("p", { class: "sub" }, "\\u0e44\\u0e21\\u0e48\\u0e21\\u0e35 events") :
        dataTable(["Time", "Event", "Side", "Level", "Lot", "Price", "Dist", "Float P/L", "Total Lots", "Pos", "Equity", "Margin", "DD%", "Label"],
          events.map(e => el("tr", null,
            el("td", null, e.timestamp || "?"),
            el("td", null, el("b", null, e.event)),
            el("td", null, e.side || "\\u2014"),
            el("td", null, e.level ?? "\\u2014"),
            numCell(e.lot, 2), numCell(e.price, 2),
            numCell(e.distance_from_reference, 2),
            numCell(e.floating_pnl, 2),
            numCell(e.total_lots, 2), el("td", null, e.position_count ?? "\\u2014"),
            numCell(e.equity, 2), numCell(e.margin, 2),
            numCell(e.drawdown, 2),
            el("td", null, el("span", { class: "badge sev-INFO", title: "MODEL ASSUMPTION" }, "MODEL"))))),
        el("p", { class: "sub" },
          "\\u0e17\\u0e38\\u0e01 event \\u0e40\\u0e1b\\u0e47\\u0e19 MODEL ASSUMPTION — simulation \\u0e17\\u0e33\\u0e15\\u0e32\\u0e21 model \\u0e42\\u0e14\\u0e22\\u0e01\\u0e32\\u0e23\\u0e01\\u0e23\\u0e30\\u0e17\\u0e33 (\\u0e2a\\u0e39\\u0e15\\u0e23\\u0e40\\u0e14\\u0e35\\u0e22\\u0e27\\u0e01\\u0e31\\u0e19) \\u0e44\\u0e21\\u0e48\\u0e43\\u0e0a\\u0e48\\u0e2b\\u0e25\\u0e31\\u0e01\\u0e10\\u0e32\\u0e19\\u0e27\\u0e48\\u0e32 EA \\u0e17\\u0e33\\u0e07\\u0e32\\u0e19\\u0e41\\u0e1a\\u0e1a\\u0e19\\u0e35\\u0e49")),
      el("div", { class: "card" },
        el("h2", null, "Trace"),
        el("div", { class: "metric-grid" },
          metric("Model Version", d.trace.model_version),
          metric("Assumptions", String(d.trace.assumption_ids.length)),
          metric("Evidence", String(d.trace.evidence_ids.length)),
          metric("Input Mode", d.trace.input_mode)),
        el("p", { class: "sub" },
          "Assumptions: " + d.trace.assumption_ids.slice(0, 5).join(", ") + "...")),
      el("div", { class: "card" },
        el("h2", null, "Export"),
        el("div", { class: "chip-row" },
          el("button", { class: "btn-gold btn-small", onclick: () => doExport("json") }, "JSON"),
          el("button", { class: "btn-gold btn-small", onclick: () => doExport("csv") }, "CSV"),
          el("button", { class: "btn-gold btn-small", onclick: () => doExport("html") }, "HTML"))));
  }

  async function doExport(fmt) {
    const body = calcBody({
      scenario: $("#tl_scenario").value,
      start_price: parseFloat($("#tl_start").value) || S.symbol_profile.reference_price,
      bars: parseInt($("#tl_bars").value) || 60,
      step: parseFloat($("#tl_step").value) || 1.0,
      side: $("#tl_side").value,
      capital: S.capital,
      format: fmt,
    });
    const res = await fetch("/api/timeline/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) { resultBox.append(errorBox({ message: "HTTP " + res.status })); return; }
    const blob = await res.blob();
    const a = el("a", { href: URL.createObjectURL(blob),
                        download: "timeline-simulation." + fmt });
    a.click();
  }

  async function init() {
    try {
      const d = await apiGet("/api/timeline/scenarios");
      scenarios = d.scenarios;
      const sel = $("#tl_scenario");
      sel.replaceChildren(...scenarios.map(s => el("option", { value: s }, s)));
      sel.value = "NORMAL_DOWN";
    } catch (e) { /* defaults still work */ }
  }

  page.append(
    el("h1", { class: "page-title" }, "Timeline Simulator"),
    el("p", { class: "page-sub" },
      "\\u0e08\\u0e33\\u0e25\\u0e2d\\u0e07\\u0e40\\u0e2a\\u0e49\\u0e19\\u0e17\\u0e32\\u0e07\\u0e23\\u0e32\\u0e04\\u0e32-\\u0e40\\u0e27\\u0e25\\u0e32 \\u0e1e\\u0e23\\u0e49\\u0e2d\\u0e21 event timeline \\u0e40\\u0e15\\u0e47\\u0e21\\u0e23\\u0e39\\u0e1b\\u0e41\\u0e1a\\u0e1a (\\u0e42\\u0e14\\u0e22\\u0e43\\u0e0a\\u0e49 Core \\u0e0a\\u0e38\\u0e14\\u0e40\\u0e14\\u0e35\\u0e22\\u0e27\\u0e01\\u0e31\\u0e19)"),
    disclaimerBanner(),
    el("div", { class: "card" },
      el("h2", null, "Scenario Builder"),
      el("div", { class: "form-grid" },
        el("div", { class: "field" }, el("label", null, "Scenario"),
          el("select", { id: "tl_scenario" })),
        el("div", { class: "field" }, el("label", null, "Start Price"),
          el("input", { type: "number", step: "any", id: "tl_start", placeholder: String(S.symbol_profile.reference_price) })),
        el("div", { class: "field" }, el("label", null, "Bars (10-5000)"),
          el("input", { type: "number", id: "tl_bars", value: "60" })),
        el("div", { class: "field" }, el("label", null, "Step Size ($)"),
          el("input", { type: "number", step: "any", id: "tl_step", value: "1.0" })),
        el("div", { class: "field" }, el("label", null, "Side"),
          el("select", { id: "tl_side" },
            el("option", { value: "BUY" }, "BUY"),
            el("option", { value: "SELL" }, "SELL")))),
      el("p", { class: "sub" }, "\\u0e17\\u0e38\\u0e01 scenario \\u0e40\\u0e1b\\u0e47\\u0e19 SYNTHETIC / TEST DATA — \\u0e44\\u0e21\\u0e48\\u0e40\\u0e01\\u0e47\\u0e1a\\u0e40\\u0e02\\u0e49\\u0e32 Evidence Registry"),
      el("div", { style: "margin-top:10px" },
        el("button", { class: "btn-primary", onclick: doSimulate }, "\\u0e08\\u0e33\\u0e25\\u0e2d\\u0e07 Timeline"))),
    resultBox);
  init();
}

/* ======================= router + boot ======================= */'''

PAGE = PAGE.encode("utf-8").decode("unicode_escape")
src = src.replace('/* ======================= router + boot ======================= */', PAGE)
io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
print("timeline page added")
