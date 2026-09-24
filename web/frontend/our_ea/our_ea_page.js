/* OUR EA runtime page (P2 live rewrite).
   Source of truth = the live runtime service via /api/our_ea/* —
   NEVER a static export. Every render checks freshness: provenance
   (runtime version / manifest hash / trace) must come from the API; a
   mismatched or unreachable runtime shows STALE / OFFLINE, never
   silently accepted as current. */
let _ourEaTimer = null;

function pageOurEa(page) {
  page.appendChild(el("h2", {}, "OUR EA — Runtime"));
  page.appendChild(el("p", { class: "page-sub" },
    "Runtime Service สด (mode/state/risk/health) — อ่านจาก /api/our_ea/*"));
  const box = el("div", { class: "card" });
  box.appendChild(el("p", {}, "กำลังเชื่อมต่อ runtime…"));
  page.appendChild(box);
  const actions = el("div", { class: "card" });
  page.appendChild(actions);
  renderOurEaRuntime(box, actions, true);
}

function ourEaStopTimer() {
  if (_ourEaTimer) { clearInterval(_ourEaTimer); _ourEaTimer = null; }
}

async function fetchOurEa(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error("HTTP " + res.status);
  const j = await res.json();
  return j.data || j;        // tolerate {ok,data} envelope or bare
}

async function renderOurEaRuntime(box, actions, first) {
  let health, status;
  try {
    health = await fetchOurEa("/api/our_ea/health");
    status = await fetchOurEa("/api/our_ea/status");
  } catch (e) {
    ourEaStopTimer();
    box.replaceChildren(
      el("h3", {}, "OFFLINE — runtime service unavailable"),
      el("p", { class: "muted" },
        "ตรวจว่าเซิร์ฟเวอร์ (single instance) เปิดอยู่ — " + e.message));
    const retry = el("button", { class: "btn" }, "Reconnect");
    retry.onclick = () => renderOurEaRuntime(box, actions, true);
    actions.replaceChildren(retry);
    return;
  }
  if (first) {               // single auto-refresh loop (5s)
    ourEaStopTimer();
    _ourEaTimer = setInterval(
      () => renderOurEaRuntime(box, actions, false), 5000);
  }

  const prov = status.provenance || health.provenance;
  const fresh = prov && prov.manifest_hash && prov.manifest_hash !== "NOT_FOUND";
  box.replaceChildren();
  if (!fresh) box.appendChild(el("p", { class: "muted" },
    "STALE — runtime ไม่ได้แนบ provenance ที่ตรวจสอบได้"));

  const head = el("div", { class: "kv" });
  head.appendChild(el("div", {}, "Runtime : " + (prov ? prov.runtime_version : "?")));
  head.appendChild(el("div", {}, "Mode : " + status.mode));
  head.appendChild(el("div", {}, "MT5 : " + status.mt5_connection));
  head.appendChild(el("div", {}, "LIVE : " + status.live_lock));
  head.appendChild(el("div", {}, "Manifest : " + (prov && prov.manifest_hash ? prov.manifest_hash.slice(0, 12) + "…" : "?")));
  head.appendChild(el("div", {}, "Frozen : " + String(status.evidence_model_hash || "?").slice(0, 12) + "…"));
  head.appendChild(el("div", {}, "Session : " + (prov ? prov.session_id : "-")));
  head.appendChild(el("div", {}, "PID : " + health.server_pid + " · UTC " +
    (prov ? String(prov.timestamp_utc).replace("T", " ").slice(0, 19) : "-")));
  box.appendChild(head);

  const badges = el("div", {});
  badges.style.display = "flex"; badges.style.gap = "6px";
  badges.appendChild(ourEaBadge(status.mode));
  badges.appendChild(ourEaBadge(health.status));
  badges.appendChild(ourEaBadge("MT5 " + health.mt5_connection));
  badges.appendChild(ourEaBadge(status.live_lock === "LOCKED" ? "LOCKED" : "?"));
  box.appendChild(badges);

  box.appendChild(el("h3", {}, "Runtime detail"));
  const gt = el("table", { class: "tbl" });
  gt.appendChild(row("field", "value"));
  [["runtime_version", prov && prov.runtime_version],
   ["state_version", prov && prov.state_version],
   ["trace_id", prov && prov.trace_id],
   ["lifecycle", status.lifecycle],
   ["release_status", status.release_status],
   ["evidence_model", status.evidence_model_version],
   ["reconciliation", health.reconciliation],
   ["risk_state", health.risk_state],
  ].forEach(([k, v]) => gt.appendChild(row(k, String(v))));
  box.appendChild(gt);

  renderOurEaActions(actions);
}

function renderOurEaActions(actions) {
  actions.replaceChildren(el("h3", {}, "Operator commands (audit-logged)"));
  const opInput = el("input", { type: "text", placeholder: "operator id" });
  opInput.style.marginRight = "8px";
  actions.appendChild(opInput);
  const mk = (label, path, extra) => {
    const b = el("button", { class: "btn" }, label);
    b.style.margin = "0 6px 6px 0";
    b.onclick = async () => {
      const body = Object.assign({ operator: opInput.value }, extra || {});
      try {
        const res = await fetch(path, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body)
        });
        alert(JSON.stringify(await res.json(), null, 1));
      } catch (e) { alert("command failed: " + e.message); }
    };
    return b;
  };
  actions.appendChild(mk("Start OBSERVATION",
    "/api/our_ea/command/start_observation"));
  actions.appendChild(mk("Promote SHADOW",
    "/api/our_ea/command/promote_shadow"));
  actions.appendChild(mk("Promote DEMO (blocked)",
    "/api/our_ea/command/promote_demo"));
  actions.appendChild(mk("KILL (emergency)",
    "/api/our_ea/command/kill",
    { layer: "GLOBAL_EMERGENCY_KILL", reason: "UI kill" }));
  actions.appendChild(mk("Request LIVE (audit probe)",
    "/api/our_ea/command/live"));
  const refresh = el("button", { class: "btn" }, "Refresh now");
  refresh.onclick = () => { const p = $("#page"); p.replaceChildren(); pageOurEa(p); };
  actions.appendChild(refresh);
  actions.appendChild(el("p", { class: "muted" },
    "ไม่มี trading endpoint ใน P0-P3 · LIVE ถูกปฏิเสธเสมอ · ทุกคำสั่งบันทึกใน event ledger"));
}

/* ---------- shared helpers ---------- */
function ourEaBadge(status) {
  const colors = {
    VERIFIED: ["#e2f4e6", "#1c7c3c"], PARTIAL: ["#fdf0d5", "#8a6d1a"],
    UNKNOWN: ["#ececf1", "#565b69"], REJECTED: ["#fbe3e3", "#a33"],
    PASS: ["#e2f4e6", "#1c7c3c"], PASS_WITH_UNKNOWN: ["#e3ecfd", "#2a5db0"],
    FAIL: ["#fbe3e3", "#a33"], RUNNING: ["#e3ecfd", "#2a5db0"],
    LOCKED: ["#fbe3e3", "#a33"], OBSERVATION: ["#e2f4e6", "#1c7c3c"],
    SHADOW: ["#e3ecfd", "#2a5db0"], INIT: ["#ececf1", "#565b69"],
  };
  const key = String(status).replace("MT5 ", "");
  const c = colors[key] || ["#ececf1", "#565b69"];
  const b = el("span", { class: "badge" }, String(status));
  b.style.background = c[0]; b.style.color = c[1];
  return b;
}

function row(a, b) {
  const tr = el("tr", {});
  tr.appendChild(el("td", {}, String(a)));
  tr.appendChild(el("td", {}, String(b)));
  return tr;
}
