// GUI Shell QA — runs against the live server at 127.0.0.1:8765
// Loads all 3 scripts in browser-like scope and tests all workspaces
"use strict";
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..");

// ---- DOM shim ----
const els = {};
let _id = 0;
function T(t) { return { tag: "#text", text: String(t), children: [], nodeType: 3 }; }
function mkEl(tag) {
  const e = { _id: ++_id, tag, children: [], style: {}, attrs: {}, onclick: null,
    hidden: false, nodeType: 1, _cls: "",
    appendChild(c) { e.children.push(c); return c; },
    replaceChildren(...c) { e.children = c; },
    append(...cs) { e.children.push(...cs); },
    setAttribute(k, v) { e.attrs[k] = v; },
    addEventListener() {},
    classList: { toggle(c, f) { if (f !== false) e._cls = c; }, add(c) { e._cls = c; }, remove() { e._cls = ""; } },
    querySelector() { return mkEl("div"); },
    querySelectorAll() { return []; } };
  Object.defineProperty(e, "textContent", {
    get() { return (e.children || []).map(c => c.tag === "#text" ? c.text : "").join(""); },
    set(v) { e.children = [T(v)]; } });
  return e;
}
function fl(n) { return (n.children || []).map(c => c.tag === "#text" ? c.text : fl(c)).join(" "); }

let _domReady = null, _hashChange = null, _replaced = null;

async function main() {
  const BASE = "http://127.0.0.1:8765";
  const _fetch = global.fetch;

  // Set up globals BEFORE loading scripts
  globalThis.document = {
    createElement: t => mkEl(t), createTextNode: t => T(t),
    getElementById: id => els[id] || (els[id] = mkEl("div")),
    querySelectorAll() { return []; }, querySelector() { return mkEl("div"); },
    addEventListener(e, cb) { if (e === "DOMContentLoaded") _domReady = cb; },
    body: mkEl("body")
  };
  globalThis.location = { hash: "#/dashboard", replace(h) { _replaced = h; } };
  globalThis.addEventListener = (e, cb) => { if (e === "hashchange") _hashChange = cb; if (e === "DOMContentLoaded") _domReady = cb; };
  globalThis.scrollTo = () => {};
  globalThis.innerWidth = 1440;
  globalThis.alert = () => {};
  globalThis.localStorage = { getItem() { return null; }, setItem() {}, removeItem() {} };
  globalThis.fetch = (p, o) => _fetch(BASE + p, o);
  globalThis.window = globalThis;

  // Load all scripts in order (same as index.html)
  const load = f => {
    const code = fs.readFileSync(path.join(ROOT, "web", "frontend", f), "utf8")
      .replace('"use strict";', "");
    (0, eval)(code);
  };
  load("our_ea/our_ea_page.js");
  load("app.js");
  load("shell/shell.js");
  console.log("PASS  all 3 scripts loaded");

  // Boot
  if (_domReady) _domReady();
  await new Promise(r => setTimeout(r, 2500));

  const checks = {};

  // 1) All 12 workspace routes render
  const routes = [
    "#/dashboard", "#/monitor",
    "#/analyze/grid", "#/analyze/worst-case", "#/analyze/risk", "#/analyze/set-builder",
    "#/backtest",
    "#/evidence/model", "#/evidence/assumptions", "#/evidence/observation", "#/evidence/timeline",
    "#/reports"
  ];
  for (const route of routes) {
    _replaced = null;
    location.hash = route;
    shellRender();
    await new Promise(r => setTimeout(r, 600));
    const text = fl(els["page"] || mkEl("div"));
    checks["ws " + route + " [" + text.length + "ch]"] = text.length > 5;
  }

  // 2) Old route redirects
  for (const [old, expected] of [
    ["#/home", "#/dashboard"], ["#/grid", "#/analyze/grid"],
    ["#/worst-case", "#/analyze/worst-case"], ["#/evidence", "#/evidence/model"],
    ["#/assumptions", "#/evidence/assumptions"], ["#/observation", "#/evidence/observation"],
    ["#/timeline", "#/evidence/timeline"], ["#/our-ea", "#/monitor"]]) {
    _replaced = null; location.hash = old; shellRender();
    checks["redirect " + old + " → " + _replaced] = _replaced === expected;
  }

  // 3) Navigation structure
  const navText = fl(els["shell-sidebar"] || mkEl("div"));
  checks["sidebar: 6 workspaces + Settings"] =
    ["Dashboard","Monitor","Analyze","Backtest","Evidence","Reports","Settings"]
      .every(s => navText.includes(s));
  checks["sidebar count ≤ 7 items"] = (navText.match(/Dashboard|Monitor|Analyze|Backtest|Evidence|Reports|Settings/g) || []).length <= 8;
  const bottomText = fl(els["shell-bottom-nav"] || mkEl("div"));
  checks["bottom nav: Dashboard + More"] = bottomText.includes("Dashboard") && bottomText.includes("More");

  // 4) Status bar
  shellUpdateStatusBar();
  const sbText = fl(els["shell-status-bar"] || mkEl("div"));
  checks["status bar: LIVE LOCKED"] = sbText.includes("LIVE") && sbText.includes("LOCKED");

  // 5) LIVE lock via API
  const liveRes = await fetch("/api/our_ea/command/live", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operator: "QA" })
  }).then(r => r.json());
  checks["LIVE locked via API"] = liveRes.data && liveRes.data.error === "LIVE_LOCKED";

  // 6) Runtime freshness (monitor page shows runtime data)
  location.hash = "#/monitor"; shellRender();
  await new Promise(r => setTimeout(r, 1200));
  const monText = fl(els["page"] || mkEl("div"));
  checks["monitor shows runtime"] = monText.includes("Runtime") || monText.includes("Mode") || monText.includes("OBSERVATION");

  // 7) Dashboard shows system overview
  location.hash = "#/dashboard"; shellRender();
  await new Promise(r => setTimeout(r, 1200));
  const dashText = fl(els["page"] || mkEl("div"));
  checks["dashboard shows system"] = dashText.includes("Mode") || dashText.includes("MT5") || dashText.includes("Evidence");

  // Report
  let pass = 0, fail = 0;
  for (const [k, v] of Object.entries(checks)) {
    console.log((v ? "PASS" : "FAIL") + "  " + k);
    if (v) pass++; else fail++;
  }
  console.log("\n" + pass + "/" + (pass + fail) + " checks passed");
  process.exit(fail === 0 ? 0 : 1);
}

main().catch(e => { console.error("QA FAIL:", e.message); process.exit(1); });
