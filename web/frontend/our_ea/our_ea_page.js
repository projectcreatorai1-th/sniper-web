/* OUR EA status page (Phase 6 §42).
   Self-contained read-only view over the immutable release_status.json
   exported at build time. NO backend endpoint is used (analyzer backend
   is read-only for Phase 6). Unknown never looks verified: each status
   has a distinct badge. */
function pageOurEa(page) {
  page.appendChild(el("h2", {}, "OUR EA — Release Candidate"));
  const box = el("div", { class: "card" });
  box.appendChild(el("p", {}, "โหลดสถานะ…"));
  page.appendChild(box);
  fetch("/static/our_ea/release_status.json")
    .then(r => { if (!r.ok) throw new Error("manifest missing"); return r.json(); })
    .then(st => { box.replaceChildren(); renderOurEaStatus(box, st); })
    .catch(() => {
      box.replaceChildren(
        el("p", { class: "muted" },
          "ยังไม่มี release_status.json — รัน tools/phase6_release.py ก่อน"));
    });
}

function ourEaBadge(status) {
  const colors = {
    VERIFIED: ["#e2f4e6", "#1c7c3c"],
    PARTIAL:  ["#fdf0d5", "#8a6d1a"],
    UNKNOWN:  ["#ececf1", "#565b69"],
    REJECTED: ["#fbe3e3", "#a33"],
    PASS:     ["#e2f4e6", "#1c7c3c"],
    "PASS_WITH_UNKNOWN": ["#e3ecfd", "#2a5db0"],
    FAIL:     ["#fbe3e3", "#a33"],
  }[status] || ["#ececf1", "#565b69"];
  const b = el("span", { class: "badge" }, status);
  b.style.background = colors[0];
  b.style.color = colors[1];
  return b;
}

function renderOurEaStatus(box, st) {
  const head = el("div", { class: "kv" });
  head.appendChild(el("div", {}, "Build: " + st.build_version));
  head.appendChild(el("div", {}, "Model: " + st.model_version));
  head.appendChild(el("div", {}, "Model hash: " + st.model_hash));
  head.appendChild(el("div", {}, "Generated: " + st.generated_at));
  head.appendChild(el("div", {},
    "LIVE: " + el("b", {}, st.live_lock.split("(")[0]).textContent));
  box.appendChild(head);

  // gates
  const g = el("h3", {}, "Gates (6.1–6.12)");
  box.appendChild(g);
  const gt = el("table", { class: "tbl" });
  gt.appendChild(row("Gate", "ชื่อ", "ผล"));
  st.gates.forEach(x => {
    const tr = el("tr", {});
    tr.appendChild(el("td", {}, x.gate));
    tr.appendChild(el("td", {}, x.name));
    const td = el("td", {});
    td.appendChild(ourEaBadge(x.result));
    tr.appendChild(td);
    gt.appendChild(tr);
  });
  box.appendChild(gt);

  // rules with honest status separation
  box.appendChild(el("h3", {}, "Rules (V1.68 evidence)"));
  const rt = el("table", { class: "tbl" });
  rt.appendChild(row("Rule", "ชื่อ", "สถานะ"));
  st.rules.forEach(r => {
    const tr = el("tr", {});
    tr.appendChild(el("td", {}, r.rule_id));
    tr.appendChild(el("td", {}, r.name));
    const td = el("td", {});
    td.appendChild(ourEaBadge(r.status));
    tr.appendChild(td);
    rt.appendChild(tr);
  });
  box.appendChild(rt);

  // replay
  box.appendChild(el("h3", {}, "Historical Replay"));
  const rp = st.replay;
  box.appendChild(el("p", {},
    `comparisons ${rp.total} · MATCH ${rp.MATCH} · MISMATCH ${rp.MISMATCH} · ` +
    `UNKNOWN ${rp.UNKNOWN} · NOT_COMPARABLE ${rp.NOT_COMPARABLE} · ` +
    `match ${rp.match_pct}%`));
  box.appendChild(el("p", { class: "muted" },
    "resume ≤2s: " + (st.resume.checks - st.resume.mismatches) + "/" +
    st.resume.checks));

  // paper
  box.appendChild(el("h3", {}, "Paper Run"));
  box.appendChild(el("p", {},
    `ticks ${st.paper.ticks} · cycles ${st.paper.cycles} · events ` +
    JSON.stringify(st.paper.events || {}).slice(0, 160)));

  box.appendChild(el("p", { class: "muted" },
    "ข้อมูลนี้เป็น immutable build-time export — OUR EA runtime ไม่เขียนกลับ Analyzer"));
}

function row(a, b, c) {
  const tr = el("tr", {});
  tr.appendChild(el("td", {}, String(a)));
  tr.appendChild(el("td", {}, String(b)));
  tr.appendChild(el("td", {}, String(c)));
  return tr;
}
