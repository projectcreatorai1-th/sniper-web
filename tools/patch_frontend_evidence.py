"""Patch: add Phase 3 Evidence page to web/frontend/app.js (idempotent)."""
import io

PATH = "web/frontend/app.js"
src = io.open(PATH, encoding="utf-8").read()

if "pageEvidence" in src:
    print("already patched")
    raise SystemExit(0)

src = src.replace('  ["#/observation", "Observation"],',
                  '  ["#/observation", "Observation"],\n  ["#/evidence", "Evidence"],')
src = src.replace('  "/observation": pageObservation,',
                  '  "/observation": pageObservation,\n  "/evidence": pageEvidence,')

PAGE = r'''
/* ---------- Evidence (Phase 3: external evidence + candidates) ---------- */
function pageEvidence(page) {
  const resultBox = el("div");
  const importBox = el("div");
  const detailBox = el("div");
  const candBox = el("div");

  function relBadge(rel) {
    const cls = { supports: "pass-true", contradicts: "pass-false",
                  context_for: "sev-INFO" }[rel] || "st-UNKNOWN";
    return el("span", { class: "badge " + cls }, rel);
  }

  async function loadList() {
    const d = await apiGet("/api/evidence/external");
    resultBox.replaceChildren(el("div", { class: "card" },
      el("h2", null, "External Evidence (" + d.count + ")"),
      d.count === 0 ? el("p", { class: "sub" },
        "\\u0e22\\u0e31\\u0e07\\u0e44\\u0e21\\u0e48\\u0e21\\u0e35 external evidence — \\u0e01\\u0e14 Import Myfxbook \\u0e14\\u0e49\\u0e32\\u0e19\\u0e25\\u0e48\\u0e32\\u0e07") :
      dataTable(["ID", "Source", "URL", "Retrieved", "Period", "Status", "Quality", "Metrics", "Snapshots"],
        d.evidence.map(e => el("tr", { class: "row-expand", onclick: () => loadDetail(e.evidence_id) },
          el("td", null, e.evidence_id),
          el("td", null, e.source_type),
          el("td", { class: "na", title: e.source_url },
             (e.source_url || "").slice(0, 40) + ((e.source_url || "").length > 40 ? "\\u2026" : "")),
          el("td", null, e.retrieved_at || "?"),
          el("td", null, (e.period_start || "?") + " \\u2192 " + (e.period_end || "?")),
          el("td", null, el("span", { class: "badge " + (e.status === "SUPERSEDED" ? "sev-INFO" : "st-OBSERVED_FROM_TESTING") }, e.status)),
          el("td", null, e.quality || "UNKNOWN"),
          el("td", null, String((e.extracted_metrics || []).length)),
          el("td", null, String(e.snapshots))))),
      el("p", { class: "sub" },
        "\\u0e04\\u0e25\\u0e34\\u0e01\\u0e41\\u0e16\\u0e27\\u0e40\\u0e1e\\u0e37\\u0e48\\u0e2d\\u0e14\\u0e39\\u0e23\\u0e32\\u0e22\\u0e25\\u0e30\\u0e40\\u0e2d\\u0e35\\u0e22\\u0e14 \\u00b7 metrics \\u0e40\\u0e1b\\u0e47\\u0e19 OBSERVED_EXTERNAL_METRIC \\u2014 \\u0e44\\u0e21\\u0e48\\u0e43\\u0e0a\\u0e48\\u0e2b\\u0e25\\u0e31\\u0e01\\u0e10\\u0e32\\u0e19\\u0e2a\\u0e39\\u0e15\\u0e23\\u0e20\\u0e32\\u0e22\\u0e43\\u0e19 EA")));
    loadConflicts();
    loadCandidates();
  }

  async function loadConflicts() {
    const d = await apiGet("/api/evidence/conflicts");
    candBox.replaceChildren();   // candidates reload separately below
  }

  async function loadDetail(eid) {
    const d = await apiGet("/api/evidence/" + eid);
    const e = d.evidence;
    detailBox.replaceChildren(el("div", { class: "card" },
      el("h2", null, e.evidence_id + " — " + e.source_type),
      el("div", { class: "metric-grid" },
        metric("Status", e.status), metric("Quality", e.quality || "UNKNOWN"),
        metric("Retrieved", e.retrieved_at || "?"),
        metric("Period", (e.period_start || "UNKNOWN") + " \\u2192 " + (e.period_end || "UNKNOWN")),
        metric("Broker", e.broker || "UNKNOWN"),
        metric("Platform", e.platform || "UNKNOWN"),
        metric("Environment match", d.environment_comparison.overall)),
      el("p", { class: "sub" }, "URL: " + (e.source_url || "\\u2014")),
      el("h3", null, "Metrics (OBSERVED_EXTERNAL_METRIC)"),
      (e.extracted_metrics || []).length === 0 ? el("p", { class: "sub" }, "\\u0e44\\u0e21\\u0e48\\u0e21\\u0e35") :
      dataTable(["Metric", "Value", "Period"],
        e.extracted_metrics.map(m => el("tr", null,
          el("td", null, m.key), numCell(m.value, 4),
          el("td", null, (m.period_start || "?") + " \\u2192 " + (m.period_end || "?"))))),
      el("h3", null, "Snapshots (" + d.snapshots.length + ")"),
      dataTable(["Snapshot", "Retrieved", "Content hash", "Metrics hash"],
        d.snapshots.map(s => el("tr", null,
          el("td", null, s.snapshot_id), el("td", null, s.retrieved_at),
          el("td", { class: "na", title: s.content_hash }, s.content_hash.slice(0, 16) + "\\u2026"),
          el("td", { class: "na", title: s.metrics_hash }, s.metrics_hash.slice(0, 16) + "\\u2026")))),
      el("h3", null, "Links (Evidence \\u2192 Assumption/Observation)"),
      linkForm(eid),
      (d.links || []).length === 0 ? el("p", { class: "sub" }, "\\u0e44\\u0e21\\u0e48\\u0e21\\u0e35 link") :
      dataTable(["Link", "Target", "Relation", "Confirmed by", "Actions"],
        d.links.map(l => el("tr", null,
          el("td", null, l.link_id),
          el("td", null, l.target_type + ":" + l.target_id),
          el("td", null, relBadge(l.relation)),
          el("td", null, l.confirmed_by ||
            el("span", { class: "badge sev-WARNING" }, "unconfirmed")),
          el("td", null,
            l.confirmed_by ? "\\u2014" :
            el("button", { class: "btn-ghost btn-small", onclick: () => confirmLink(eid, l.link_id) }, "Confirm")))))),
      el("p", { class: "sub" },
        "INDIRECT evidence \\u0e17\\u0e33\\u0e44\\u0e14\\u0e40\\u0e09\\u0e32\\u0e30 context_for/contradicts \\u2014 \\u0e2b\\u0e49\\u0e32\\u0e21 supports \\u0e2a\\u0e39\\u0e15\\u0e23 (gate \\u0e01\\u0e23\\u0e2d\\u0e07\\u0e1a\\u0e19 server)")));
  }

  function linkForm(eid) {
    const target = el("input", { placeholder: "ASSUMPTION id \\u0e40\\u0e0a\\u0e48\\u0e19 GRID_DISTANCE_DOC_001", style: "flex:1;min-width:200px;padding:5px 8px;border:1px solid #dcdce4;border-radius:7px" });
    const rel = el("select", { style: "padding:5px" },
      el("option", { value: "context_for" }, "context_for"),
      el("option", { value: "supports" }, "supports"),
      el("option", { value: "contradicts" }, "contradicts"));
    return el("div", { class: "chip-row", style: "margin:6px 0" },
      target, rel,
      el("button", { class: "btn-ghost btn-small", onclick: async () => {
        try {
          await apiPost("/api/evidence/" + eid + "/link", {
            target_type: "ASSUMPTION", target_id: target.value.trim(),
            relation: rel.value });
          loadDetail(eid);
        } catch (err) { detailBox.append(errorBox(err)); }
      } }, "Link"));
  }

  async function confirmLink(eid, linkId) {
    const reviewer = "web-user";
    try {
      await apiPost("/api/evidence/" + eid + "/confirm",
                    { link_id: linkId, confirmed_by: reviewer, note: "confirmed via web UI" });
      loadDetail(eid);
    } catch (err) { detailBox.append(errorBox(err)); }
  }

  async function doImport(ev) {
    const b = ev.target;
    const url = $("#mf_url").value.trim();
    if (!url) { importBox.replaceChildren(errorBox({ message: "\\u0e43\\u0e2a\\u0e48 URL" })); return; }
    busy(b, true, "\\u0e19\\u0e33\\u0e40\\u0e02\\u0e49\\u0e32\\u2026");
    try {
      const d = await apiPost("/api/evidence/myfxbook/import", { url });
      importBox.replaceChildren(el("div", { class: "card" },
        el("h2", null, "\\u0e19\\u0e33\\u0e40\\u0e02\\u0e49\\u0e32\\u0e2a\\u0e33\\u0e40\\u0e23\\u0e47\\u0e08: " + d.evidence.evidence_id),
        el("p", { class: "sub" },
          "metrics " + d.evidence.extracted_metrics.length + " \\u0e15\\u0e31\\u0e27 \\u00b7 snapshot " +
          d.snapshot.snapshot_id + " \\u00b7 quality " + d.evidence.quality),
        (d.warnings || []).length ? el("ul", { class: "issue-list" },
          d.warnings.map(w => el("li", null, el("span", { class: "na" }, w)))) : null));
      loadList();
    } catch (err) { importBox.replaceChildren(errorBox(err)); }
    busy(b, false);
  }

  async function loadCandidates() {
    const d = await apiGet("/api/model-candidates");
    candBox.replaceChildren(el("div", { class: "card" },
      el("h2", null, "Model Candidates (" + d.candidates.length + ")"),
      el("p", { class: "sub" },
        "Evidence \\u2192 Candidate \\u2192 Human Review \\u2192 Confirm \\u2192 Model Version — \\u0e2b\\u0e49\\u0e32\\u0e21 auto-accept"),
      d.candidates.length === 0 ? el("p", { class: "sub" }, "\\u0e44\\u0e21\\u0e48\\u0e21\\u0e35 candidate") :
      dataTable(["ID", "Rule", "Description", "Evidence", "Status", "Reviewed by", "Actions"],
        d.candidates.map(c => el("tr", null,
          el("td", null, c.candidate_id), el("td", null, c.rule_type),
          el("td", null, c.description),
          el("td", null, (c.source_evidence_ids || []).join(", ") || "\\u2014"),
          el("td", null, el("span", { class: "badge " +
            (c.status === "ACCEPTED" ? "pass-true" : c.status === "REJECTED" ? "pass-false" : "sev-INFO") }, c.status)),
          el("td", null, c.reviewed_by || "\\u2014"),
          el("td", null, c.status === "CANDIDATE" ?
            el("span", { class: "chip-row" },
              el("button", { class: "btn-ghost btn-small", onclick: () => reviewCandidate(c.candidate_id, "confirm") }, "Accept"),
              el("button", { class: "btn-ghost btn-small", onclick: () => reviewCandidate(c.candidate_id, "reject") }, "Reject")) :
            "\\u2014")))),
      el("p", { class: "sub" }, "Accept \\u0e15\\u0e49\\u0e2d\\u0e07\\u0e21\\u0e35 confirmation \\u0e40\\u0e2a\\u0e21\\u0e2d (reviewer name + conflict-free) \\u0e40\\u0e2a\\u0e21\\u0e2d")));
  }

  async function reviewCandidate(cid, action) {
    const reviewer = prompt("Reviewer name (human confirmation \\u0e08\\u0e33\\u0e40\\u0e1b\\u0e47\\u0e19):");
    if (!reviewer) return;
    try {
      await apiPost("/api/model-candidates/" + cid + "/" + action,
                    { reviewed_by: reviewer, note: "via web UI" });
      loadCandidates();
    } catch (err) { candBox.append(errorBox(err)); }
  }

  page.append(
    el("h1", { class: "page-title" }, "External Evidence & Model Candidates"),
    el("p", { class: "page-sub" },
      "\\u0e19\\u0e33\\u0e40\\u0e02\\u0e49\\u0e32\\u0e2b\\u0e25\\u0e31\\u0e01\\u0e10\\u0e32\\u0e19\\u0e20\\u0e32\\u0e22\\u0e19\\u0e2d\\u0e01 (Myfxbook) \\u2192 \\u0e40\\u0e01\\u0e47\\u0e1a\\u0e40\\u0e1b\\u0e47\\u0e19 evidence \\u0e17\\u0e35\\u0e48 trace \\u0e44\\u0e14\\u0e49 \\u0e40\\u0e0a\\u0e37\\u0e48\\u0e2d\\u0e21\\u0e01\\u0e31\\u0e1a Assumption/Observation \\u0e41\\u0e25\\u0e30 Candidate Rules"),
    el("div", { class: "banner" },
      el("b", null, "External performance data does not prove internal EA formulas."),
      " — metrics \\u0e40\\u0e1b\\u0e47\\u0e19 OBSERVED_EXTERNAL_METRIC \\u0e2a\\u0e33\\u0e2b\\u0e23\\u0e31\\u0e1a context/cross-check \\u0e40\\u0e17\\u0e48\\u0e32\\u0e19\\u0e31\\u0e49\\u0e19"),
    el("div", { class: "card" },
      el("h2", null, "Import Myfxbook"),
      el("div", { class: "chip-row" },
        el("input", { id: "mf_url", placeholder: "https://www.myfxbook.com/members/...", style: "flex:1;min-width:260px;padding:7px 9px;border:1px solid #dcdce4;border-radius:7px" }),
        el("button", { class: "btn-primary", onclick: doImport }, "Import")),
      el("p", { class: "sub" }, "\\u0e16\\u0e49\\u0e32\\u0e40\\u0e02\\u0e49\\u0e32\\u0e44\\u0e21\\u0e48\\u0e44\\u0e14\\u0e49 \\u0e23\\u0e30\\u0e1a\\u0e1a\\u0e08\\u0e30\\u0e23\\u0e32\\u0e22\\u0e07\\u0e32\\u0e19 IMPORT_FAILED \\u0e1e\\u0e23\\u0e49\\u0e2d\\u0e21\\u0e40\\u0e2b\\u0e15\\u0e38\\u0e1c\\u0e25 \\u2014 \\u0e44\\u0e21\\u0e48\\u0e21\\u0e35 fallback \\u0e02\\u0e49\\u0e2d\\u0e21\\u0e39\\u0e25\\u0e1b\\u0e25\\u0e2d\\u0e21"),
      importBox),
    resultBox, detailBox, candBox);
  loadList();
}

/* ======================= router + boot ======================= */'''

PAGE = PAGE.encode("utf-8").decode("unicode_escape")
src = src.replace('/* ======================= router + boot ======================= */', PAGE)
io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
print("evidence page added")
