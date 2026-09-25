/* SNIPER Unified Shell — 6 Workspaces + Responsive Desktop/Mobile
   Master Command §5-§43: ONE PROGRAM · ONE MAIN WINDOW · SIX WORKSPACES

   Route compatibility: old 13 routes redirect into workspaces.
   Runtime source: /api/our_ea/* (never stale export).
   Inspector: right panel (desktop) / bottom sheet (mobile).
   Event Stream: bottom panel (desktop) / drawer (mobile).
   LIVE always LOCKED. No fake data. No MT5 connection. */

"use strict";

/* ======================= workspace configuration ======================= */
const WORKSPACES = [
  { id: "dashboard", label: "Dashboard", icon: "▣", route: "#/dashboard",
    desc: "System overview" },
  { id: "monitor", label: "Monitor", icon: "◉", route: "#/monitor",
    desc: "OUR EA runtime" },
  { id: "analyze", label: "Analyze", icon: "◈", route: "#/analyze/grid",
    desc: "Grid · Worst Case · Risk · Set Builder",
    tools: [
      { id: "grid", label: "Grid", route: "#/analyze/grid", page: "pageGrid" },
      { id: "worst-case", label: "Worst Case", route: "#/analyze/worst-case", page: "pageWorstCase" },
      { id: "risk", label: "Risk", route: "#/analyze/risk", page: "pageRisk" },
      { id: "set-builder", label: "Set Builder", route: "#/analyze/set-builder", page: "pageSetBuilder" },
    ]},
  { id: "backtest", label: "Backtest", icon: "▤", route: "#/backtest",
    desc: "Report analysis" },
  { id: "evidence", label: "Evidence", icon: "◈", route: "#/evidence/model",
    desc: "Model · Assumptions · Observation · Timeline",
    tools: [
      { id: "model", label: "Model", route: "#/evidence/model", page: "pageEvidence" },
      { id: "assumptions", label: "Assumptions", route: "#/evidence/assumptions", page: "pageAssumptions" },
      { id: "observation", label: "Observation", route: "#/evidence/observation", page: "pageObservation" },
      { id: "timeline", label: "Timeline", route: "#/evidence/timeline", page: "pageTimeline" },
    ]},
  { id: "reports", label: "Reports", icon: "▥", route: "#/reports",
    desc: "Generate · Export" },
];

/* old route → workspace route mapping (route compatibility §26) */
const ROUTE_MAP = {
  "#/home": "#/dashboard",
  "#/our-ea": "#/monitor",
  "#/grid": "#/analyze/grid",
  "#/worst-case": "#/analyze/worst-case",
  "#/risk": "#/analyze/risk",
  "#/set-builder": "#/analyze/set-builder",
  "#/backtest": "#/backtest",
  "#/evidence": "#/evidence/model",
  "#/assumptions": "#/evidence/assumptions",
  "#/observation": "#/evidence/observation",
  "#/timeline": "#/evidence/timeline",
  "#/reports": "#/reports",
  "#/settings": "#/settings",
};

/* runtime state store (centralized §30) */
const ShellRuntime = {
  data: null, lastFetch: 0, status: "OFFLINE", listeners: [],
  async refresh() {
    try {
      const r = await fetch("/api/our_ea/status");
      if (!r.ok) throw new Error("HTTP " + r.status);
      const j = await r.json();
      this.data = j.data || j;
      this.status = "LIVE";
      this.lastFetch = Date.now();
    } catch (e) {
      this.status = this.lastFetch && Date.now() - this.lastFetch < 15000 ? "STALE" : "OFFLINE";
    }
    this.listeners.forEach(fn => { try { fn(this); } catch (e) {} });
  },
  on(fn) { this.listeners.push(fn); },
  freshness() {
    if (this.status === "OFFLINE") return "OFFLINE";
    const s = Math.round((Date.now() - this.lastFetch) / 1000);
    if (this.status === "STALE" || s > 15) return "STALE (" + s + "s ago)";
    return "Updated " + s + "s ago";
  },
};

/* ======================= DOM helpers ======================= */
function _el(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
    else if (k === "class") n.className = v;
    else if (k === "hidden") n.hidden = !!v;
    else n.setAttribute(k, v);
  }
  for (const k of kids) if (k !== null && k !== undefined)
    n.append(k.nodeType ? k : document.createTextNode(String(k)));
  return n;
}

/* ======================= shell render ======================= */
let _shellCurrent = null;

function shellInit() {
  shellBuildNav();
  shellRender();
  window.addEventListener("hashchange", shellRender);
  ShellRuntime.refresh();
  setInterval(() => ShellRuntime.refresh(), 5000);
  setInterval(() => shellUpdateStatusBar(), 5000);
}

function shellBuildNav() {
  const sidebar = document.getElementById("shell-sidebar");
  if (!sidebar) return;
  sidebar.replaceChildren(
    ...WORKSPACES.map(ws => _el("a", {
      href: ws.route, "data-ws": ws.id, class: "shell-nav-item",
      onclick: (e) => { e.preventDefault(); shellNavigate(ws.route); }
    }, _el("span", { class: "shell-nav-icon" }, ws.icon),
       _el("span", { class: "shell-nav-label" }, ws.label))),
    _el("a", { href: "#/settings", "data-ws": "settings",
      class: "shell-nav-item shell-nav-settings",
      onclick: (e) => { e.preventDefault(); shellOpenSettings(); }
    }, _el("span", { class: "shell-nav-icon" }, "⚙"),
       _el("span", { class: "shell-nav-label" }, "Settings")));

  const bottomNav = document.getElementById("shell-bottom-nav");
  if (!bottomNav) return;
  const mobileWs = WORKSPACES.slice(0, 5);
  bottomNav.replaceChildren(
    ...mobileWs.map(ws => _el("a", {
      href: ws.route, "data-ws": ws.id, class: "shell-bottom-item",
      onclick: (e) => { e.preventDefault(); shellNavigate(ws.route); }
    }, _el("span", { class: "shell-bottom-icon" }, ws.icon),
       _el("span", { class: "shell-bottom-label" }, ws.label))),
    _el("a", { href: "#/more", class: "shell-bottom-item",
      onclick: (e) => { e.preventDefault(); shellToggleMore(); }
    }, _el("span", { class: "shell-bottom-icon" }, "⋯"),
       _el("span", { class: "shell-bottom-label" }, "More")));
}

function shellNavigate(route) {
  if (location.hash !== route) location.hash = route;
  else shellRender();
}

function shellToggleMore() {
  const menu = document.getElementById("shell-more-menu");
  if (menu) menu.classList.toggle("open");
}

function shellParseRoute() {
  let hash = location.hash || "#/dashboard";
  if (ROUTE_MAP[hash]) { location.replace(ROUTE_MAP[hash]); return null; }
  const parts = hash.slice(2).split("/");
  const wsId = parts[0] || "dashboard";
  const toolId = parts[1] || "";
  return { wsId, toolId, hash };
}

function shellFindPage(route) {
  const ws = WORKSPACES.find(w => w.id === route.wsId);
  if (!ws) return { ws: WORKSPACES[0], tool: null, pageFn: "pageDashboard" };
  if (ws.tools && route.toolId) {
    const tool = ws.tools.find(t => t.id === route.toolId);
    if (tool) return { ws, tool, pageFn: tool.page };
  }
  if (ws.tools) return { ws, tool: ws.tools[0], pageFn: ws.tools[0].page };
  const map = {
    dashboard: "pageDashboard", monitor: "pageOurEa",
    backtest: "pageBacktest", reports: "pageReports"
  };
  return { ws, tool: null, pageFn: map[ws.id] || "pageDashboard" };
}

function shellRender() {
  const route = shellParseRoute();
  if (!route) return;
  const { ws, tool, pageFn } = shellFindPage(route);
  _shellCurrent = { ws, tool, pageFn };

  document.querySelectorAll(".shell-nav-item").forEach(a =>
    a.classList.toggle("active", a.getAttribute("data-ws") === ws.id));
  document.querySelectorAll(".shell-bottom-item").forEach(a =>
    a.classList.toggle("active", a.getAttribute("data-ws") === ws.id));

  const header = document.getElementById("shell-ws-header");
  if (header) {
    header.replaceChildren();
    header.appendChild(_el("h1", { class: "ws-title" }, ws.label));
    if (ws.desc) header.appendChild(_el("span", { class: "ws-desc" }, ws.desc));
    if (ws.tools) {
      const tabs = _el("div", { class: "ws-tabs", role: "tablist" });
      ws.tools.forEach(t => {
        const b = _el("button", {
          class: "ws-tab" + (tool && tool.id === t.id ? " active" : ""),
          role: "tab", "aria-selected": tool && tool.id === t.id ? "true" : "false",
          onclick: () => shellNavigate(t.route)
        }, t.label);
        tabs.appendChild(b);
      });
      header.appendChild(tabs);
    }
  }

  const page = document.getElementById("page");
  if (page) page.replaceChildren();
  const fn = window[pageFn];
  if (typeof fn === "function") { try { fn(page); } catch (e) {
    page.appendChild(_el("p", { class: "muted" }, "Error rendering: " + e.message));
  }}
  window.scrollTo(0, 0);
}

/* ======================= settings drawer ======================= */
function shellOpenSettings() {
  const drawer = document.getElementById("shell-settings-drawer");
  if (!drawer) return;
  drawer.classList.add("open");
  const page = drawer.querySelector(".drawer-content");
  if (page) { page.replaceChildren(); if (typeof pageSettings === "function") pageSettings(page); }
}
function shellCloseSettings() {
  const d = document.getElementById("shell-settings-drawer");
  if (d) d.classList.remove("open");
}

/* ======================= inspector ======================= */
let _inspectorData = null;
function shellInspect(title, data) {
  _inspectorData = { title, data };
  const insp = document.getElementById("shell-inspector");
  if (!insp) return;
  insp.classList.add("open");
  const body = insp.querySelector(".inspector-body");
  if (!body) return;
  body.replaceChildren(_el("h3", {}, title));
  const tbl = _el("table", { class: "tbl" });
  tbl.appendChild(_el("tr", {}, _el("th", {}, "Field"), _el("th", {}, "Value")));
  const flat = (obj, prefix) => {
    for (const [k, v] of Object.entries(obj || {})) {
      const key = prefix ? prefix + "." + k : k;
      if (v && typeof v === "object" && !Array.isArray(v)) flat(v, key);
      else tbl.appendChild(_el("tr", {},
        _el("td", {}, key), _el("td", {}, String(v))));
    }
  };
  flat(data);
  body.appendChild(tbl);
}
function shellCloseInspector() {
  const i = document.getElementById("shell-inspector");
  if (i) i.classList.remove("open");
}

/* ======================= event stream ======================= */
function shellToggleEventStream() {
  const es = document.getElementById("shell-event-stream");
  if (es) es.classList.toggle("open");
}
async function shellRefreshEvents() {
  try {
    const r = await fetch("/api/our_ea/events");
    const j = await r.json();
    const events = (j.data && j.data.latest) || [];
    const body = document.getElementById("shell-event-body");
    if (body) {
      body.replaceChildren(...events.slice(0, 20).map(ev =>
        _el("div", { class: "es-row", onclick: () => shellInspect("Event " + ev.event_id, ev) },
          _el("span", { class: "es-time" }, String(ev.timestamp || "").slice(11, 19)),
          _el("span", { class: "es-type" }, ev.event_type || ""),
          _el("span", { class: "es-sev " + (ev.event_type === "SAFE_STOP" ? "es-crit" :
            ev.event_type === "MODEL_UNCERTAINTY" ? "es-warn" : "es-ok") },
            ev.event_type === "SAFE_STOP" ? "CRITICAL" :
            ev.event_type === "MODEL_UNCERTAINTY" ? "WARN" : "INFO"),
          _el("span", { class: "es-trace" }, ev.trace_id || ""))));
    }
  } catch (e) { /* offline */ }
}

/* ======================= status bar ======================= */
function shellUpdateStatusBar() {
  const bar = document.getElementById("shell-status-bar");
  if (!bar) return;
  const rt = ShellRuntime;
  const rtStatus = rt.status === "LIVE" ? "●" : rt.status === "STALE" ? "◐" : "○";
  bar.replaceChildren(
    _el("span", { class: "sb-item" + (rt.status === "LIVE" ? " sb-ok" : " sb-err") },
      "RUNTIME " + rtStatus + " " + rt.status),
    _el("span", { class: "sb-item" }, "DATA " + (rt.data ? "●" : "○")),
    _el("span", { class: "sb-item" }, "RISK " + (rt.data && rt.data.mode ? "●" : "○")),
    _el("span", { class: "sb-item" }, "EVIDENCE ●"),
    _el("span", { class: "sb-item sb-locked" }, "🔒 LIVE LOCKED"),
    _el("span", { class: "sb-item sb-fresh" }, rt.freshness()));
}

/* ======================= boot ======================= */
document.addEventListener("DOMContentLoaded", () => {
  shellInit();
  setInterval(shellRefreshEvents, 5000);
  shellRefreshEvents();
});

/* hamburger sidebar toggle (mobile) */
function shellToggleSidebar() {
  const sb = document.getElementById("shell-sidebar");
  if (!sb) return;
  if (window.innerWidth <= 768) {
    if (sb.style.display === "flex") { sb.style.display = "none"; }
    else { sb.style.display = "flex"; sb.style.position = "fixed"; sb.style.zIndex = "99";
      sb.style.top = "48px"; sb.style.left = "0"; sb.style.bottom = "56px"; sb.style.width = "200px"; }
  }
}
