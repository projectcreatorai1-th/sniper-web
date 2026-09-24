"""Add the Phase 2 Observation page to web/frontend/app.js (idempotent)."""
import io

PATH = "web/frontend/app.js"
src = io.open(PATH, encoding="utf-8").read()

if "/observation" in src and "pageObservation" in src:
    print("already patched")
    raise SystemExit(0)

src = src.replace('  ["#/assumptions", "Assumptions"],',
                  '  ["#/assumptions", "Assumptions"],\n  ["#/observation", "Observation"],')
src = src.replace('  "/assumptions": pageAssumptions,',
                  '  "/assumptions": pageAssumptions,\n  "/observation": pageObservation,')

PAGE = '''
/* ---------- Observation (Phase 2: MT5 behavior verification) ---------- */
function pageObservation(page) {
  const resultBox = el("div");
  let sessionId = null;

  function statusBadge(s) {
    const cls = { MATCH: "pass-true", PARTIAL_MATCH: "st-OBSERVED_FROM_TESTING",
                  MISMATCH: "pass-false", UNKNOWN: "st-UNKNOWN",
                  INSUFFICIENT_DATA: "sev-INFO" }[s] || "st-UNKNOWN";
    return el("span", { class: "badge " + cls, title: s }, s);
  }

  function sectionBtn(label, fn) {
    return el("button", { class: "btn-ghost btn-small", onclick: async (ev) => {
      const b = ev.target; busy(b, true, "\\u0e42\\u0e2b\\u0e25\\u0e14\\u2026");
      try { await fn(); } catch (e) { resultBox.replaceChildren(errorBox(e)); }
      busy(b, false);
    } }, label);
  }

  async function loadEvents() {
    const d = await apiGet("/api/observation-sessions/" + sessionId + "/events");
    resultBox.replaceChildren(el("div", { class: "card" },
      el("h2", null, "Observed Events (" + d.count + ")"),
      d.count === 0 ? el("p", { class: "sub" }, "\\u0e22\\u0e31\\u0e07\\u0e44\\u0e21\\u0e48\\u0e21\\u0e35 events \\u2014 import \\u0e01\\u0e48\\u0e2d\\u0e19") :
      dataTable(["Time", "Event", "Side", "Level", "Lot", "Price", "P/L", "Comm", "Swap"],
        d.events.map(e => el("tr", null,
          el("td", null, e.timestamp || "?"), el("td", null, e.event),
          el("td", null, e.side || "\\u2014"), el("td", null, e.grid_level === null ? "\\u2014" : e.grid_level),
          numCell(e.lot, 2), numCell(e.price, 2),
          numCell(e.basket_pl === null ? e.floating_pl : e.basket_pl, 2),
          numCell(e.commission, 2), numCell(e.swap, 2))))));
  }

  async function loadComparison() {
    const d = await apiGet("/api/observation-sessions/" + sessionId + "/comparison");
    const rows = d.checks.map(c => el("tr", null,
      el("td", null, c.check_id), el("td", null, c.title),
      el("td", null, statusBadge(c.status)),
      el("td", null, c.observed_value), el("td", null, c.model_value),
      el("td", null, c.difference || "\\u2014"),
      el("td", { class: "na", title: (c.assumption_ids || []).join(", ") },
         (c.assumption_ids || []).length + " ids")));
    resultBox.replaceChildren(el("div", { class: "card" },
      el("h2", null, "Model Comparison"),
      el("div", { class: "metric-grid" },
        Object.entries(d.counts).map(([k, v]) => metric(k, String(v)))),
      dataTable(["Check", "Title", "Status", "Observed", "Model", "Diff", "Assumptions"], rows),
      el("p", { class: "sub" },
        "MATCH = \\u0e2a\\u0e2d\\u0e14\\u0e04\\u0e25\\u0e49\\u0e2d\\u0e07\\u0e01\\u0e31\\u0e1a\\u0e42\\u0e21\\u0e40\\u0e14\\u0e25\\u0e4c (\\u0e44\\u0e21\\u0e48\\u0e43\\u0e0a\\u0e48\\u0e01\\u0e32\\u0e23\\u0e1e\\u0e34\\u0e2a\\u0e39\\u0e08\\u0e19\\u0e4c\\u0e2a\\u0e39\\u0e15\\u0e23 EA) \\u00b7 \\u0e44\\u0e21\\u0e48\\u0e21\\u0e35 auto-correct")));
  }

  async function loadTimeline() {
    const d = await apiGet("/api/observation-sessions/" + sessionId + "/timeline");
    resultBox.replaceChildren(el("div", { class: "card" },
      el("h2", null, "Cycle Timeline (" + d.cycle_count + " cycles \\u00b7 complete " + d.complete + " \\u00b7 incomplete " + d.incomplete + ")"),
      d.cycle_count === 0 ? el("p", { class: "sub" }, "\\u0e22\\u0e31\\u0e07\\u0e44\\u0e21\\u0e48\\u0e21\\u0e35 cycle") :
      d.timelines.map(t => el("details", { class: "lvl-card" },
        el("summary", { class: "lvl-head" },
          el("b", null, t.cycle_id + " \\u00b7 " + t.direction + " \\u00b7 " + t.grid_levels + " levels"),
          el("span", { class: "badge " + (t.status === "COMPLETE" ? "pass-true" : "sev-WARNING") },
            t.status + (t.missing.length ? " (\\u0e02\\u0e32\\u0e14: " + t.missing.join(", ") + ")" : ""))),
        dataTable(["#", "Time", "Event", "Pos", "Lots", "Float", "Equity"],
          t.rows.map(r => el("tr", null,
            el("td", null, r.seq), el("td", null, r.timestamp || "?"),
            el("td", null, r.event), el("td", null, r.position_count === null ? "\\u2014" : r.position_count),
            numCell(r.total_lots, 2), numCell(r.floating_pl, 2), numCell(r.equity, 2))))))));
  }

  async function downloadReport() {
    const res = await fetch("/api/observation-sessions/" + sessionId + "/report");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const blob = await res.blob();
    const a = el("a", { href: URL.createObjectURL(blob),
                        download: "behavior-verification-report.json" });
    a.click();
    resultBox.replaceChildren(el("div", { class: "card" },
      el("h2", null, "\\u0e23\\u0e32\\u0e22\\u0e07\\u0e32\\u0e19\\u0e14\\u0e32\\u0e27\\u0e19\\u0e4c\\u0e42\\u0e2b\\u0e25\\u0e14\\u0e41\\u0e25\\u0e49\\u0e27"),
      el("p", { class: "sub" }, "behavior-verification-report.json \\u2014 \\u0e04\\u0e23\\u0e1a 15 sections + evidence/assumption traceability")));
  }

  async function doCreate(ev) {
    const b = ev.target; resultBox.replaceChildren();
    const body = {
      symbol: $("#ob_symbol").value.trim(),
      timeframe: $("#ob_tf").value.trim(),
      broker: $("#ob_broker").value.trim(),
      account_type: $("#ob_acct").value.trim(),
      source_type: $("#ob_src").value,
      notes: $("#ob_notes").value.trim(),
    };
    const bal = parseFloat($("#ob_bal").value);
    if (!isNaN(bal)) body.initial_balance = bal;
    busy(b, true, "\\u0e2a\\u0e23\\u0e49\\u0e32\\u0e07\\u2026");
    try {
      const d = await apiPost("/api/observation-sessions", body);
      sessionId = d.session.session_id;
      resultBox.replaceChildren(el("div", { class: "card" },
        el("h2", null, "Session \\u0e2a\\u0e23\\u0e49\\u0e32\\u0e07\\u0e41\\u0e25\\u0e49\\u0e27: " + sessionId),
        el("p", { class: "sub" }, "import \\u0e44\\u0e1f\\u0e25\\u0e4c MT5 (CSV/Journal/Tester) \\u0e44\\u0e14\\u0e49\\u0e40\\u0e25\\u0e22\\u0e14\\u0e49\\u0e32\\u0e19\\u0e25\\u0e48\\u0e32\\u0e07")));
    } catch (e) { resultBox.replaceChildren(errorBox(e)); }
    busy(b, false);
  }

  async function doImport(ev) {
    const b = ev.target; resultBox.replaceChildren();
    if (!sessionId) { resultBox.replaceChildren(errorBox({ message: "\\u0e2a\\u0e23\\u0e49\\u0e32\\u0e07 session \\u0e01\\u0e48\\u0e2d\\u0e19" })); return; }
    const input = $("#ob_file");
    if (!input.files || !input.files.length) {
      resultBox.replaceChildren(errorBox({ message: "\\u0e40\\u0e25\\u0e37\\u0e2d\\u0e01\\u0e44\\u0e1f\\u0e25\\u0e4c\\u0e01\\u0e48\\u0e2d\\u0e19 (.csv/.txt/.log/.html)" }));
      return;
    }
    const fd = new FormData();
    fd.append("file", input.files[0], input.files[0].name);
    fd.append("source_kind", $("#ob_kind").value);
    busy(b, true, "\\u0e19\\u0e33\\u0e40\\u0e02\\u0e49\\u0e32\\u2026");
    try {
      const d = await apiUpload("/api/observation-sessions/" + sessionId + "/import", fd);
      const r = d.import_result;
      resultBox.replaceChildren(el("div", { class: "card" },
        el("h2", null, "Import \\u0e40\\u0e2a\\u0e23\\u0e47\\u0e08 \\u2014 " + r.rows_imported + "/" + r.rows_read + " \\u0e41\\u0e16\\u0e27"),
        el("div", { class: "metric-grid" },
          metric("Read", String(r.rows_read)), metric("Imported", String(r.rows_imported)),
          metric("Rejected", String(r.rows_rejected)), metric("Events \\u0e23\\u0e27\\u0e21", String(d.event_count))),
        r.unknown_columns.length ? el("p", { class: "sub" },
          "\\u0e04\\u0e2d\\u0e25\\u0e31\\u0e21\\u0e19\\u0e4c\\u0e17\\u0e35\\u0e48\\u0e44\\u0e21\\u0e48\\u0e23\\u0e39\\u0e49\\u0e08\\u0e31\\u0e01 (\\u0e44\\u0e21\\u0e48\\u0e19\\u0e33\\u0e40\\u0e02\\u0e49\\u0e32): " + r.unknown_columns.join(", ")) : null,
        r.warnings.length ? el("ul", { class: "issue-list" },
          r.warnings.map(w => el("li", null, el("span", { class: "na" }, w)))) : null));
    } catch (e) { resultBox.replaceChildren(errorBox(e)); }
    busy(b, false);
  }

  page.append(
    el("h1", { class: "page-title" }, "MT5 Observation & Behavior Verification"),
    el("p", { class: "page-sub" },
      "\\u0e19\\u0e33\\u0e40\\u0e02\\u0e49\\u0e32\\u0e02\\u0e49\\u0e2d\\u0e21\\u0e39\\u0e25\\u0e08\\u0e23\\u0e34\\u0e07\\u0e08\\u0e32\\u0e01 MT5 \\u2192 \\u0e15\\u0e23\\u0e27\\u0e08\\u0e1e\\u0e24\\u0e15\\u0e34\\u0e01\\u0e23\\u0e23\\u0e21 EA \\u0e40\\u0e17\\u0e35\\u0e22\\u0e1a Simulation Model (OBSERVED vs MODEL vs UNKNOWN)"),
    disclaimerBanner(),
    el("div", { class: "card" },
      el("h2", null, "1. \\u0e2a\\u0e23\\u0e49\\u0e32\\u0e07 Observation Session"),
      el("div", { class: "form-grid" },
        el("div", { class: "field" }, el("label", null, "Symbol"), el("input", { id: "ob_symbol", placeholder: "XAUUSD" })),
        el("div", { class: "field" }, el("label", null, "Timeframe"), el("input", { id: "ob_tf", placeholder: "M15" })),
        el("div", { class: "field" }, el("label", null, "Broker"), el("input", { id: "ob_broker", placeholder: "XM Global" })),
        el("div", { class: "field" }, el("label", null, "Account Type"), el("input", { id: "ob_acct", placeholder: "Hedge" })),
        el("div", { class: "field" }, el("label", null, "Initial Balance"), el("input", { type: "number", id: "ob_bal", placeholder: "500" })),
        el("div", { class: "field" }, el("label", null, "Source Type"),
          el("select", { id: "ob_src" },
            el("option", { value: "MT5_CSV" }, "MT5_CSV"),
            el("option", { value: "MT5_JOURNAL" }, "MT5_JOURNAL"),
            el("option", { value: "MT5_TESTER" }, "MT5_TESTER"),
            el("option", { value: "MANUAL_OBSERVATION" }, "MANUAL_OBSERVATION"))),
        el("div", { class: "field" }, el("label", null, "Notes"), el("input", { id: "ob_notes", placeholder: "\\u0e2b\\u0e21\\u0e32\\u0e22\\u0e40\\u0e2b\\u0e15\\u0e38" }))),
      el("div", { style: "margin-top:10px" }, el("button", { class: "btn-primary", onclick: doCreate }, "\\u0e2a\\u0e23\\u0e49\\u0e32\\u0e07 Session"))),
    el("div", { class: "card" },
      el("h2", null, "2. Import \\u0e44\\u0e1f\\u0e25\\u0e4c MT5"),
      el("div", { class: "form-grid" },
        el("div", { class: "field" }, el("label", null, "\\u0e44\\u0e1f\\u0e25\\u0e4c (.csv/.txt/.log/.html \\u2264 8MB)"),
          el("input", { type: "file", id: "ob_file", accept: ".csv,.txt,.log,.htm,.html" })),
        el("div", { class: "field" }, el("label", null, "\\u0e0a\\u0e19\\u0e34\\u0e14\\u0e02\\u0e49\\u0e2d\\u0e21\\u0e39\\u0e25"),
          el("select", { id: "ob_kind" },
            el("option", { value: "MT5_CSV" }, "Behavior CSV"),
            el("option", { value: "MT5_JOURNAL" }, "Journal/Log"),
            el("option", { value: "MT5_TESTER" }, "Tester Report")))),
      el("div", { style: "margin-top:10px" }, el("button", { class: "btn-primary", onclick: doImport }, "Import"))),
    el("div", { class: "card" },
      el("h2", null, "3. \\u0e15\\u0e23\\u0e27\\u0e08 & \\u0e23\\u0e32\\u0e22\\u0e07\\u0e32\\u0e19"),
      el("div", { class: "chip-row" },
        sectionBtn("Events", loadEvents),
        sectionBtn("Model Comparison", loadComparison),
        sectionBtn("Cycle Timeline", loadTimeline),
        sectionBtn("\\u0e14\\u0e32\\u0e27\\u0e19\\u0e4c\\u0e42\\u0e2b\\u0e25\\u0e14\\u0e23\\u0e32\\u0e22\\u0e07\\u0e32\\u0e19 JSON", downloadReport))),
    resultBox);
}

/* ======================= router + boot ======================= */'''

PAGE = PAGE.encode("utf-8").decode("unicode_escape")

src = src.replace('/* ======================= router + boot ======================= */', PAGE)
io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
print("observation page added")
