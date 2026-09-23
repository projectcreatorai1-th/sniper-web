"""Behavior Verification page (Modules 10, 13, 14, 15).

Workflow:
  1. New Test Session (or select an existing one)
  2. Import data (CSV / tester report / log) or add manual observations
  3. Analyze -> compare Observed vs Simulation Model (MATCH/MISMATCH/UNKNOWN)
  4. Optionally: fit a lot rule from observations and APPLY it (creates a new
     versioned model rule) - only after explicit confirmation.
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from core.mt5_adapters import (
    BehaviorRecord, EVENT_TYPES, load_adapter,
)
from core.model_vs_observed import compare_behavior, suggest_lot_rule_from_observed
from core.sessions import TestSession
from desktop.theme import make_table, section_label


class BehaviorPage(ttk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent)
        self.state = state
        ttk.Label(self, text="Behavior Verification", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="Record what the EA actually does on Demo/Strategy Tester "
                             "and compare it against the Simulation Model — without "
                             "decompiling the EX5.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(0, 6))

        # ---- session bar ------------------------------------------------
        sess = ttk.LabelFrame(self, text="Test Session (Module 15)", padding=6)
        sess.pack(fill="x", pady=4)
        ttk.Button(sess, text="New Session", command=self.new_session).pack(side="left")
        ttk.Label(sess, text="Session:").pack(side="left", padx=(12, 2))
        self.session_var = tk.StringVar(value="(none)")
        self.session_cb = ttk.Combobox(sess, textvariable=self.session_var,
                                       state="readonly", width=34)
        self.session_cb.pack(side="left")
        ttk.Button(sess, text="Load", command=self.load_session).pack(side="left", padx=4)
        ttk.Button(sess, text="Delete", command=self.delete_session).pack(side="left")
        self.session_info = ttk.Label(sess, text="", style="Muted.TLabel")
        self.session_info.pack(side="left", padx=12)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, pady=4)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        # ---- left: import + records --------------------------------------
        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        imp = ttk.LabelFrame(left, text="Import Data (Module 13 - adapters)", padding=6)
        imp.pack(fill="x")
        ttk.Label(imp, text="Sources: standard CSV (timestamp,event,lot,price,…), MT5 tester "
                            "report (CSV/HTML), text log, manual entry.",
                  style="Muted.TLabel", wraplength=520).pack(anchor="w")
        row = ttk.Frame(imp)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Adapter:").pack(side="left")
        self.adapter_var = tk.StringVar(value="auto")
        ttk.Combobox(row, textvariable=self.adapter_var, width=12, state="readonly",
                     values=["auto", "csv", "tester", "log"]).pack(side="left", padx=4)
        ttk.Button(row, text="Import File…", command=self.import_data).pack(side="left", padx=6)
        ttk.Button(row, text="Add Manual Entry…", command=self.manual_entry).pack(side="left")

        rec_frame, self.records_tree = make_table(left, [
            ("time", "Timestamp", 130, "w"),
            ("event", "Event", 110, "w"),
            ("side", "Side", 50, "center"),
            ("level", "Level", 50, "e"),
            ("lot", "Lot", 60, "e"),
            ("price", "Price", 80, "e"),
            ("basket", "Basket P/L", 90, "e"),
            ("pos", "Pos", 50, "e"),
            ("lots", "Total Lots", 80, "e"),
            ("src", "Source", 80, "w"),
        ])
        rec_frame.pack(fill="both", expand=True, pady=6)
        rec_row = ttk.Frame(left)
        rec_row.pack(fill="x")
        ttk.Button(rec_row, text="Clear Records", command=self.clear_records).pack(side="left")
        self.rec_count = ttk.Label(rec_row, text="0 records", style="Muted.TLabel")
        self.rec_count.pack(side="left", padx=8)

        # ---- right: comparison + model rules ------------------------------
        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew")
        cmp_lf = ttk.LabelFrame(right, text="Model vs Observed (Module 14)", padding=6)
        cmp_lf.pack(fill="both", expand=True)
        ttk.Button(cmp_lf, text="Compare Model vs Observed", style="Accent.TButton",
                   command=self.run_comparison).pack(anchor="w", pady=4)
        cmp_frame, self.cmp_tree = make_table(cmp_lf, [
            ("check", "Check", 130, "w"),
            ("result", "Result", 80, "center"),
            ("detail", "Detail", 300, "w"),
        ])
        cmp_frame.pack(fill="both", expand=True)
        self.cmp_summary = ttk.Label(cmp_lf, text="", style="Muted.TLabel", wraplength=360)
        self.cmp_summary.pack(anchor="w", pady=(4, 0))

        rules_lf = ttk.LabelFrame(right, text="Observed Rule Fitting (apply = new model version)",
                                  padding=6)
        rules_lf.pack(fill="x", pady=6)
        ttk.Button(rules_lf, text="Suggest Lot Rule from Observations",
                   command=self.suggest_rule).pack(anchor="w")
        self.suggest_lbl = ttk.Label(rules_lf, text="", style="Muted.TLabel",
                                     wraplength=380, justify="left")
        self.suggest_lbl.pack(anchor="w", pady=2)
        self.apply_btn = ttk.Button(rules_lf, text="Apply Observed Rule",
                                    command=self.apply_rule, state="disabled")
        self.apply_btn.pack(anchor="w")
        self._suggestion = None
        self.refresh_sessions()

    # ------------------------------------------------------------------ sessions
    def refresh_sessions(self) -> None:
        ids = self.state.session_store.list_sessions()
        self.session_cb.configure(values=ids)
        cur = self.state.current_session
        if cur:
            self.session_var.set(cur.session_id)
            self.session_info.configure(text=f"{cur.symbol or '-'} · {cur.broker or '-'} · "
                                             f"{cur.account_type or '-'} · "
                                             f"{len(cur.observed_events)} events")

    def _require_session(self) -> bool:
        if self.state.current_session is None:
            messagebox.showinfo("No session", "Create or load a Test Session first.")
            return False
        return True

    def new_session(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("New Test Session")
        dlg.geometry("420x300")
        dlg.transient(self.winfo_toplevel())
        fields = {}
        for i, (key, label) in enumerate([
            ("ea_version", "EA version"), ("symbol", "Symbol"),
            ("broker", "Broker"), ("account_type", "Account type (demo/live/tester)"),
            ("initial_balance", "Initial balance ($)"), ("start_time", "Start time"),
            ("end_time", "End time"), ("notes", "Notes"),
        ]):
            ttk.Label(dlg, text=label + ":").grid(row=i, column=0, sticky="w", padx=8, pady=3)
            var = tk.StringVar(value="")
            ttk.Entry(dlg, textvariable=var, width=30).grid(row=i, column=1, padx=4, pady=3)
            fields[key] = var

        def ok():
            vals = {k: v.get() for k, v in fields.items()}
            try:
                ib = float(vals.pop("initial_balance") or 0) or None
            except ValueError:
                messagebox.showerror("Invalid", "Initial balance must be a number", parent=dlg)
                return
            sess = TestSession.new(
                ea_version=vals["ea_version"] or "1.68", symbol=vals["symbol"],
                broker=vals["broker"], account_type=vals["account_type"],
                initial_balance=ib, start_time=vals["start_time"],
                end_time=vals["end_time"], notes=vals["notes"],
                config=self.state.config.to_dict())
            self.state.session_store.save(sess)
            self.state.current_session = sess
            self._render_records()
            self.refresh_sessions()
            dlg.destroy()

        ttk.Button(dlg, text="Create", command=ok).grid(row=len(fields), column=1,
                                                        sticky="e", pady=8)

    def load_session(self) -> None:
        sid = self.session_var.get()
        if not sid or sid == "(none)":
            return
        try:
            self.state.current_session = self.state.session_store.load(sid)
        except KeyError:
            messagebox.showerror("Load failed", "session file not found")
            return
        self._render_records()
        self.refresh_sessions()

    def delete_session(self) -> None:
        sid = self.session_var.get()
        if not sid or sid == "(none)":
            return
        if not messagebox.askyesno("Delete session", f"Delete session {sid}?"):
            return
        self.state.session_store.delete(sid)
        if self.state.current_session and self.state.current_session.session_id == sid:
            self.state.current_session = None
            self.records_tree.delete(*self.records_tree.get_children())
        self.refresh_sessions()

    # ------------------------------------------------------------------ import
    def import_data(self) -> None:
        if not self._require_session():
            return
        path = filedialog.askopenfilename(filetypes=[
            ("MT5 / behavior data", "*.csv *.html *.htm *.txt *.log"),
            ("All files", "*.*")])
        if not path:
            return
        kind = None if self.adapter_var.get() == "auto" else self.adapter_var.get()
        try:
            adapter, records = load_adapter(path, kind)
        except Exception as exc:
            messagebox.showerror("Import failed", f"{os.path.basename(path)}:\n{exc}")
            return
        sess = self.state.current_session
        sess.report_files.append(os.path.basename(path))
        sess.observed_events.extend(r.to_dict() for r in records)
        self.state.session_store.save(sess)
        self._render_records()
        self.refresh_sessions()
        messagebox.showinfo("Imported",
                            f"{len(records)} records loaded via {adapter.name} adapter.")

    def manual_entry(self) -> None:
        if not self._require_session():
            return
        dlg = tk.Toplevel(self)
        dlg.title("Manual Behavior Entry")
        dlg.geometry("460x360")
        dlg.transient(self.winfo_toplevel())
        vars_ = {}

        def add_field(key, label, width=14):
            row = len(vars_)
            ttk.Label(dlg, text=label + ":").grid(row=row, column=0, sticky="w", padx=8, pady=3)
            var = tk.StringVar(value="")
            if key == "event":
                w = ttk.Combobox(dlg, textvariable=var, values=list(EVENT_TYPES),
                                 state="readonly", width=width)
                var.set("OPEN_POSITION")
            elif key == "side":
                w = ttk.Combobox(dlg, textvariable=var, values=["", "BUY", "SELL"],
                                 state="readonly", width=width)
            else:
                w = ttk.Entry(dlg, textvariable=var, width=width)
            w.grid(row=row, column=1, padx=4, pady=3)
            vars_[key] = var

        for key, label in [
            ("timestamp", "Timestamp"), ("event", "Event"), ("side", "Side"),
            ("grid_level", "Grid level"), ("lot", "Lot"), ("price", "Price"),
            ("basket_pl", "Basket P/L ($)"), ("balance", "Balance ($)"),
            ("position_count", "Position count"), ("total_lots", "Total lots"),
        ]:
            add_field(key, label)

        def num_or_none(var, cast=float):
            raw = var.get().strip()
            if not raw:
                return None
            try:
                return cast(float(raw))
            except ValueError:
                return None

        def ok():
            rec = BehaviorRecord(
                timestamp=vars_["timestamp"].get(),
                event=vars_["event"].get(),
                side=vars_["side"].get(),
                grid_level=num_or_none(vars_["grid_level"], int),
                lot=num_or_none(vars_["lot"]),
                price=num_or_none(vars_["price"]),
                basket_pl=num_or_none(vars_["basket_pl"]),
                balance=num_or_none(vars_["balance"]),
                position_count=num_or_none(vars_["position_count"], int),
                total_lots=num_or_none(vars_["total_lots"]),
                source="manual",
            )
            sess = self.state.current_session
            sess.observed_events.append(rec.to_dict())
            self.state.session_store.save(sess)
            self._render_records()
            self.refresh_sessions()
            dlg.destroy()

        ttk.Button(dlg, text="Add", command=ok).grid(row=len(vars_) + 1, column=1,
                                                     sticky="e", pady=8)

    def clear_records(self) -> None:
        if not self._require_session():
            return
        if not messagebox.askyesno("Clear records",
                                   "Remove ALL observed events from this session?"):
            return
        self.state.current_session.observed_events = []
        self.state.session_store.save(self.state.current_session)
        self._render_records()
        self.refresh_sessions()

    def _render_records(self) -> None:
        self.records_tree.delete(*self.records_tree.get_children())
        sess = self.state.current_session
        if not sess:
            self.rec_count.configure(text="0 records")
            return
        for d in sess.observed_events:
            self.records_tree.insert("", "end", values=(
                d.get("timestamp", ""), d.get("event", ""), d.get("side", ""),
                d.get("grid_level", ""), d.get("lot", ""), d.get("price", ""),
                d.get("basket_pl", ""), d.get("position_count", ""),
                d.get("total_lots", ""), d.get("source", "")))
        self.rec_count.configure(text=f"{len(sess.observed_events)} records")

    # ------------------------------------------------------------------ compare
    def run_comparison(self) -> None:
        sess = self.state.current_session
        if not sess:
            messagebox.showinfo("No session", "Load a Test Session with observed events first.")
            return
        records = [BehaviorRecord.from_dict(d) for d in sess.observed_events]
        if not records:
            messagebox.showinfo("No data", "This session has no observed events.")
            return
        from core.config import EAConfig
        config = EAConfig.from_dict(sess.config) if sess.config else self.state.config
        report = compare_behavior(records, config, self.state.profile,
                                  self.state.rules())
        self.cmp_tree.delete(*self.cmp_tree.get_children())
        for ch in report.checks:
            tag = {"MATCH": "ok", "MISMATCH": "warn", "UNKNOWN": "unk"}[ch.result]
            self.cmp_tree.insert("", "end", tags=(tag,), values=(
                ch.check, ch.result, ch.detail))
        self.cmp_summary.configure(text=(
            f"Overall: {report.overall} · {report.match_count} MATCH / "
            f"{report.mismatch_count} MISMATCH / {report.unknown_count} UNKNOWN"))
        sess.last_comparison = report.to_dict()
        self.state.session_store.save(sess)

    # ------------------------------------------------------------------ rules
    def suggest_rule(self) -> None:
        sess = self.state.current_session
        if not sess or not sess.observed_events:
            messagebox.showinfo("No data", "Import observed events first.")
            return
        records = [BehaviorRecord.from_dict(d) for d in sess.observed_events]
        suggestion = suggest_lot_rule_from_observed(records, self.state.profile)
        self._suggestion = suggestion
        if suggestion is None:
            self.suggest_lbl.configure(
                text="Not enough (level, lot) observations yet — need ≥ 3 priced entries.")
            self.apply_btn.configure(state="disabled")
            return
        cands = suggestion["candidates"]
        txt = (f"{suggestion['points']} observations. Fitted mean-absolute-error:\n"
               + "\n".join(f"  {k}: {v['mae']:.4f}" for k, v in cands.items())
               + f"\nBest fit: {suggestion['best_rule']} ({suggestion['best_params']})\n"
                 "Applying creates a NEW model version; current results stay reproducible.")
        self.suggest_lbl.configure(text=txt)
        self.apply_btn.configure(state="normal")

    def apply_rule(self) -> None:
        if not self._suggestion:
            return
        best = self._suggestion["best_rule"]
        params = self._suggestion["best_params"]
        rules = self.state.rules()
        changes = []
        if best == "GEOMETRIC":
            if "multiplier" in params:
                changes.append(f"LotMultiplier fitted to {params['multiplier']}")
                rules.lot_formula = "GEOMETRIC"
        elif best == "ARITHMETIC":
            rules.lot_formula = "ARITHMETIC"
            if "step_lots" in params:
                rules.arithmetic_step_lots = params["step_lots"]
                changes.append(f"arithmetic step {params['step_lots']} lots/level")
        else:
            rules.lot_formula = "FLAT"
        changes.append("source: Apply Observed Rule (user confirmed)")
        if not messagebox.askyesno(
                "Apply Observed Rule",
                "Apply the fitted lot rule as a NEW simulation model version?\n\n"
                + "\n".join(changes) +
                "\n\nThe current model is never overwritten - versions are kept."):
            return
        try:
            self.state.model_store.apply_new_version(
                rules, source="observed-applied", changes=changes,
                notes=f"fitted from {self._suggestion['points']} observations")
        except ValueError as exc:
            messagebox.showerror("Apply failed", str(exc))
            return
        self.state.notify_changed()
        messagebox.showinfo("Model version created",
                            f"New active model version: {self.state.rules().model_version}")

    def on_show(self) -> None:
        self.refresh_sessions()
        self._render_records()
