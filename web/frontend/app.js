/* SNIPER CashFlow — Web frontend.
 * Contains NO calculation formulas: every number shown is computed by the
 * backend (which calls the shared core/). This file only collects inputs,
 * calls the API, and formats/renders results.
 */
"use strict";

/* ======================= tiny DOM helpers ======================= */
const $ = (sel, root) => (root || document).querySelector(sel);

function el(tag, attrs, ...kids) {
  const node = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined) continue;
      if (k === "class") node.className = v;
      else if (k === "checked") node.checked = !!v;
      else if (k === "disabled") node.disabled = !!v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    }
  }
  appendKids(node, kids);
  return node;
}
function appendKids(node, kids) {
  for (const k of kids.flat(Infinity)) {
    if (k === null || k === undefined || k === false || k === true) continue;
    node.append(k.nodeType ? k : document.createTextNode(String(k)));
  }
}

/* ======================= formatting (display only) ======================= */
function fmt(v, d) {
  if (v === null || v === undefined) return "N/A";
  if (typeof v !== "number" || !isFinite(v)) return String(v);
  const dig = (d === undefined) ? 2 : d;
  return v.toLocaleString("en-US", { minimumFractionDigits: dig, maximumFractionDigits: dig });
}
const fmtMoney = v => fmt(v, 2);
const fmtLot = v => fmt(v, 2);
const fmtPct = v => fmt(v, 2);

/* mobile-friendly card view (auto on narrow screens, user can toggle) */
function isNarrow() { return window.matchMedia("(max-width: 720px)").matches; }
function useCards() {
  if (S.ui.cards === "cards") return true;
  if (S.ui.cards === "table") return false;
  return isNarrow();
}
function viewToggle() {
  const mode = S.ui.cards || "auto";
  const label = mode === "cards" ? "การ์ด" : mode === "table" ? "ตาราง"
    : (useCards() ? "การ์ด (อัตโนมัติ)" : "ตาราง (อัตโนมัติ)");
  const next = mode === "cards" ? "table" : "cards";
  return el("button", { class: "btn-ghost btn-small", onclick: () => {
    S.ui.cards = next;
    if (S.ui.rerender) S.ui.rerender();
  } }, "มุมมอง: " + label + " ⇄");
}
function kv(k, v, neg) {
  return el("div", { class: "kv" },
    el("span", { class: "k" }, k),
    el("span", { class: "v" + (neg ? " neg" : "") }, v));
}

const STATUS_LABELS = {
  VERIFIED_FROM_DOCUMENTATION: "Verified / From-document",
  OBSERVED_FROM_TESTING: "Observed",
  MODEL_ASSUMPTION: "Model assumption",
  UNKNOWN: "Unknown",
};
function statusBadge(status) {
  return el("span", { class: "badge st-" + status, title: status },
            STATUS_LABELS[status] || status);
}
function sevBadge(sev) {
  return el("span", { class: "badge sev-" + sev }, sev);
}

/* ======================= state ======================= */
const LS_KEY = "sniper_web_state_v1";
const S = {
  meta: null,
  capital: 500,
  config: null,
  symbol_profile: null,
  account: null,
  thresholds: null,
  backtest: null,          // last backtest analyze result (memory only)
  ui: {
    wcMoves: new Set([10, 30, 50, 100]),
    wcScenarios: new Set(["BUY_ADVERSE", "SELL_ADVERSE", "BOTH_SIDES"]),
  },
};

function saveState() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify({
      capital: S.capital, config: S.config, symbol_profile: S.symbol_profile,
      account: S.account, thresholds: S.thresholds,
    }));
  } catch (e) { /* storage unavailable - state stays in memory */ }
}
function loadState() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) { return null; }
}

/* ======================= API ======================= */
async function apiGet(path) {
  const res = await fetch(path);
  const data = await res.json();
  if (!res.ok || !data.ok) throw apiError(res.status, data);
  return data.data;
}
async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok || !data.ok) throw apiError(res.status, data);
  return data.data;
}
async function apiUpload(path, formData) {
  const res = await fetch(path, { method: "POST", body: formData });
  let data = null;
  try { data = await res.json(); } catch (e) { /* non-JSON error body */ }
  if (!res.ok || !data || !data.ok) {
    throw apiError(res.status, data || { error: { message: "HTTP " + res.status } });
  }
  return data.data;
}
function apiError(status, data) {
  const err = new Error((data && data.error && data.error.message) || ("HTTP " + status));
  err.details = (data && data.error && data.error.details) || [];
  err.code = data && data.error && data.error.code;
  return err;
}
function calcBody(extra) {
  return Object.assign({
    config: S.config,
    symbol_profile: S.symbol_profile,
    account: S.account,
    capital: S.capital,
  }, extra || {});
}

/* ======================= shared UI pieces ======================= */
const DISCLAIMER = "Simulation Model — not verified internal EA formula";
function disclaimerBanner() {
  return el("div", { class: "banner" },
            el("b", null, DISCLAIMER),
            " — ตัวเลขทั้งหมดมาจากโมเดลจำลองของโปรแกรมวิเคราะห์ ไม่ใช่สูตรภายในที่ยืนยันจากไฟล์ EX5 ของ EA");
}
function errorBox(err) {
  const box = el("div", { class: "error-box" },
                 el("b", null, "เกิดข้อผิดพลาด: "), err.message || String(err));
  if (err.details && err.details.length) {
    box.appendChild(el("ul", null, err.details.map(d => el("li", null, d))));
  }
  return box;
}
function assumptionsBlock(data) {
  const details = (data && data.assumption_details) || [];
  if (!details.length) return el("div", { class: "asm-block muted" }, "ไม่มี assumption แนบมากับผลลัพธ์นี้");
  const chips = el("div", { class: "asm-chips" },
    details.map(d => el("span",
      { class: "badge st-" + d.status, title: (STATUS_LABELS[d.status] || d.status) + " — " + d.title },
      d.assumption_id)));
  const table = el("table", { class: "data" },
    el("tr", null,
      el("th", null, "Assumption ID"), el("th", null, "สถานะ"),
      el("th", null, "หัวข้อ"), el("th", null, "รายละเอียด"), el("th", null, "แหล่งอ้างอิง")),
    details.map(d => el("tr", null,
      el("td", null, d.assumption_id),
      el("td", null, statusBadge(d.status)),
      el("td", null, d.title),
      el("td", null, d.detail || "—"),
      el("td", null, d.source || "—"))));
  return el("div", { class: "asm-block" }, chips,
    el("details", { class: "asm-details" },
      el("summary", null, "ดูรายละเอียด Assumptions ทั้งหมด (" + details.length + ")"),
      el("div", { class: "table-wrap" }, table)));
}
function validationList(issues) {
  if (!issues || !issues.length) return el("p", { class: "sub" }, "ไม่มีคำเตือนจากการตรวจสอบค่า");
  return el("ul", { class: "issue-list" }, issues.map(i => el("li", null,
    sevBadge(i.severity),
    el("span", null, i.message),
    el("span", { class: "na" }, " [" + i.code + (i.parameter ? " · " + i.parameter : "") + "]"))));
}
function metric(k, v, small) {
  return el("div", { class: "metric" },
    el("div", { class: "k" }, k),
    el("div", { class: "v" }, v, small ? el("small", null, " " + small) : null));
}
function dataTable(headers, rows) {
  return el("div", { class: "table-wrap" },
    el("table", { class: "data" },
      el("tr", null, headers.map(h => el("th", null, h))),
      rows));
}
function numCell(v, d, cls) {
  const txt = fmt(v, d);
  const c = el("td", { class: (v < 0 ? "neg " : "") + (cls || "") }, txt);
  return c;
}
function busy(btn, on, busyText) {
  if (on) {
    btn.dataset.label = btn.textContent;
    btn.disabled = true;
    btn.textContent = busyText || "กำลังคำนวณ…";
  } else {
    btn.disabled = false;
    if (btn.dataset.label) btn.textContent = btn.dataset.label;
  }
}
function parseNumList(text) {
  return (text || "").split(/[,;\s]+/).map(s => s.trim()).filter(Boolean)
    .map(Number);
}

/* ======================= navigation ======================= */
const NAV = [
  ["#/home", "หน้าแรก"],
  ["#/settings", "EA Settings"],
  ["#/grid", "Grid Calculator"],
  ["#/worst-case", "Worst Case"],
  ["#/risk", "Risk Dashboard"],
  ["#/set-builder", "Set Builder"],
  ["#/backtest", "Backtest"],
  ["#/reports", "รายงาน"],
  ["#/assumptions", "Assumptions"],
  ["#/observation", "Observation"],
];
function buildNav() {
  const nav = $("#nav");
  nav.replaceChildren(
    ...NAV.map(([href, label]) =>
      el("a", { href, "data-route": href.slice(1) }, label)),
    el("a", { href: "/static/manual.html", target: "_blank" }, "คู่มือ 📘"));
}
function setActiveNav(route) {
  document.querySelectorAll("#nav a").forEach(a =>
    a.classList.toggle("active", a.getAttribute("data-route") === route));
}
function render() {
  if (!S.meta) return;
  const route = (location.hash || "#/home").slice(1) || "/home";
  const page = $("#page");
  page.replaceChildren();
  setActiveNav(route);
  const fn = ROUTES[route] || ROUTES["/home"];
  fn(page);
  window.scrollTo(0, 0);
}

/* ======================= pages ======================= */
function pageHome(page) {
  page.append(
    el("div", { class: "hero" },
      el("h1", null, "SNIPER CashFlow"),
      el("p", null, "เครื่องมือคำนวณ/จำลอง EA SNIPER CashFlow V1.68 — Grid, Lot, Basket Close, Worst Case และความเสี่ยง — ใช้ Calculation Core ชุดเดียวกับโปรแกรม Desktop ผลลัพธ์เหมือนกันเป๊ะเมื่อ input เหมือนกัน"),
      disclaimerBanner(),
      el("a", { class: "btn-gold", href: "#/settings", style: "display:inline-block;margin-top:14px;text-decoration:none;padding:12px 26px;font-size:16px" }, "เริ่มใช้ Calculator"),
      el("div", { class: "flow-steps" },
        ["1 · เลือก Preset", "2 · ใส่ทุน", "3 · Calculate", "4 · ดู Grid", "5 · ดู Worst Case", "6 · ดู Risk"]
          .map(s => el("span", { class: "flow-step" }, s)))),
    el("div", { class: "card" },
      el("h2", null, "คำอธิบายสั้น ๆ"),
      el("ul", null, [
        "EA SNIPER CashFlow V1.68 มีพารามิเตอร์ 27 ตัว (Grid, Lot Multiplier, Basket Close, Partial Close, Emergency, ตารางเวลา)",
        "เว็บนี้ให้กรอกค่าแล้วคำนวณผลจำลอง: ตาราง Grid, ทุน/มาร์จิ้น, สถานการณ์ตลาดวิ่งทางเดียว (Worst Case), ธงเตือนความเสี่ยง",
        "รองรับ preset ของผู้ขาย (ทุน $500 / $3000), สร้างชุดค่าผสม (Set Builder), นำเข้าผล Backtest จริง (CSV/HTML/TXT) และ export รายงาน",
        "ทุกตัวเลขแนบ Assumption IDs พร้อมสถานะ Verified / Observed / Model assumption / Unknown",
      ].map(t => el("li", { style: "margin:4px 0" }, t))),
      el("p", { class: "sub" },
        "ข้อมูลที่ขาดแสดงเป็น N/A เสมอ — โปรแกรมไม่เดาค่า ไม่จัดอันดับว่าค่าไหน \"ดีที่สุด\" และไม่รับประกันกำไร"),
      el("p", null,
        "📗 ยังใหม่กับโปรแกรม? เปิด ",
        el("a", { href: "/static/manual.html", target: "_blank", style: "color:#16213e;font-weight:700" },
          "คู่มือการใช้งานฉบับเต็ม"),
        " ได้ตลอดเวลา (หรือกดเมนู \"คู่มือ\" ด้านบน)")));
}

/* ---------- EA Settings ---------- */
function pageSettings(page) {
  const meta = S.meta;
  const basicGroups = ["Symbol / Grid", "Lot / Money Management"];
  const groups = [];
  for (const p of meta.parameter_meta) {
    if (!groups.length || groups[groups.length - 1].name !== p.group) {
      groups.push({ name: p.group, params: [] });
    }
    groups[groups.length - 1].params.push(p);
  }

  const resultBox = el("div");

  const profileSel = el("select", { id: "f_profile" },
    meta.profiles.map((p, i) => el("option", { value: String(i) }, p.name)));
  const matchedIdx = meta.profiles.findIndex(
    p => p.name === (S.symbol_profile && S.symbol_profile.name));
  profileSel.value = String(matchedIdx >= 0 ? matchedIdx : 0);
  const profileFields = ["contract_size", "tick_size", "lot_min", "lot_max", "lot_step", "digits", "reference_price"];
  const advProfile = el("details", { class: "advanced" },
    el("summary", null, "ตั้งค่า Symbol Profile ละเอียด (Broker constraints)"),
    el("div", { class: "form-grid" },
      profileFields.map(k => el("div", { class: "field" },
        el("label", null, k), el("input", { type: "number", step: "any", id: "pf_" + k, value: String(S.symbol_profile[k]) })))));
  const advAccount = el("details", { class: "advanced" },
    el("summary", null, "ตั้งค่าบัญชี (Leverage / Margin)"),
    el("div", { class: "form-grid" },
      el("div", { class: "field" }, el("label", null, "leverage (เช่น 500 = 1:500)"),
        el("input", { type: "number", step: "1", id: "ac_leverage", value: String(S.account.leverage) })),
      el("div", { class: "field" }, el("label", null, "margin_rate"),
        el("input", { type: "number", step: "any", id: "ac_margin_rate", value: String(S.account.margin_rate) }))));

  const paramInput = (p) => {
    const val = S.config[p.key];
    const id = "p_" + p.key;
    if (p.kind === "bool") {
      return el("div", { class: "field" },
        el("label", null, p.label),
        el("input", { type: "checkbox", id, checked: !!val, style: "width:20px;height:20px" }));
    }
    if (p.kind === "time") {
      return el("div", { class: "field" },
        el("label", null, p.label),
        el("input", { type: "text", id, value: val || "", placeholder: "HH:MM" }));
    }
    if (p.kind === "float") {
      return el("div", { class: "field" },
        el("label", null, p.label),
        el("input", { type: "number", step: "any", id, value: String(val) }));
    }
    return el("div", { class: "field" },
      el("label", null, p.label),
      el("input", { type: "text", id, value: val || "" }));
  };

  const advancedGroups = groups.filter(g => !basicGroups.includes(g.name));
  const basicCards = groups.filter(g => basicGroups.includes(g.name)).map(g =>
    el("div", { class: "card" },
      el("h3", { style: "margin-top:0" }, g.name),
      el("div", { class: "form-grid" }, g.params.map(paramInput))));
  const advancedCard = el("div", { class: "card" },
    el("details", { class: "advanced" },
      el("summary", null, "พารามิเตอร์ขั้นสูง (" +
        advancedGroups.map(g => g.params.length).reduce((a, b) => a + b, 0) +
        " ตัว) — Trailing / Partial Close / Emergency / Daily Target / Schedule"),
      advancedGroups.map(g => el("div", null,
        el("h3", null, g.name),
        el("div", { class: "form-grid" }, g.params.map(paramInput))))));

  function collect() {
    const problems = [];
    const config = Object.assign({}, S.config);
    for (const p of meta.parameter_meta) {
      const input = $("#p_" + p.key);
      if (!input) continue;
      if (p.kind === "bool") config[p.key] = input.checked;
      else if (p.kind === "float") {
        const v = parseFloat(input.value);
        if (input.value === "" || isNaN(v)) problems.push(p.label + " ต้องเป็นตัวเลข");
        else config[p.key] = v;
      } else config[p.key] = input.value;
    }
    const capital = parseFloat($("#f_capital").value);
    if (!isNaN(capital) && capital > 0) S.capital = capital;
    else problems.push("Capital ต้องเป็นตัวเลข > 0 (ใช้ค่าเดิมชั่วคราว)");

    const profile = Object.assign({}, S.symbol_profile);
    for (const k of profileFields) {
      const v = parseFloat($("#pf_" + k).value);
      if (isNaN(v)) problems.push("symbol_profile." + k + " ต้องเป็นตัวเลข");
      else profile[k] = v;
    }
    const account = Object.assign({}, S.account);
    const lev = parseFloat($("#ac_leverage").value);
    const mr = parseFloat($("#ac_margin_rate").value);
    if (!isNaN(lev)) account.leverage = lev;
    if (!isNaN(mr)) account.margin_rate = mr;

    return { config, profile, account, problems };
  }

  function doValidate(ev) {
    const btn = ev.target;
    const collected = collect();
    resultBox.replaceChildren();
    if (collected.problems.length) {
      resultBox.append(errorBox({ message: "แก้ค่าให้ครบก่อน", details: collected.problems }));
      return;
    }
    S.config = collected.config;
    S.symbol_profile = collected.profile;
    S.account = collected.account;
    saveState();
    busy(btn, true, "กำลังตรวจสอบ…");
    apiPost("/api/validate", calcBody({ capital: S.capital })).then(data => {
      busy(btn, false);
      const head = el("h3", null, "ผลการตรวจสอบ (" + data.issues.length + " รายการ" +
        (data.has_errors ? " — มี ERROR" : "") + ")");
      resultBox.replaceChildren(head, validationList(data.issues));
      if (!data.has_errors) {
        resultBox.append(el("div", null,
          el("a", { class: "next-link", href: "#/grid" }, "ถัดไป: Grid Calculator →")));
      }
    }).catch(err => { busy(btn, false); resultBox.replaceChildren(errorBox(err)); });
  }

  function applyPreset(name) {
    S.config = JSON.parse(JSON.stringify(S.meta.presets[name]));
    saveState();
    render();
  }

  page.append(
    el("h1", { class: "page-title" }, "EA Settings"),
    el("p", { class: "page-sub" }, "พารามิเตอร์ 27 ตัวของ SNIPER CashFlow V1.68 — เหมือนโปรแกรม Desktop 1:1"),
    disclaimerBanner(),
    el("div", { class: "card" },
      el("h2", null, "Preset ของผู้ขาย"),
      el("p", { class: "sub" }, "ค่ามาจากคู่มือ PDF + อินโฟกราฟิกของผู้ขาย — ชื่อ preset ตั้งตามเอกสารต้นทาง ไม่มีการระบุว่า \"ปลอดภัยที่สุด\""),
      el("div", { class: "chip-row" },
        Object.keys(S.meta.presets).map(name =>
          el("button", { class: "btn-ghost btn-small", onclick: () => applyPreset(name) }, name)))),
    el("div", { class: "card" },
      el("h2", null, "ทุน (Capital) และสัญลักษณ์"),
      el("div", { class: "form-grid" },
        el("div", { class: "field" }, el("label", null, "Capital (USD)"),
          el("input", { type: "number", step: "any", min: "0", id: "f_capital", value: String(S.capital) })),
        el("div", { class: "field" }, el("label", null, "Symbol"),
          profileSel)),
      advProfile, advAccount),
    ...basicCards, advancedCard,
    el("div", { class: "card" },
      el("h2", null, "ตรวจสอบค่า (Validate)"),
      el("p", { class: "sub" }, "ตรวจกับข้อจำกัดโบรกเกอร์ (lot min/max/step), leverage และกฎความสอดคล้องของพารามิเตอร์ — ใช้ logic validation ชุดเดียวกับ Desktop"),
      el("div", { class: "chip-row" },
        el("button", { class: "btn-primary", onclick: doValidate }, "บันทึกและตรวจสอบ"),
        el("button", { class: "btn-ghost", onclick: () => {
          localStorage.removeItem(LS_KEY);
          S.config = S.meta.defaults; S.symbol_profile = S.meta.profiles[0];
          S.account = S.meta.account_default; S.thresholds = S.meta.risk_thresholds_default;
          S.capital = 500; render();
        } }, "รีเซ็ตเป็นค่าเริ่มต้น")),
      resultBox));
}

/* ---------- Grid Calculator ---------- */
function pageGrid(page) {
  const resultBox = el("div");
  const LEVELS = ["5", "10", "11", "20", "30", "50", "100"];

  function selectWithId(id, options, value) {
    const s = el("select", { id }, options);
    s.value = value;
    return s;
  }

  function doCalc(ev) {
    const btn = ev.target;
    // quick params update shared config
    const gs = parseFloat($("#q_GridStepUSD").value);
    const bl = parseFloat($("#q_BaseLot").value);
    const lm = parseFloat($("#q_LotMultiplier").value);
    const problems = [];
    if (isNaN(gs) || gs <= 0) problems.push("GridStepUSD ต้องเป็นตัวเลข > 0");
    if (isNaN(bl) || bl <= 0) problems.push("BaseLot ต้องเป็นตัวเลข > 0");
    if (isNaN(lm) || lm <= 0) problems.push("LotMultiplier ต้องเป็นตัวเลข > 0");
    const cap = parseFloat($("#g_capital").value);
    if (!isNaN(cap) && cap > 0) S.capital = cap; else problems.push("Capital ต้องเป็นตัวเลข > 0");
    resultBox.replaceChildren();
    if (problems.length) { resultBox.append(errorBox({ message: "แก้ค่าก่อนคำนวณ", details: problems })); return; }
    S.config.GridStepUSD = gs; S.config.BaseLot = bl; S.config.LotMultiplier = lm;
    saveState();

    const side = $("#g_side").value;
    const custom = parseInt($("#g_custom").value, 10);
    const levels = (!isNaN(custom) && custom >= 1 && custom <= 500) ? custom
      : parseInt($("#g_levels").value, 10);
    const spRaw = $("#g_start").value.trim();
    const start_price = spRaw ? parseFloat(spRaw) : null;
    const basketDepth = parseInt($("#g_basket_depth").value, 10);

    const body = calcBody({ side, levels, capital: S.capital });
    if (start_price) body.start_price = start_price;
    const basketBody = calcBody({ side, levels: basketDepth });
    if (start_price) basketBody.start_price = start_price;

    busy(btn, true);
    Promise.all([
      apiPost("/api/grid/calculate", body),
      apiPost("/api/basket/simulate", basketBody),
    ]).then(([grid, basket]) => {
      busy(btn, false);
      renderGrid(grid, basket, levels, basketDepth);
    }).catch(err => { busy(btn, false); resultBox.replaceChildren(errorBox(err)); });
  }

  function gridRowCard(r) {
    return el("div", { class: "lvl-card" },
      el("div", { class: "lvl-head" },
        el("b", null, "ชั้น " + r.level),
        el("span", { class: "na" }, "lot " + fmtLot(r.lot))),
      el("div", { class: "kv-grid" },
        kv("Entry", fmt(r.entry_price, 2)),
        kv("ระยะ ($)", fmt(r.distance_from_start, 2)),
        kv("Lot สะสม", fmtLot(r.cumulative_lot)),
        kv("Exposure ($)", fmtMoney(r.exposure)),
        kv("Floating P/L ($)", fmtMoney(r.floating_pl_at_open), r.floating_pl_at_open < 0),
        kv("Margin ($)", fmtMoney(r.margin)),
        kv("Avg Entry", r.avg_entry === null ? "N/A" : fmt(r.avg_entry, 2))));
  }

  function renderGrid(data, basket, levels, basketDepth) {
    const g = data.grid;
    const rows = g.rows.map(r => el("tr", null,
      el("td", null, r.level),
      numCell(r.distance_from_start, 2),
      numCell(r.entry_price, 2),
      numCell(r.lot, 2),
      numCell(r.cumulative_lot, 2),
      numCell(r.exposure, 2),
      numCell(r.floating_pl_at_open, 2),
      numCell(r.margin, 2),
      numCell(r.avg_entry, 2)));
    const b = basket.basket;
    S.ui.rerender = () => renderGrid(data, basket, levels, basketDepth);
    resultBox.replaceChildren(
      el("div", { class: "card" },
        el("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap" },
          el("h2", null, "ผลลัพธ์ — Grid " + g.side + " · " + g.rows.length + " ชั้น · start " + fmt(g.start_price, 2)),
          viewToggle()),
        validationList(data.validation),
        el("div", { class: "metric-grid" },
          metric("Total Lot", fmt(g.total_lot, 2)),
          metric("Total Exposure", "$" + fmtMoney(g.total_exposure)),
          metric("Total Margin", "$" + fmtMoney(g.total_margin)),
          metric("Floating P/L ชั้นสุดท้าย",
                 (g.final_floating_pl < 0 ? "-" : "") + "$" + fmtMoney(Math.abs(g.final_floating_pl)),
                 "(ที่จุด trigger ล่าสุด)"),
          metric("Avg Entry", fmt(g.avg_entry, 2))),
        useCards()
          ? el("div", { class: "cards" }, g.rows.map(gridRowCard))
          : dataTable(
              ["Level", "ระยะราคา ($)", "Entry Price", "Lot", "Lot สะสม", "Exposure ($)", "Floating P/L ($)", "Margin ($)", "Avg Entry"],
              rows),
        assumptionsBlock(data)),
      el("div", { class: "card" },
        el("h2", null, "Basket / Partial Close Simulation (ความลึก " + b.levels + " ชั้น)"),
        el("div", { class: "metric-grid" },
          metric("Total Lots", fmtLot(b.total_lots)),
          metric("Avg Entry", fmt(b.avg_entry, 2)),
          metric("Current Price", fmt(b.current_price, 2)),
          metric("Basket P/L ปัจจุบัน", (b.current_basket_pl < 0 ? "-" : "") + "$" + fmtMoney(Math.abs(b.current_basket_pl)))),
        el("div", { class: "metric-grid" },
          metric("Partial Trigger", b.partial_trigger === null ? "N/A" : "$" + fmtMoney(b.partial_trigger), b.partial_pending ? "(ยังไม่ทำงาน)" : "(ทำแล้ว/OnlyOnce)"),
          metric("Partial Volume", fmtLot(b.partial_close_volume)),
          metric("Realized P/L", "$" + fmtMoney(b.partial_realized_pl)),
          metric("Lots คงเหลือ", fmtLot(b.partial_remaining_lots))),
        el("div", { class: "metric-grid" },
          metric("Basket Target", b.basket_target === null ? "N/A" : "$" + fmtMoney(b.basket_target)),
          metric("ราคาต้องเด้งกลับ → Partial", b.price_move_to_partial === null ? "N/A" : "$" + fmt(b.price_move_to_partial, 4)),
          metric("ราคาต้องเด้งกลับ → Target", b.price_move_to_target === null ? "N/A" : "$" + fmt(b.price_move_to_target, 4))),
        el("p", { class: "sub" }, b.remaining_position_note),
        assumptionsBlock(basket)),
      el("div", null,
        el("a", { class: "next-link", href: "#/worst-case" }, "ถัดไป: Worst Case Simulator →")));
  }

  page.append(
    el("h1", { class: "page-title" }, "Grid Calculator"),
    el("p", { class: "page-sub" }, "ตารางไม้ตามชั้น Grid — lot, lot สะสม, ระยะราคา, floating P/L ณ จุดเปิดไม้, มาร์จิ้น — คำนวณโดย Core ชุดเดียวกับ Desktop"),
    disclaimerBanner(),
    el("div", { class: "card" },
      el("div", { class: "form-grid" },
        el("div", { class: "field" }, el("label", null, "Side"),
          el("select", { id: "g_side" }, [el("option", { value: "BUY" }, "BUY"), el("option", { value: "SELL" }, "SELL")])),
        el("div", { class: "field" }, el("label", null, "Grid Levels"),
          selectWithId("g_levels", LEVELS.map(l => el("option", { value: l }, l)), "11")),
        el("div", { class: "field" }, el("label", null, "Custom Levels (1-500)"),
          el("input", { type: "number", id: "g_custom", placeholder: "เช่น 15" })),
        el("div", { class: "field" }, el("label", null, "Capital (USD)"),
          el("input", { type: "number", step: "any", id: "g_capital", value: String(S.capital) })),
        el("div", { class: "field" }, el("label", null, "GridStepUSD"),
          el("input", { type: "number", step: "any", id: "q_GridStepUSD", value: String(S.config.GridStepUSD) })),
        el("div", { class: "field" }, el("label", null, "BaseLot"),
          el("input", { type: "number", step: "any", id: "q_BaseLot", value: String(S.config.BaseLot) })),
        el("div", { class: "field" }, el("label", null, "LotMultiplier"),
          el("input", { type: "number", step: "any", id: "q_LotMultiplier", value: String(S.config.LotMultiplier) })),
        el("div", { class: "field" }, el("label", null, "Basket depth (Partial/Target)"),
          selectWithId("g_basket_depth",
            ["1", "3", "5", "10", "20"].map(l => el("option", { value: l }, l)), "5"))),
      el("details", { class: "advanced" },
        el("summary", null, "ตัวเลือกขั้นสูง"),
        el("div", { class: "form-grid" },
          el("div", { class: "field" }, el("label", null, "Start Price (ว่าง = ราคาอ้างอิงของ symbol)"),
            el("input", { type: "number", step: "any", id: "g_start", placeholder: String(S.symbol_profile.reference_price) })))),
      el("div", { style: "margin-top:12px" },
        el("button", { class: "btn-primary", onclick: doCalc }, "Calculate"))),
    resultBox);
}

/* ---------- Worst Case ---------- */
function pageWorstCase(page) {
  const resultBox = el("div");
  const SCEN = [["BUY_ADVERSE", "ราคาลง (BUY grid เสียเปรียบ)"],
                ["SELL_ADVERSE", "ราคาขึ้น (SELL grid เสียเปรียบ)"],
                ["BOTH_SIDES", "สองฝั่งพร้อมกัน"]];
  const movesBox = el("div", { class: "chip-row" });
  const customMove = el("input", { type: "number", step: "any", placeholder: "กำหนดเอง ($)", style: "width:130px;padding:5px 8px;border:1px solid #dcdce4;border-radius:7px" });

  function chip(move) {
    const on = S.ui.wcMoves.has(move);
    const c = el("button", { class: "toggle-chip" + (on ? " on" : "") },
      "$" + move);
    c.addEventListener("click", () => {
      if (S.ui.wcMoves.has(move)) S.ui.wcMoves.delete(move);
      else S.ui.wcMoves.add(move);
      c.classList.toggle("on");
    });
    return c;
  }
  function refreshChips() {
    const all = [...new Set([...S.meta.move_presets, ...S.ui.wcMoves])].sort((a, b) => a - b);
    movesBox.replaceChildren(...all.map(chip));
  }
  refreshChips();

  const scenChecks = SCEN.map(([id, label]) => {
    const cb = el("input", { type: "checkbox", checked: S.ui.wcScenarios.has(id), id: "wc_" + id });
    cb.addEventListener("change", () => {
      if (cb.checked) S.ui.wcScenarios.add(id); else S.ui.wcScenarios.delete(id);
    });
    return el("label", { style: "display:flex;gap:6px;align-items:center;font-size:13.5px" }, cb, label);
  });

  function doSim(ev) {
    const btn = ev.target;
    resultBox.replaceChildren();
    const cap = parseFloat($("#wc_capital").value);
    const problems = [];
    if (isNaN(cap) || cap <= 0) problems.push("Capital ต้องเป็นตัวเลข > 0");
    if (!S.ui.wcMoves.size) problems.push("เลือกระยะ movement อย่างน้อย 1 ค่า");
    if (!S.ui.wcScenarios.size) problems.push("เลือก scenario อย่างน้อย 1 แบบ");
    if (problems.length) { resultBox.append(errorBox({ message: "แก้ค่าก่อนคำนวณ", details: problems })); return; }
    S.capital = cap;
    saveState();
    const body = calcBody({
      capital: S.capital,
      moves: [...S.ui.wcMoves],
      scenarios: [...S.ui.wcScenarios],
    });
    const spRaw = $("#wc_start").value.trim();
    if (spRaw) body.start_price = parseFloat(spRaw);
    busy(btn, true, "กำลังจำลอง…");
    apiPost("/api/worst-case/simulate", body).then(data => {
      busy(btn, false);
      renderWorst(data);
    }).catch(err => { busy(btn, false); resultBox.replaceChildren(errorBox(err)); });
  }

  function wcRowCard(r) {
    return el("div", { class: "lvl-card" + (r.emergency_triggered ? " emerg" : "") },
      el("div", { class: "lvl-head" },
        el("b", null, r.scenario + " · เลื่อน $" + fmt(r.adverse_move, 0)),
        r.emergency_triggered
          ? el("span", { class: "badge sev-WARNING", title: r.emergency_note }, "⚠ Emergency")
          : el("span", { class: "na" }, "—")),
      el("div", { class: "kv-grid" },
        kv("Grid Levels", String(r.grid_levels)),
        kv("Total Lots", fmtLot(r.total_lots)),
        kv("Floating P/L ($)", fmtMoney(r.floating_pl), r.floating_pl < 0),
        kv("Margin ($)", fmtMoney(r.estimated_margin_used)),
        kv("Equity ($)", fmtMoney(r.equity)),
        kv("DD %", fmtPct(r.drawdown_pct)),
        kv("Margin Level %", r.margin_level_pct === null ? "N/A" : fmt(r.margin_level_pct, 2)),
        kv("เหลือทุน ($)", fmtMoney(r.remaining_capital)),
        kv("End Price", fmt(r.end_price, 2))));
  }

  function renderWorst(data) {
    const rows = data.results.map((r, i) => el("tr", null,
      el("td", null, r.scenario),
      numCell(r.adverse_move, 0),
      numCell(r.end_price, 2),
      el("td", null, r.grid_levels),
      numCell(r.total_lots, 2),
      numCell(r.floating_pl, 2),
      numCell(r.estimated_margin_used, 2),
      numCell(r.equity, 2),
      numCell(r.drawdown_pct, 2),
      numCell(r.margin_level_pct, 2),
      numCell(r.remaining_capital, 2),
      el("td", null, r.emergency_triggered
        ? el("span", { class: "badge sev-WARNING", title: r.emergency_note }, "⚠ Emergency")
        : el("span", { class: "na" }, "—"))));
    const notes = [...new Set(data.results.map(r => r.emergency_note))];
    S.ui.rerender = () => renderWorst(data);
    resultBox.replaceChildren(
      el("div", { class: "card" },
        el("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap" },
          el("h2", null, "ผลลัพธ์ (" + data.results.length + " สถานการณ์) — ทุน $" + fmtMoney(data.capital)),
          viewToggle()),
        validationList(data.validation),
        useCards()
          ? el("div", { class: "cards" }, data.results.map(wcRowCard))
          : dataTable(
              ["Scenario", "Movement ($)", "End Price", "Grid Levels", "Total Lots", "Floating P/L ($)", "Margin ($)", "Equity ($)", "DD %", "Margin Level %", "เหลือทุน ($)", "Emergency"],
              rows),
        el("h3", null, "หมายเหตุ Emergency"),
        el("ul", { class: "issue-list" }, notes.map(n => el("li", null, el("span", { class: "na" }, n)))),
        el("p", { class: "sub" }, "Margin Level % ต่ำ = ใกล้ถูก stop-out ตามกฎโบรกเกอร์ — ดูธงเตือนความเสี่ยงเต็มรูปแบบที่หน้า Risk Dashboard (threshold ปรับได้)"),
        assumptionsBlock(data)),
      el("div", null,
        el("a", { class: "next-link", href: "#/risk" }, "ถัดไป: Risk Dashboard →")));
  }

  page.append(
    el("h1", { class: "page-title" }, "Worst Case Simulator"),
    el("p", { class: "page-sub" }, "จำลองราคาวิ่งทางเดียวต่อกริด แล้วดูสถานะพอร์ต ณ จุดสุดท้าย — 3 สถานการณ์ต่อระยะ movement"),
    disclaimerBanner(),
    el("div", { class: "card" },
      el("div", { class: "form-grid" },
        el("div", { class: "field" }, el("label", null, "Capital (USD)"),
          el("input", { type: "number", step: "any", id: "wc_capital", value: String(S.capital) }))),
      el("h3", null, "Price movement (เลือกได้หลายค่า)"),
      movesBox,
      el("div", { style: "margin-top:8px" }, customMove,
        el("button", { class: "btn-ghost btn-small", style: "margin-left:6px", onclick: () => {
          const v = parseFloat(customMove.value);
          if (!isNaN(v) && v >= 0) { S.ui.wcMoves.add(v); refreshChips(); customMove.value = ""; }
        } }, "เพิ่มระยะ")),
      el("h3", null, "Scenarios"),
      el("div", { class: "chip-row" }, scenChecks),
      el("details", { class: "advanced" },
        el("summary", null, "ตัวเลือกขั้นสูง"),
        el("div", { class: "form-grid" },
          el("div", { class: "field" }, el("label", null, "Start Price (ว่าง = ราคาอ้างอิง)"),
            el("input", { type: "number", step: "any", id: "wc_start", placeholder: String(S.symbol_profile.reference_price) })))),
      el("div", { style: "margin-top:12px" },
        el("button", { class: "btn-primary", onclick: doSim }, "Simulate"))),
    resultBox);
}

/* ---------- Risk Dashboard ---------- */
function pageRisk(page) {
  const resultBox = el("div");
  const THR_FIELDS = [
    ["high_lot_growth_multiplier", "LotMultiplier ถือว่าโตเร็วเมื่อ >="],
    ["high_grid_depth_levels", "Grid depth ถือว่าลึกเมื่อ >= (ชั้น)"],
    ["high_dd_percent", "DD% ถือว่าสูงเมื่อ >= (%)"],
    ["low_capital_buffer_percent", "ทุนเหลือถือว่าน้อยเมื่อ <= (%)"],
    ["high_margin_usage_percent", "Margin ใช้ถือว่าสูงเมื่อ > (%)"],
    ["max_simulated_grid_levels", "จำนวนชั้นที่จำลองสูงสุด (1-500)"],
    ["reference_adverse_move_usd", "ระยะ movement อ้างอิง ($)"],
  ];

  function doCalc(ev) {
    const btn = ev.target;
    resultBox.replaceChildren();
    const problems = [];
    const cap = parseFloat($("#r_capital").value);
    if (isNaN(cap) || cap <= 0) problems.push("Capital ต้องเป็นตัวเลข > 0");
    const thresholds = {};
    for (const [k] of THR_FIELDS) {
      const v = parseFloat($("#th_" + k).value);
      if (isNaN(v)) problems.push("Threshold '" + k + "' ต้องเป็นตัวเลข");
      else thresholds[k] = v;
    }
    if (problems.length) { resultBox.append(errorBox({ message: "แก้ค่าก่อนคำนวณ", details: problems })); return; }
    thresholds.max_simulated_grid_levels = Math.round(thresholds.max_simulated_grid_levels);
    thresholds.high_grid_depth_levels = Math.round(thresholds.high_grid_depth_levels);
    S.capital = cap;
    S.thresholds = Object.assign({}, S.thresholds, thresholds);
    saveState();
    busy(btn, true);
    apiPost("/api/risk/calculate", calcBody({
      capital: S.capital,
      thresholds: S.thresholds,
      side: $("#r_side").value,
    })).then(data => {
      busy(btn, false);
      renderRisk(data);
    }).catch(err => { busy(btn, false); resultBox.replaceChildren(errorBox(err)); });
  }

  function renderRisk(data) {
    const s = data.summary;
    resultBox.replaceChildren(
      el("div", { class: "card" },
        el("h2", null, "Risk Summary — ทุน $" + fmtMoney(s.capital)),
        validationList(data.validation),
        el("div", { class: "metric-grid" },
          metric("Capital", "$" + fmtMoney(s.capital)),
          metric("Equity ที่เหลือ", "$" + fmtMoney(s.remaining_equity)),
          metric("Floating P/L (สถานการณ์อ้างอิง)",
                 (s.estimated_worst_floating_loss < 0 ? "-" : "") + "$" +
                 fmtMoney(Math.abs(s.estimated_worst_floating_loss))),
          metric("DD ประมาณการ", fmtPct(s.estimated_dd_percent) + "%"),
          metric("Margin ที่ใช้", "$" + fmtMoney(s.margin_used)),
          metric("Margin Usage", fmtPct(s.margin_usage_percent) + "%"),
          metric("Total Lots", fmtLot(s.total_lots)),
          metric("Exposure", "$" + fmtMoney(s.estimated_exposure)),
          metric("Grid ที่จำลอง", String(s.max_simulated_grid) + " ชั้น"),
          metric("Basket Target", s.basket_target === null ? "N/A (ปิด)" : "$" + fmtMoney(s.basket_target))),
        el("h3", null, "Risk Flags (" + s.flags.length + ")"),
        el("ul", { class: "flags-list" },
          s.flags.map(f => el("li", { class: f.severity === "info" ? "sev-info" : "" },
            el("b", null, f.flag), " — ", f.detail))),
        el("p", { class: "sub" }, "ธงเตือนทั้งหมดเทียบกับ threshold ที่คุณตั้ง — โปรแกรมไม่ให้คะแนนและไม่จัดอันดับความปลอดภัย"),
        assumptionsBlock(data)),
      el("div", null,
        el("a", { class: "next-link", href: "#/reports" }, "ถัดไป: ส่งออกรายงาน →")));
  }

  page.append(
    el("h1", { class: "page-title" }, "Risk Dashboard"),
    el("p", { class: "page-sub" }, "สรุปความเสี่ยงจากสถานการณ์อ้างอิง (movement + grid ตาม threshold) พร้อมธงเตือน — threshold ปรับได้ทั้งหมด"),
    disclaimerBanner(),
    el("div", { class: "card" },
      el("div", { class: "form-grid" },
        el("div", { class: "field" }, el("label", null, "Capital (USD)"),
          el("input", { type: "number", step: "any", id: "r_capital", value: String(S.capital) })),
        el("div", { class: "field" }, el("label", null, "Side ที่ใช้สร้างตาราง grid"),
          el("select", { id: "r_side" }, [el("option", { value: "BUY" }, "BUY"), el("option", { value: "SELL" }, "SELL")]))),
      el("h3", null, "Thresholds (แก้ได้)"),
      el("div", { class: "form-grid" },
        THR_FIELDS.map(([k, label]) => el("div", { class: "field" },
          el("label", null, label),
          el("input", { type: "number", step: "any", id: "th_" + k, value: String(S.thresholds[k]) })))),
      el("div", { style: "margin-top:12px", class: "chip-row" },
        el("button", { class: "btn-primary", onclick: doCalc }, "Calculate"),
        el("button", { class: "btn-ghost", onclick: () => {
          S.thresholds = S.meta.risk_thresholds_default; saveState(); render();
        } }, "ใช้ threshold ค่าเริ่มต้น")),
      resultBox));
}

/* ---------- Set Builder ---------- */
function pageSetBuilder(page) {
  const resultBox = el("div");
  const FIELDS = [
    ["grid_step", "GridStepUSD รายการค่า *", "5.0, 8.0"],
    ["multiplier", "LotMultiplier รายการค่า *", "1.08, 1.10, 1.20"],
    ["base_lot", "BaseLot รายการค่า *", "0.1"],
    ["basket_target", "BasketCloseAllUSD (ว่าง = ค่าจาก config)", ""],
    ["max_grid", "MaxGrid ชั้น (ว่าง = 11)", ""],
    ["capital", "Capital (ตัวเดียวหรือหลายค่า)", ""],
  ];
  const FILTERS = [
    ["max_dd_percent", "DD <= (%)"],
    ["max_margin_usage_percent", "Margin usage <= (%)"],
    ["max_grid", "Grid levels <= (ชั้น)"],
    ["max_lot", "Single lot <= "],
  ];

  function doGen(ev) {
    const btn = ev.target;
    resultBox.replaceChildren();
    const values = {};
    const problems = [];
    for (const [k, , ] of FIELDS) {
      const input = $("#sb_" + k);
      const raw = input.value.trim();
      if (k === "grid_step" || k === "multiplier" || k === "base_lot") {
        const nums = parseNumList(raw);
        if (!nums.length || nums.some(isNaN)) { problems.push("รายการค่าของ " + k + " ต้องเป็นตัวเลข ≥ 1 ค่า"); continue; }
        values[k] = nums;
      } else if (raw) {
        const nums = parseNumList(raw);
        if (nums.some(isNaN)) problems.push("รายการค่าของ " + k + " ต้องเป็นตัวเลข");
        else values[k] = nums;
      }
    }
    const filters = {};
    for (const [k] of FILTERS) {
      const raw = $("#f_" + k).value.trim();
      if (raw) {
        const v = parseFloat(raw);
        if (isNaN(v)) problems.push("Filter " + k + " ต้องเป็นตัวเลข");
        else filters[k] = v;
      }
    }
    if (problems.length) { resultBox.append(errorBox({ message: "แก้ค่าก่อนสร้างชุด", details: problems })); return; }

    const body = calcBody({ values });
    if (!values.capital) body.capital = S.capital;
    if (Object.keys(filters).length) body.filters = filters;

    busy(btn, true, "กำลังสร้างชุด…");
    apiPost("/api/set-builder/generate", body).then(data => {
      busy(btn, false);
      renderSets(data);
    }).catch(err => { busy(btn, false); resultBox.replaceChildren(errorBox(err)); });
  }

  function setCard(r, i) {
    const m = r.metrics;
    const warns = m.warnings || [];
    return el("details", { class: "lvl-card set-card" },
      el("summary", { class: "lvl-head" },
        el("span", null,
          el("b", null, "#" + (i + 1) + " "),
          "step " + fmt(r.grid_step, 2) + " · lot " + fmt(r.base_lot, 2) +
          " · mult " + fmt(r.multiplier, 2)),
        el("span", { class: "badge pass-" + r.passed }, r.passed ? "ผ่าน" : "ไม่ผ่าน")),
      el("div", { class: "kv-grid" },
        kv("Basket $", fmt(r.basket_target, 2)),
        kv("MaxGrid", String(r.max_grid)),
        kv("Capital", "$" + fmt(r.capital, 0)),
        kv("Total Lots", fmtLot(m.total_lots)),
        kv("Max Lot", fmtLot(m.max_single_lot)),
        kv("DD %", fmtPct(m.estimated_dd_percent)),
        kv("Worst P/L ($)", fmtMoney(m.estimated_worst_floating_loss), m.estimated_worst_floating_loss < 0),
        kv("Margin ($)", fmtMoney(m.estimated_margin)),
        kv("Margin %", fmtPct(m.margin_usage_percent)),
        kv("Capacity", String(m.grid_capacity_levels)),
        kv("เด้งกลับ→Target", m.price_move_to_basket_target === null ? "N/A" : "$" + fmt(m.price_move_to_basket_target, 4))),
      warns.length
        ? el("div", { style: "margin-top:6px;font-size:12.5px" },
            el("b", null, "คำเตือน (" + warns.length + ")"),
            el("ul", { class: "issue-list", style: "margin-top:4px" },
              warns.map(w => el("li", null, el("span", { class: "na" }, w)))))
        : el("p", { class: "sub", style: "margin:4px 0 0" }, "ไม่มีคำเตือน"),
      r.filter_reasons.length
        ? el("p", { class: "sub", style: "margin:4px 0 0" }, "ไม่ผ่าน filter: " + r.filter_reasons.join("; "))
        : null);
  }

  function renderSets(data) {
    const rows = [];
    data.combinations.forEach((r, i) => {
      const main = el("tr", { class: "row-expand" },
        el("td", null, i + 1),
        numCell(r.grid_step, 2),
        numCell(r.base_lot, 2),
        numCell(r.multiplier, 2),
        numCell(r.basket_target, 2),
        el("td", null, r.max_grid),
        numCell(r.capital, 0),
        numCell(r.metrics.total_lots, 2),
        numCell(r.metrics.max_single_lot, 2),
        numCell(r.metrics.estimated_dd_percent, 2),
        numCell(r.metrics.estimated_worst_floating_loss, 2),
        numCell(r.metrics.estimated_margin, 2),
        numCell(r.metrics.margin_usage_percent, 2),
        el("td", null, r.metrics.grid_capacity_levels),
        el("td", null, el("span", { class: "badge pass-" + r.passed }, r.passed ? "ผ่าน" : "ไม่ผ่าน")),
        el("td", { class: "na" }, r.filter_reasons.join("; ") || "—"));
      const warns = r.metrics.warnings || [];
      const detail = el("tr", { style: "display:none" },
        el("td", { colspan: "16" },
          el("div", { style: "padding:6px 4px" },
            el("b", null, "คำเตือนจาก validation จริง (" + warns.length + ")"),
            warns.length
              ? el("ul", { class: "issue-list" }, warns.map(w => el("li", null, w)))
              : el("p", { class: "sub" }, "ไม่มีคำเตือน"),
            el("p", { class: "sub" }, "ราคาต้องเด้งกลับถึง basket target: " +
              (r.metrics.price_move_to_basket_target === null ? "N/A" : "$" + fmt(r.metrics.price_move_to_basket_target, 4))))));
      main.addEventListener("click", () => {
        detail.style.display = detail.style.display === "none" ? "" : "none";
      });
      rows.push(main, detail);
    });
    S.ui.rerender = () => renderSets(data);
    resultBox.replaceChildren(
      el("div", { class: "card" },
        el("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap" },
          el("h2", null, "ผลลัพธ์ " + data.total + " ชุด — ผ่าน filter " + data.passed_count + " / ไม่ผ่าน " + data.filtered_count),
          viewToggle()),
        el("p", { class: "sub" }, data.note + (useCards() ? " แตะการ์ดเพื่อดูรายละเอียด/คำเตือน" : " คลิกแถวเพื่อดูคำเตือนของชุดนั้น")),
        useCards()
          ? el("div", { class: "cards" }, data.combinations.map((r, i) => setCard(r, i)))
          : dataTable(
              ["#", "GridStep", "BaseLot", "Mult", "Basket $", "MaxGrid", "Capital",
               "Total Lots", "Max Lot", "DD %", "Worst P/L ($)", "Margin ($)", "Margin %", "Capacity", "Filter", "เหตุผล"],
              rows),
        assumptionsBlock(data)));
  }

  page.append(
    el("h1", { class: "page-title" }, "Set Builder"),
    el("p", { class: "page-sub" }, "สร้างชุดค่าผสมจากรายการที่กำหนด แล้วคำนวณผลจริงของทุกชุด — ผลลัพธ์เรียงตามลำดับการสร้าง ไม่มีการจัดอันดับหรือให้คะแนน"),
    disclaimerBanner(),
    el("div", { class: "card" },
      el("div", { class: "form-grid" },
        FIELDS.map(([k, label, ph]) => el("div", { class: "field" },
          el("label", null, label),
          el("input", { type: "text", id: "sb_" + k, placeholder: ph || "", value: ph && k === "grid_step" ? ph : (k === "multiplier" ? ph : (k === "base_lot" ? ph : "")) })))),
      el("h3", null, "Filter (ไม่ระบุ = ไม่กรอง)"),
      el("div", { class: "form-grid" },
        FILTERS.map(([k, label]) => el("div", { class: "field" },
          el("label", null, label),
          el("input", { type: "number", step: "any", id: "f_" + k })))),
      el("div", { style: "margin-top:12px" },
        el("button", { class: "btn-primary", onclick: doGen }, "Generate"))),
    resultBox);
}

/* ---------- Backtest Analyzer ---------- */
function pageBacktest(page) {
  const resultBox = el("div");

  function doUpload(ev) {
    const btn = ev.target;
    const input = $("#bt_file");
    resultBox.replaceChildren();
    if (!input.files || !input.files.length) {
      resultBox.append(errorBox({ message: "เลือกไฟล์ก่อน (CSV / HTML / TXT)" }));
      return;
    }
    const file = input.files[0];
    const name = file.name.toLowerCase();
    if (![".csv", ".html", ".htm", ".txt"].some(ext => name.endsWith(ext))) {
      resultBox.append(errorBox({ message: "ชนิดไฟล์ไม่รองรับ — รับเฉพาะ .csv / .html / .htm / .txt" }));
      return;
    }
    const fd = new FormData();
    fd.append("file", file, file.name);
    busy(btn, true, "กำลังอัปโหลดและวิเคราะห์…");
    apiUpload("/api/backtest/analyze", fd).then(data => {
      busy(btn, false);
      S.backtest = data;
      renderBacktest(data, file.name);
    }).catch(err => { busy(btn, false); resultBox.replaceChildren(errorBox(err)); });
  }

  function renderBacktest(data, filename) {
    const s = data.summary, a = data.analysis;
    const sumCards = el("div", { class: "metric-grid" },
      metric("Net Profit", s.net_profit === null ? "N/A" : "$" + fmtMoney(s.net_profit)),
      metric("Profit Factor", s.profit_factor === null ? "N/A" : fmt(s.profit_factor, 4)),
      metric("Max DD", s.max_drawdown === null ? "N/A" : "$" + fmtMoney(s.max_drawdown),
             s.max_drawdown_percent === null ? "" : "(" + fmt(s.max_drawdown_percent, 2) + "%)"),
      metric("Trades", s.trades === null ? "N/A" : String(s.trades)),
      metric("Initial Deposit", s.initial_deposit === null ? "N/A" : "$" + fmtMoney(s.initial_deposit)),
      metric("Expected Payoff", s.expected_payoff === null ? "N/A" : "$" + fmt(s.expected_payoff, 4)),
      metric("Gross Profit", s.gross_profit === null ? "N/A" : "$" + fmtMoney(s.gross_profit)),
      metric("Gross Loss", s.gross_loss === null ? "N/A" : "$" + fmtMoney(s.gross_loss)),
      metric("Win / Loss", (s.winning_trades === null ? "N/A" : s.winning_trades) + " / " +
                           (s.losing_trades === null ? "N/A" : s.losing_trades)));
    const anCards = el("div", { class: "metric-grid" },
      metric("Max Grid Depth (รวม)", a.max_grid_depth_total === null ? "N/A" : String(a.max_grid_depth_total)),
      metric("Max Grid Depth BUY", a.max_grid_depth_buy === null ? "N/A" : String(a.max_grid_depth_buy)),
      metric("Max Grid Depth SELL", a.max_grid_depth_sell === null ? "N/A" : String(a.max_grid_depth_sell)),
      metric("Max Lot", a.max_lot === null ? "N/A" : fmtLot(a.max_lot)),
      metric("Avg Lot", a.avg_lot === null ? "N/A" : fmtLot(a.avg_lot)),
      metric("Total Volume", a.total_volume === null ? "N/A" : fmtLot(a.total_volume)),
      metric("Worst Losing Streak",
        a.worst_losing_streak_deals === null ? "N/A" : a.worst_losing_streak_deals + " ไม้",
        a.worst_losing_streak_amount === null ? "" : "(-$" + fmt(Math.abs(a.worst_losing_streak_amount), 2) + ")"));

    const dd = a.max_drawdown_episode;
    const ddBox = dd ? el("div", { class: "card" },
      el("h2", null, "Worst Loss Period (drawdown ลึกสุด)"),
      el("div", { class: "metric-grid" },
        metric("Peak", "$" + fmtMoney(dd.peak_balance), dd.peak_time),
        metric("Trough", "$" + fmtMoney(dd.trough_balance), dd.trough_time),
        metric("Depth", "$" + fmtMoney(dd.depth), "(" + fmt(dd.depth_percent, 2) + "%)"),
        metric("Recovery", dd.recovery_time || "ไม่ฟื้นในรายงาน"),
        metric("ช่วงเวลา", dd.duration_label))) : null;

    resultBox.replaceChildren(
      el("div", { class: "card" },
        el("h2", null, "สรุป Backtest — " + filename + " (" + s.source_format.toUpperCase() + ")"),
        el("p", { class: "sub" }, "ข้อมูลที่ไม่มีในไฟล์แสดง N/A — โปรแกรมไม่เดาค่า · Deals ที่อ่านได้: " + (s.deals ? s.deals.length : 0)),
        sumCards,
        el("h3", null, "Equity / Balance Curve"),
        curveSvg(a.balance_curve.length ? a.balance_curve : s.balance_curve)),
      el("div", { class: "card" },
        el("h2", null, "การวิเคราะห์เชิงกริด"),
        a.notes.length ? el("ul", { class: "issue-list" }, a.notes.map(n => el("li", null, el("span", { class: "na" }, n)))) : null,
        anCards),
      ddBox,
      el("div", { class: "card" },
        el("h2", null, "หมายเหตุจาก parser"),
        s.notes && s.notes.length
          ? el("ul", { class: "issue-list" }, s.notes.map(n => el("li", null, el("span", { class: "na" }, n))))
          : el("p", { class: "sub" }, "ไม่มี")),
      el("div", null,
        el("a", { class: "next-link", href: "#/reports" }, "แนบผลนี้ไปกับรายงานได้ที่หน้ารายงาน →")));
  }

  page.append(
    el("h1", { class: "page-title" }, "Backtest Analyzer"),
    el("p", { class: "page-sub" }, "อัปโหลดผล Strategy Tester ของ MT5 — CSV (deals export), HTML (report), TXT — ใช้ parser ชุดเดียวกับ Desktop"),
    el("div", { class: "card" },
      el("h2", null, "อัปโหลดไฟล์"),
      el("p", { class: "sub" }, "รับเฉพาะ .csv / .html / .htm / .txt ขนาดไม่เกิน 8MB — ไฟล์ถูกอ่านเป็นข้อความเท่านั้น ไม่มีการประมวลผลโค้ดใด ๆ"),
      el("div", { class: "chip-row" },
        el("input", { type: "file", id: "bt_file", accept: ".csv,.html,.htm,.txt", style: "flex:1;min-width:220px" }),
        el("button", { class: "btn-primary", onclick: doUpload }, "อัปโหลดและวิเคราะห์"))),
    resultBox);
}

function curveSvg(values) {
  if (!values || values.length < 2) {
    return el("p", { class: "sub" }, "N/A — ไฟล์ไม่มีข้อมูล balance curve");
  }
  const NS = "http://www.w3.org/2000/svg";
  const W = 640, H = 210, padL = 52, padR = 10, padT = 12, padB = 22;
  let min = Math.min(...values), max = Math.max(...values);
  if (max === min) max = min + 1;
  const x = i => padL + (i * (W - padL - padR)) / (values.length - 1);
  const y = v => padT + (1 - (v - min) / (max - min)) * (H - padT - padB);
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  svg.setAttribute("class", "svg-curve");
  const mk = (tag, attrs) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    return n;
  };
  svg.append(mk("rect", { x: 0, y: 0, width: W, height: H, fill: "#fafafc" }));
  svg.append(mk("line", { x1: padL, y1: H - padB, x2: W - padR, y2: H - padB, stroke: "#c9c9d4" }));
  const pts = values.map((v, i) => x(i).toFixed(1) + "," + y(v).toFixed(1)).join(" ");
  svg.append(mk("polyline", { points: pts, fill: "none", stroke: "#16213e", "stroke-width": 1.6 }));
  [max, min].forEach((v, idx) => {
    const t = document.createElementNS(NS, "text");
    t.setAttribute("x", 4); t.setAttribute("y", idx === 0 ? padT + 4 : H - padB);
    t.setAttribute("font-size", 10); t.setAttribute("fill", "#6a6f7d");
    t.textContent = fmt(v, 0);
    svg.append(t);
  });
  const n = document.createElementNS(NS, "text");
  n.setAttribute("x", W - padR); n.setAttribute("y", H - 6);
  n.setAttribute("font-size", 10); n.setAttribute("fill", "#6a6f7d");
  n.setAttribute("text-anchor", "end");
  n.textContent = values.length + " จุด (balance หลังแต่ละ deal)";
  svg.append(n);
  return svg;
}

/* ---------- Reports ---------- */
function pageReports(page) {
  const resultBox = el("div");
  const fmtSel = el("select", { id: "rp_format" },
    el("option", { value: "json" }, "JSON"),
    el("option", { value: "csv" }, "CSV"),
    el("option", { value: "html" }, "HTML (พิมพ์เป็น PDF ได้จาก browser)"));

  function doReport(ev) {
    const btn = ev.target;
    resultBox.replaceChildren();
    const problems = [];
    const cap = parseFloat($("#rp_capital").value);
    if (isNaN(cap) || cap <= 0) problems.push("Capital ต้องเป็นตัวเลข > 0");
    const body = calcBody({ capital: cap, format: fmtSel.value });
    if ($("#rp_grid").checked) {
      body.include_grid = true;
      const lv = parseInt($("#rp_levels").value, 10);
      if (isNaN(lv) || lv < 1 || lv > 500) problems.push("Grid levels ต้อง 1-500");
      else { body.levels = lv; body.side = $("#rp_side").value; }
    }
    if ($("#rp_worst").checked) {
      body.include_worst_case = true;
      const moves = parseNumList($("#rp_moves").value);
      if (!moves.length || moves.some(isNaN)) problems.push("Moves ต้องเป็นตัวเลข ≥ 1 ค่า");
      else body.moves = moves;
    }
    if ($("#rp_risk").checked) body.include_risk = true;
    if ($("#rp_basket").checked) {
      body.include_basket = true;
      body.basket_side = $("#rp_basket_side").value;
      const bl = parseInt($("#rp_basket_levels").value, 10);
      if (isNaN(bl) || bl < 1 || bl > 500) problems.push("Basket levels ต้อง 1-500");
      else body.basket_levels = bl;
    }
    if ($("#rp_bt").checked) {
      if (!S.backtest) problems.push("ยังไม่มีผล backtest — ไปอัปโหลดที่หน้า Backtest ก่อน หรือไม่ติ๊กแนบผล backtest");
      else body.backtest_summary = S.backtest.summary;
    }
    if (problems.length) { resultBox.append(errorBox({ message: "แก้ค่าก่อนสร้างรายงาน", details: problems })); return; }
    S.capital = cap;
    saveState();
    busy(btn, true, "กำลังสร้างรายงาน…");
    fetch("/api/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(async res => {
      if (!res.ok) {
        let data = null;
        try { data = await res.json(); } catch (e) {}
        throw apiError(res.status, data || { error: { message: "HTTP " + res.status } });
      }
      return res.blob().then(blob => ({ blob, ctype: res.headers.get("Content-Type") || "" }));
    }).then(({ blob }) => {
      busy(btn, false);
      const url = URL.createObjectURL(blob);
      const ext = fmtSel.value === "json" ? "json" : fmtSel.value;
      const dl = el("a", { class: "btn-gold btn-small", href: url, download: "sniper-report." + ext, style: "text-decoration:none;display:inline-block" }, "ดาวน์โหลด sniper-report." + ext);
      const open = fmtSel.value === "html"
        ? el("a", { class: "btn-ghost btn-small", href: url, target: "_blank", style: "text-decoration:none;display:inline-block;margin-left:8px" }, "เปิด HTML ในแท็บใหม่ (พิมพ์เป็น PDF ได้)")
        : null;
      resultBox.replaceChildren(
        el("div", { class: "card" },
          el("h2", null, "รายงานพร้อมแล้ว"),
          el("p", { class: "sub" }, "รายงานสร้างจาก Core ชุดเดียวกับ Desktop พร้อม assumption IDs และ disclaimer ครบ"),
          dl, open));
    }).catch(err => { busy(btn, false); resultBox.replaceChildren(errorBox(err)); });
  }

  page.append(
    el("h1", { class: "page-title" }, "รายงาน (Reports)"),
    el("p", { class: "page-sub" }, "ส่งออก JSON / CSV / HTML — ไฟล์ HTML เปิดใน browser ได้และพิมพ์เป็น PDF จากเมนูพิมพ์ของ browser ได้"),
    disclaimerBanner(),
    el("div", { class: "card" },
      el("div", { class: "form-grid" },
        el("div", { class: "field" }, el("label", null, "Capital (USD)"),
          el("input", { type: "number", step: "any", id: "rp_capital", value: String(S.capital) })),
        el("div", { class: "field" }, el("label", null, "รูปแบบไฟล์"), fmtSel),
        el("div", { class: "field" }, el("label", null, "Grid levels"),
          el("input", { type: "number", id: "rp_levels", value: "11" })),
        el("div", { class: "field" }, el("label", null, "Grid side"),
          el("select", { id: "rp_side" }, [el("option", { value: "BUY" }, "BUY"), el("option", { value: "SELL" }, "SELL")])),
        el("div", { class: "field" }, el("label", null, "Worst-case moves ($)"),
          el("input", { type: "text", id: "rp_moves", value: "10, 30, 50, 100" })),
        el("div", { class: "field" }, el("label", null, "Basket side"),
          el("select", { id: "rp_basket_side" }, [el("option", { value: "BUY" }, "BUY"), el("option", { value: "SELL" }, "SELL")])),
        el("div", { class: "field" }, el("label", null, "Basket levels"),
          el("input", { type: "number", id: "rp_basket_levels", value: "5" }))),
      el("h3", null, "ส่วนที่รวมในรายงาน"),
      el("div", { class: "chip-row" },
        el("label", { class: "toggle-chip" }, el("input", { type: "checkbox", id: "rp_grid", checked: true, style: "margin-right:6px" }), "Grid table"),
        el("label", { class: "toggle-chip" }, el("input", { type: "checkbox", id: "rp_worst", checked: true, style: "margin-right:6px" }), "Worst case"),
        el("label", { class: "toggle-chip" }, el("input", { type: "checkbox", id: "rp_risk", checked: true, style: "margin-right:6px" }), "Risk summary"),
        el("label", { class: "toggle-chip" }, el("input", { type: "checkbox", id: "rp_basket", checked: true, style: "margin-right:6px" }), "Basket/Partial"),
        el("label", { class: "toggle-chip" }, el("input", { type: "checkbox", id: "rp_bt", style: "margin-right:6px" }), "แนบผล Backtest ล่าสุด" + (S.backtest ? " (มีข้อมูล)" : " (ยังไม่มี)"))),
      el("div", { style: "margin-top:12px" },
        el("button", { class: "btn-primary", onclick: doReport }, "สร้างรายงาน"))),
    resultBox);
}

/* ---------- Assumptions ---------- */
function pageAssumptions(page) {
  const box = el("div", { class: "card" }, el("p", { class: "sub" }, "กำลังโหลด…"));
  page.append(
    el("h1", { class: "page-title" }, "Assumption Registry"),
    el("p", { class: "page-sub" }, "ทะเบียนสมมติฐานของโมเดลจำลอง — สถานะเดียวกับระบบ Desktop (อ่านจาก registry เดียวกัน)"),
    disclaimerBanner(),
    el("div", { class: "card" },
      el("h2", null, "ความหมายของสถานะ"),
      el("ul", { class: "issue-list" },
        [el("li", null, statusBadge("VERIFIED_FROM_DOCUMENTATION"), "ระบุไว้ในคู่มือ/เอกสารผู้ขาย"),
         el("li", null, statusBadge("OBSERVED_FROM_TESTING"), "ยืนยันจากการบันทึกพฤติกรรม MT5 จริง"),
         el("li", null, statusBadge("MODEL_ASSUMPTION"), "สมมติฐานของโมเดลจำลอง (ยังไม่ยืนยัน)"),
         el("li", null, statusBadge("UNKNOWN"), "ไม่มีข้อมูล — แสดงเป็น Unknown/N/A เสมอ")])),
    box);
  apiGet("/api/assumptions").then(data => {
    const counts = {};
    data.assumptions.forEach(a => { counts[a.status] = (counts[a.status] || 0) + 1; });
    box.replaceChildren(
      el("h2", null, "ทั้งหมด " + data.assumptions.length + " รายการ"),
      el("p", { class: "sub" },
        Object.entries(STATUS_LABELS).map(([st, lb]) => lb + " " + (counts[st] || 0)).join(" · ")),
      dataTable(
        ["ID", "สถานะ", "หัวข้อ", "รายละเอียด", "แหล่งอ้างอิง", "หลักฐาน"],
        data.assumptions.map(a => el("tr", null,
          el("td", null, a.assumption_id),
          el("td", null, statusBadge(a.status)),
          el("td", null, a.title),
          el("td", null, a.detail || "—"),
          el("td", null, a.source || "—"),
          el("td", null, a.evidence || "—")))));
  }).catch(err => box.replaceChildren(errorBox(err)));
}


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
      const b = ev.target; busy(b, true, "โหลด…");
      try { await fn(); } catch (e) { resultBox.replaceChildren(errorBox(e)); }
      busy(b, false);
    } }, label);
  }

  async function loadEvents() {
    const d = await apiGet("/api/observation-sessions/" + sessionId + "/events");
    resultBox.replaceChildren(el("div", { class: "card" },
      el("h2", null, "Observed Events (" + d.count + ")"),
      d.count === 0 ? el("p", { class: "sub" }, "ยังไม่มี events — import ก่อน") :
      dataTable(["Time", "Event", "Side", "Level", "Lot", "Price", "P/L", "Comm", "Swap"],
        d.events.map(e => el("tr", null,
          el("td", null, e.timestamp || "?"), el("td", null, e.event),
          el("td", null, e.side || "—"), el("td", null, e.grid_level === null ? "—" : e.grid_level),
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
      el("td", null, c.difference || "—"),
      el("td", { class: "na", title: (c.assumption_ids || []).join(", ") },
         (c.assumption_ids || []).length + " ids")));
    resultBox.replaceChildren(el("div", { class: "card" },
      el("h2", null, "Model Comparison"),
      el("div", { class: "metric-grid" },
        Object.entries(d.counts).map(([k, v]) => metric(k, String(v)))),
      dataTable(["Check", "Title", "Status", "Observed", "Model", "Diff", "Assumptions"], rows),
      el("p", { class: "sub" },
        "MATCH = สอดคล้องกับโมเดล์ (ไม่ใช่การพิสูจน์สูตร EA) · ไม่มี auto-correct")));
  }

  async function loadTimeline() {
    const d = await apiGet("/api/observation-sessions/" + sessionId + "/timeline");
    resultBox.replaceChildren(el("div", { class: "card" },
      el("h2", null, "Cycle Timeline (" + d.cycle_count + " cycles · complete " + d.complete + " · incomplete " + d.incomplete + ")"),
      d.cycle_count === 0 ? el("p", { class: "sub" }, "ยังไม่มี cycle") :
      d.timelines.map(t => el("details", { class: "lvl-card" },
        el("summary", { class: "lvl-head" },
          el("b", null, t.cycle_id + " · " + t.direction + " · " + t.grid_levels + " levels"),
          el("span", { class: "badge " + (t.status === "COMPLETE" ? "pass-true" : "sev-WARNING") },
            t.status + (t.missing.length ? " (ขาด: " + t.missing.join(", ") + ")" : ""))),
        dataTable(["#", "Time", "Event", "Pos", "Lots", "Float", "Equity"],
          t.rows.map(r => el("tr", null,
            el("td", null, r.seq), el("td", null, r.timestamp || "?"),
            el("td", null, r.event), el("td", null, r.position_count === null ? "—" : r.position_count),
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
      el("h2", null, "รายงานดาวน์โหลดแล้ว"),
      el("p", { class: "sub" }, "behavior-verification-report.json — ครบ 15 sections + evidence/assumption traceability")));
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
    busy(b, true, "สร้าง…");
    try {
      const d = await apiPost("/api/observation-sessions", body);
      sessionId = d.session.session_id;
      resultBox.replaceChildren(el("div", { class: "card" },
        el("h2", null, "Session สร้างแล้ว: " + sessionId),
        el("p", { class: "sub" }, "import ไฟล์ MT5 (CSV/Journal/Tester) ได้เลยด้านล่าง")));
    } catch (e) { resultBox.replaceChildren(errorBox(e)); }
    busy(b, false);
  }

  async function doImport(ev) {
    const b = ev.target; resultBox.replaceChildren();
    if (!sessionId) { resultBox.replaceChildren(errorBox({ message: "สร้าง session ก่อน" })); return; }
    const input = $("#ob_file");
    if (!input.files || !input.files.length) {
      resultBox.replaceChildren(errorBox({ message: "เลือกไฟล์ก่อน (.csv/.txt/.log/.html)" }));
      return;
    }
    const fd = new FormData();
    fd.append("file", input.files[0], input.files[0].name);
    fd.append("source_kind", $("#ob_kind").value);
    busy(b, true, "นำเข้า…");
    try {
      const d = await apiUpload("/api/observation-sessions/" + sessionId + "/import", fd);
      const r = d.import_result;
      resultBox.replaceChildren(el("div", { class: "card" },
        el("h2", null, "Import เสร็จ — " + r.rows_imported + "/" + r.rows_read + " แถว"),
        el("div", { class: "metric-grid" },
          metric("Read", String(r.rows_read)), metric("Imported", String(r.rows_imported)),
          metric("Rejected", String(r.rows_rejected)), metric("Events รวม", String(d.event_count))),
        r.unknown_columns.length ? el("p", { class: "sub" },
          "คอลัมน์ที่ไม่รู้จัก (ไม่นำเข้า): " + r.unknown_columns.join(", ")) : null,
        r.warnings.length ? el("ul", { class: "issue-list" },
          r.warnings.map(w => el("li", null, el("span", { class: "na" }, w)))) : null));
    } catch (e) { resultBox.replaceChildren(errorBox(e)); }
    busy(b, false);
  }

  page.append(
    el("h1", { class: "page-title" }, "MT5 Observation & Behavior Verification"),
    el("p", { class: "page-sub" },
      "นำเข้าข้อมูลจริงจาก MT5 → ตรวจพฤติกรรม EA เทียบ Simulation Model (OBSERVED vs MODEL vs UNKNOWN)"),
    disclaimerBanner(),
    el("div", { class: "card" },
      el("h2", null, "1. สร้าง Observation Session"),
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
        el("div", { class: "field" }, el("label", null, "Notes"), el("input", { id: "ob_notes", placeholder: "หมายเหตุ" }))),
      el("div", { style: "margin-top:10px" }, el("button", { class: "btn-primary", onclick: doCreate }, "สร้าง Session"))),
    el("div", { class: "card" },
      el("h2", null, "2. Import ไฟล์ MT5"),
      el("div", { class: "form-grid" },
        el("div", { class: "field" }, el("label", null, "ไฟล์ (.csv/.txt/.log/.html ≤ 8MB)"),
          el("input", { type: "file", id: "ob_file", accept: ".csv,.txt,.log,.htm,.html" })),
        el("div", { class: "field" }, el("label", null, "ชนิดข้อมูล"),
          el("select", { id: "ob_kind" },
            el("option", { value: "MT5_CSV" }, "Behavior CSV"),
            el("option", { value: "MT5_JOURNAL" }, "Journal/Log"),
            el("option", { value: "MT5_TESTER" }, "Tester Report")))),
      el("div", { style: "margin-top:10px" }, el("button", { class: "btn-primary", onclick: doImport }, "Import"))),
    el("div", { class: "card" },
      el("h2", null, "3. ตรวจ & รายงาน"),
      el("div", { class: "chip-row" },
        sectionBtn("Events", loadEvents),
        sectionBtn("Model Comparison", loadComparison),
        sectionBtn("Cycle Timeline", loadTimeline),
        sectionBtn("ดาวน์โหลดรายงาน JSON", downloadReport))),
    resultBox);
}

/* ======================= router + boot ======================= */
const ROUTES = {
  "/home": pageHome,
  "/settings": pageSettings,
  "/grid": pageGrid,
  "/worst-case": pageWorstCase,
  "/risk": pageRisk,
  "/set-builder": pageSetBuilder,
  "/backtest": pageBacktest,
  "/reports": pageReports,
  "/assumptions": pageAssumptions,
  "/observation": pageObservation,
};

async function init() {
  let meta = null;
  try {
    meta = await apiGet("/api/config");
  } catch (err) {
    $("#notice").hidden = false;
    $("#notice").textContent = "เชื่อมต่อ API ไม่สำเร็จ: " + err.message + " — ลองรีเฟรชอีกครั้ง";
    return;
  }
  S.meta = meta;
  const stored = loadState();
  S.config = (stored && stored.config) || meta.defaults;
  S.symbol_profile = (stored && stored.symbol_profile) || meta.profiles[0];
  S.account = (stored && stored.account) || meta.account_default;
  S.thresholds = (stored && stored.thresholds) || meta.risk_thresholds_default;
  S.capital = (stored && stored.capital) || 500;
  buildNav();
  window.addEventListener("hashchange", render);
  render();
}

init();
