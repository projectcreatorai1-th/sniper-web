"""Settings page: symbol profile, account, assumption registry, model versions."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from core.assumptions import (ALL_STATUSES, VERIFIED_FROM_DOCUMENTATION,
                              OBSERVED_FROM_TESTING, MODEL_ASSUMPTION, UNKNOWN)
from core.symbol_profile import builtin_profiles
from desktop.theme import make_table, section_label


class SettingsPage(ttk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent)
        self.state = state
        ttk.Label(self, text="Settings", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="Broker constraints are configurable — nothing is hard-coded. "
                             "Every profile value can be edited per broker.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(0, 6))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        # ---- symbol profile + account ---------------------------------------
        prof_lf = ttk.LabelFrame(body, text="Symbol Profile (broker constraints)", padding=8)
        prof_lf.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.prof_vars = {}
        for key, label in [
            ("name", "Symbol name"), ("contract_size", "Contract size"),
            ("tick_size", "Tick size"), ("lot_min", "Min lot"),
            ("lot_max", "Max lot"), ("lot_step", "Lot step"),
            ("digits", "Digits"), ("reference_price", "Reference price"),
        ]:
            row = ttk.Frame(prof_lf)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, width=18, anchor="w").pack(side="left")
            var = tk.StringVar()
            ttk.Entry(row, textvariable=var, width=16).pack(side="left")
            self.prof_vars[key] = var
        ttk.Button(prof_lf, text="Load builtin: XAUUSD / BTCUSD / EURUSD",
                   command=self.load_builtin).pack(anchor="w", pady=4)
        ttk.Button(prof_lf, text="Apply Profile", style="Accent.TButton",
                   command=self.apply_profile).pack(anchor="w", pady=2)

        acct_lf = ttk.LabelFrame(body, text="Account", padding=8)
        acct_lf.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        self.acct_vars = {}
        for key, label in [("leverage", "Leverage (1:X)"), ("margin_rate", "Margin rate"),
                           ("currency", "Currency")]:
            row = ttk.Frame(acct_lf)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, width=18, anchor="w").pack(side="left")
            var = tk.StringVar()
            ttk.Entry(row, textvariable=var, width=16).pack(side="left")
            self.acct_vars[key] = var
        ttk.Button(acct_lf, text="Apply Account", style="Accent.TButton",
                   command=self.apply_account).pack(anchor="w", pady=4)
        ttk.Label(acct_lf, text="Margin model: lots × contract × price / leverage × rate\n"
                                "(MARGIN_ASSUMPTION_001 — configure per broker)",
                  style="Muted.TLabel", wraplength=320, justify="left").pack(anchor="w")

        # ---- assumption registry ----------------------------------------------
        reg_lf = ttk.LabelFrame(body, text="Assumption Registry (Module 11)", padding=6)
        reg_lf.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        reg_frame, self.reg_tree = make_table(reg_lf, [
            ("id", "ID", 240, "w"),
            ("status", "Status", 170, "w"),
            ("title", "Title", 260, "w"),
        ])
        reg_frame.pack(fill="both", expand=True)
        row = ttk.Frame(reg_lf)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Set status:").pack(side="left")
        self.reg_status_var = tk.StringVar(value=MODEL_ASSUMPTION)
        ttk.Combobox(row, textvariable=self.reg_status_var, state="readonly",
                     width=28, values=list(ALL_STATUSES)).pack(side="left", padx=4)
        ttk.Button(row, text="Update Selected (evidence-based)",
                   command=self.update_assumption).pack(side="left", padx=4)
        self.reg_detail = ttk.Label(reg_lf, text="", style="Muted.TLabel",
                                    wraplength=560, justify="left")
        self.reg_detail.pack(anchor="w", fill="x")
        self.reg_tree.bind("<<TreeviewSelect>>", self.show_assumption_detail)

        # ---- model versions -----------------------------------------------------
        mv_lf = ttk.LabelFrame(body, text="Simulation Model Versions", padding=6)
        mv_lf.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)
        mv_frame, self.mv_tree = make_table(mv_lf, [
            ("ver", "Version", 70, "w"),
            ("time", "Timestamp", 150, "w"),
            ("source", "Source", 110, "w"),
            ("changes", "Changes", 220, "w"),
        ])
        mv_frame.pack(fill="both", expand=True)
        self.mv_note = ttk.Label(
            mv_lf, text="The model never changes automatically from observations —\n"
                        "new versions are created only via Apply Observed Rule\n"
                        "(Behavior Verification page).",
            style="Muted.TLabel", justify="left")
        self.mv_note.pack(anchor="w", pady=4)

        self.load_into_form()

    # ------------------------------------------------------------------
    def load_into_form(self) -> None:
        p = self.state.profile
        for key, var in self.prof_vars.items():
            var.set(str(getattr(p, key)))
        a = self.state.account
        for key, var in self.acct_vars.items():
            var.set(str(getattr(a, key)))
        self.render_registry()
        self.render_versions()

    def load_builtin(self) -> None:
        names = [p.name for p in builtin_profiles()]
        chosen = messagebox.askyesnocancel(
            "Load builtin", f"Load {names[0]}? (Yes=XAUUSD, No=BTCUSD, Cancel=EURUSD)")
        idx = {True: 0, False: 1, None: 2}[chosen]
        prof = builtin_profiles()[idx]
        for key, var in self.prof_vars.items():
            var.set(str(getattr(prof, key)))

    def apply_profile(self) -> None:
        p = self.state.profile
        try:
            for key, var in self.prof_vars.items():
                cur = getattr(p, key)
                raw = var.get().strip()
                setattr(p, key, type(cur)(raw) if isinstance(cur, str) else
                        (int(raw) if isinstance(cur, int) else float(raw)))
        except ValueError:
            messagebox.showerror("Invalid value", "Profile fields must be numeric "
                                                  "(name can be text)")
            return
        self.state.notify_changed()
        messagebox.showinfo("Applied", f"Symbol profile '{p.name}' applied.")

    def apply_account(self) -> None:
        a = self.state.account
        try:
            a.leverage = int(float(self.acct_vars["leverage"].get()))
            a.margin_rate = float(self.acct_vars["margin_rate"].get())
            a.currency = self.acct_vars["currency"].get().strip() or "USD"
        except ValueError:
            messagebox.showerror("Invalid value", "Leverage/margin rate must be numeric")
            return
        self.state.notify_changed()
        messagebox.showinfo("Applied", "Account settings applied.")

    # ------------------------------------------------------------------
    def render_registry(self) -> None:
        self.reg_tree.delete(*self.reg_tree.get_children())
        for a in self.state.registry.all():
            tag = {"VERIFIED_FROM_DOCUMENTATION": "ok", "OBSERVED_FROM_TESTING": "ok",
                   "MODEL_ASSUMPTION": "unk", "UNKNOWN": "unk"}.get(a.status, "")
            self.reg_tree.insert("", "end", tags=(tag,) if tag else "",
                                 values=(a.assumption_id, a.status, a.title))

    def show_assumption_detail(self, _e=None) -> None:
        sel = self.reg_tree.selection()
        if not sel:
            return
        aid = str(self.reg_tree.item(sel[0])["values"][0])
        a = self.state.registry.try_get(aid)
        if a:
            self.reg_detail.configure(
                text=f"{a.assumption_id}\n{a.detail}\nSource: {a.source or '-'}\n"
                     f"Evidence: {a.evidence or '-'}")

    def update_assumption(self) -> None:
        sel = self.reg_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select an assumption row first.")
            return
        aid = str(self.reg_tree.item(sel[0])["values"][0])
        status = self.reg_status_var.get()
        from tkinter import simpledialog
        evidence = simpledialog.askstring(
            "Evidence", "Evidence note (recommended when changing status):") or ""
        try:
            self.state.registry.set_status(aid, status, evidence)
        except (KeyError, ValueError) as exc:
            messagebox.showerror("Update failed", str(exc))
            return
        self.render_registry()

    def render_versions(self) -> None:
        self.mv_tree.delete(*self.mv_tree.get_children())
        for e in self.state.model_store.all_versions():
            self.mv_tree.insert("", "end", values=(
                e.model_version, e.timestamp, e.source, "; ".join(e.changes)))

    def on_show(self) -> None:
        self.load_into_form()
