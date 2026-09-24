"""Desktop Evidence page (Phase 4) — reads the SAME core registries as Web.

No separate store; all actions call core logic directly.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from core.assumptions import default_registry
from core.environment import observed_test_environment
from core.evidence import default_evidence_registry
from core.external_evidence import (
    LINK_RELATIONS,
    QUALITY_INDIRECT,
    REL_CONTEXT_FOR,
    REL_SUPPORTS,
    TARGET_ASSUMPTION,
    TARGET_OBSERVATION,
    ExternalEvidenceStore,
    EvidenceLinkStore,
    indirect_support_gate,
)
from core.model_candidates import ModelCandidateStore
from core.observation import ObservationSessionStore
from desktop.theme import make_table, section_label


class EvidencePage(ttk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent)
        self.state = state
        self.ev_store = ExternalEvidenceStore()
        self.link_store = EvidenceLinkStore()
        self.cand_store = ModelCandidateStore(link_store=self.link_store)
        self.obs_store = ObservationSessionStore()
        self.registry = default_registry()

        ttk.Label(self, text="Evidence", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="External Evidence + Evidence Registry + Model Candidates — "
                             "reads the same core registries as the Web version",
                  style="Banner.TLabel").pack(fill="x", pady=(4, 8))

        # -- Myfxbook import ------------------------------------------------
        imp_lf = ttk.LabelFrame(self, text="Import Myfxbook URL", padding=6)
        imp_lf.pack(fill="x", pady=4)
        self.url_var = tk.StringVar()
        ttk.Entry(imp_lf, textvariable=self.url_var, width=60).pack(side="left",
                                                                    padx=(0, 6))
        ttk.Button(imp_lf, text="Import", command=self._import_myfxbook,
                   style="Accent.TButton").pack(side="left")

        # -- external evidence list --------------------------------------------
        section_label(self, "External Evidence")
        ext_frame, self.ext_tree = make_table(self, [
            ("id", "ID", 110, "w"),
            ("source", "Source", 90, "w"),
            ("url", "URL", 200, "w"),
            ("retrieved", "Retrieved", 130, "w"),
            ("status", "Status", 90, "w"),
            ("quality", "Quality", 80, "w"),
            ("snapshots", "Snaps", 50, "e"),
        ])
        ext_frame.pack(fill="both", expand=True, pady=4)
        self.ext_tree.bind("<Double-1>", lambda e: self._view_detail())

        # -- actions ------------------------------------------------------------
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="View Detail", command=self._view_detail).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Link to Assumption", command=self._link_assumption).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Link Observation (picker)", command=self._link_observation).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Confirm Link", command=self._confirm_link).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Unlink", command=self._unlink).pack(side="left", padx=2)

        # -- links list -----------------------------------------------------------
        section_label(self, "Evidence Links")
        link_frame, self.link_tree = make_table(self, [
            ("link", "Link", 60, "w"),
            ("evidence", "Evidence", 110, "w"),
            ("target", "Target", 180, "w"),
            ("relation", "Relation", 90, "w"),
            ("confirmed", "Confirmed by", 100, "w"),
        ])
        link_frame.pack(fill="both", expand=True, pady=4)

        # -- candidates -------------------------------------------------------------
        section_label(self, "Model Candidates")
        cand_frame, self.cand_tree = make_table(self, [
            ("id", "ID", 60, "w"),
            ("rule", "Rule Type", 100, "w"),
            ("desc", "Description", 220, "w"),
            ("status", "Status", 80, "w"),
            ("reviewer", "Reviewed by", 90, "w"),
        ])
        cand_frame.pack(fill="both", expand=True, pady=4)
        cand_btn = ttk.Frame(self)
        cand_btn.pack(fill="x")
        ttk.Button(cand_btn, text="Reject", command=self._reject_candidate).pack(side="left", padx=2)

        # -- conflicts ---------------------------------------------------------------
        self.conflict_lbl = ttk.Label(self, text="", style="Muted.TLabel",
                                      wraplength=800, justify="left")
        self.conflict_lbl.pack(anchor="w", pady=4)

        self._refresh()

    # ------------------------------------------------------------------
    def _refresh(self):
        self.ext_tree.delete(*self.ext_tree.get_children())
        for e in self.ev_store.all():
            snaps = len(self.ev_store.snapshots_for(e.evidence_id))
            self.ext_tree.insert("", "end", values=(
                e.evidence_id, e.source_type,
                (e.source_url or "")[:40], e.retrieved_at or "—",
                e.status, e.quality or "UNKNOWN", snaps))
        self.link_tree.delete(*self.link_tree.get_children())
        for l in self.link_store.all():
            self.link_tree.insert("", "end", values=(
                l.link_id, l.evidence_id,
                f"{l.target_type}:{l.target_id}", l.relation,
                l.confirmed_by or "unconfirmed"))
        self.cand_tree.delete(*self.cand_tree.get_children())
        for cd in self.cand_store.all():
            self.cand_tree.insert("", "end", values=(
                cd.candidate_id, cd.rule_type, cd.description[:50],
                cd.status, cd.reviewed_by or "—"))
        conflicts = self.link_store.conflicts()
        if conflicts:
            txt = f"CONFLICTS ({len(conflicts)}): " + "; ".join(
                f"{c.target_id}: supports={c.supports} contradicts={c.contradicts}"
                for c in conflicts)
        else:
            txt = "No conflicts."
        self.conflict_lbl.configure(text=txt)

    def _selected_evidence(self) -> str:
        sel = self.ext_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "เลือก evidence ก่อน")
            return ""
        return self.ext_tree.item(sel[0], "values")[0]

    def _import_myfxbook(self):
        from core.myfxbook import MyfxbookImporter
        url = self.url_var.get().strip()
        if not url:
            messagebox.showinfo("Import", "ใส่ Myfxbook URL ก่อน")
            return
        importer = MyfxbookImporter(self.ev_store)
        result = importer.import_url(url)
        if result["status"] != "IMPORTED":
            messagebox.showerror("Import failed",
                                 f"IMPORT_FAILED:\n{result.get('reason', '?')}")
        else:
            messagebox.showinfo("Imported",
                                f"Evidence: {result['evidence']['evidence_id']}\n"
                                f"Metrics: {len(result['evidence']['extracted_metrics'])}")
        self._refresh()

    def _view_detail(self):
        eid = self._selected_evidence()
        if not eid:
            return
        try:
            e = self.ev_store.get(eid)
        except KeyError:
            return
        snaps = self.ev_store.snapshots_for(eid)
        env = observed_test_environment()
        info = (f"ID: {e.evidence_id}\nSource: {e.source_type}\n"
                f"URL: {e.source_url}\nNormalized: {e.normalized_url}\n"
                f"Retrieved: {e.retrieved_at}\nPeriod: {e.period_start or '?'} → {e.period_end or '?'}\n"
                f"Broker: {e.broker or 'UNKNOWN'} | Platform: {e.platform or 'UNKNOWN'}\n"
                f"Quality: {e.quality} | Status: {e.status}\n"
                f"Snapshots: {len(snaps)}\n\nMetrics (OBSERVED_EXTERNAL_METRIC):\n")
        for m in e.extracted_metrics:
            info += f"  {m.key} = {m.value}\n"
        if snaps:
            info += f"\nLatest snapshot hash: {snaps[-1].content_hash[:16]}…"
        messagebox.showinfo(f"Evidence {eid}", info)

    def _link_assumption(self):
        eid = self._selected_evidence()
        if not eid:
            return
        # simple picker: first 8 assumptions from registry
        assumptions = [a.assumption_id for a in self.registry.all()][:8]
        win = tk.Toplevel(self)
        win.title("Link to Assumption")
        ttk.Label(win, text="Assumption:").pack(padx=8, pady=4)
        aid_var = tk.StringVar(value=assumptions[0] if assumptions else "")
        ttk.Combobox(win, textvariable=aid_var, values=assumptions,
                     state="readonly", width=45).pack(padx=8, pady=4)
        ttk.Label(win, text="Relation:").pack(padx=8, pady=2)
        rel_var = tk.StringVar(value=REL_CONTEXT_FOR)
        ttk.Combobox(win, textvariable=rel_var, values=list(LINK_RELATIONS),
                     state="readonly", width=20).pack(padx=8, pady=4)

        def do_link():
            try:
                ev = self.ev_store.get(eid)
                gate = indirect_support_gate(ev, rel_var.get(),
                                             TARGET_ASSUMPTION, aid_var.get())
                if gate:
                    messagebox.showerror("Link rejected", gate, parent=win)
                    return
                self.link_store.add(eid, TARGET_ASSUMPTION, aid_var.get(),
                                    rel_var.get())
                win.destroy()
                self._refresh()
            except (KeyError, ValueError) as exc:
                messagebox.showerror("Link failed", str(exc), parent=win)

        ttk.Button(win, text="Link", command=do_link).pack(pady=8)

    def _link_observation(self):
        """Observation picker: session → event → confirm (validated)."""
        eid = self._selected_evidence()
        if not eid:
            return
        sessions = self.obs_store.list_sessions()
        if not sessions:
            messagebox.showinfo("Picker", "ไม่มี observation session — import ก่อนที่หน้า Behavior Verification")
            return
        win = tk.Toplevel(self)
        win.title("Link Observation (picker)")
        ttk.Label(win, text="Observation Session:").pack(padx=8, pady=4)
        sid_var = tk.StringVar(value=sessions[0])
        ttk.Combobox(win, textvariable=sid_var, values=sessions,
                     state="readonly", width=40).pack(padx=8, pady=4)
        ttk.Label(win, text="Event index (ว่าง = ทั้ง session):").pack(padx=8, pady=2)
        idx_var = tk.StringVar()
        ttk.Entry(win, textvariable=idx_var, width=10).pack(padx=8, pady=4)

        def do_link():
            sid = sid_var.get()
            try:
                session = self.obs_store.load(sid)
            except KeyError:
                messagebox.showerror("REJECT", f"session not found: {sid}", parent=win)
                return
            idx_raw = idx_var.get().strip()
            event_index = int(idx_raw) if idx_raw else None
            if event_index is not None:
                if not (0 <= event_index < len(session.events)):
                    messagebox.showerror("REJECT",
                                         f"event index out of range (0-{len(session.events)-1})",
                                         parent=win)
                    return
            target = sid if event_index is None else f"{sid}#{event_index}"
            self.link_store.add(eid, TARGET_OBSERVATION, target,
                                REL_CONTEXT_FOR)
            win.destroy()
            self._refresh()

        ttk.Button(win, text="Confirm & Link", command=do_link).pack(pady=8)

    def _selected_link(self):
        sel = self.link_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "เลือก link ก่อน")
            return None
        return self.link_tree.item(sel[0], "values")[0]

    def _confirm_link(self):
        link_id = self._selected_link()
        if not link_id:
            return
        reviewer = tk.simpledialog if False else None
        # simple reviewer prompt
        win = tk.Toplevel(self)
        win.title("Confirm Relationship")
        ttk.Label(win, text="Reviewer name (human confirmation):").pack(padx=8, pady=4)
        name_var = tk.StringVar()
        ttk.Entry(win, textvariable=name_var, width=30).pack(padx=8, pady=4)

        def do_confirm():
            if not name_var.get().strip():
                messagebox.showerror("Confirm", "ต้องใส่ชื่อ reviewer", parent=win)
                return
            try:
                self.link_store.confirm(link_id, name_var.get().strip(),
                                        "confirmed via Desktop Evidence page")
                win.destroy()
                self._refresh()
            except (ValueError, KeyError) as exc:
                messagebox.showerror("Confirm failed", str(exc), parent=win)

        ttk.Button(win, text="Confirm", command=do_confirm).pack(pady=8)

    def _unlink(self):
        link_id = self._selected_link()
        if not link_id:
            return
        if self.link_store.remove(link_id):
            self._refresh()

    def _reject_candidate(self):
        sel = self.cand_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "เลือก candidate ก่อน")
            return
        cid = self.cand_tree.item(sel[0], "values")[0]
        win = tk.Toplevel(self)
        win.title("Reject Candidate")
        ttk.Label(win, text="Reviewer name:").pack(padx=8, pady=4)
        name_var = tk.StringVar()
        ttk.Entry(win, textvariable=name_var, width=30).pack(padx=8, pady=4)

        def do_reject():
            try:
                self.cand_store.reject(cid, name_var.get().strip(),
                                       "rejected via Desktop")
                win.destroy()
                self._refresh()
            except (ValueError, KeyError) as exc:
                messagebox.showerror("Reject failed", str(exc), parent=win)

        ttk.Button(win, text="Reject", command=do_reject).pack(pady=8)
