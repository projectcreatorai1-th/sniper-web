"""Risk Dashboard page (Module 5)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from core.risk import build_risk_summary
from desktop.theme import make_table, section_label, fmt, C_WARN, C_OK


class RiskPage(ttk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent)
        self.state = state
        ttk.Label(self, text="Risk", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="Measured data + warnings at user-configurable thresholds — "
                             "no best/worst scoring", style="Subtitle.TLabel").pack(
            anchor="w", pady=(0, 6))

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Button(top, text="Recalculate", style="Accent.TButton",
                   command=self.refresh).pack(side="left")

        table_frame, self.tree = make_table(self, [
            ("metric", "Metric", 260, "w"),
            ("value", "Value", 180, "e"),
        ])
        table_frame.pack(fill="both", expand=True, pady=6)

        section_label(self, "Risk Flags")
        flags_frame, self.flags_tree = make_table(self, [
            ("flag", "Flag", 240, "w"),
            ("detail", "Detail", 620, "w"),
        ], stretch=True)
        flags_frame.pack(fill="both", expand=True, pady=4)

        lf = ttk.LabelFrame(self, text="Thresholds (user configurable)", padding=8)
        lf.pack(fill="x", pady=6)
        self.th_entries = {}
        th = state.thresholds
        for i, (key, label) in enumerate([
            ("high_lot_growth_multiplier", "HIGH LOT GROWTH: multiplier ≥"),
            ("high_grid_depth_levels", "HIGH GRID DEPTH: levels ≥"),
            ("high_dd_percent", "HIGH ESTIMATED DD: % ≥"),
            ("low_capital_buffer_percent", "LOW CAPITAL BUFFER: remaining ≤ %"),
            ("high_margin_usage_percent", "HIGH MARGIN USAGE: % >"),
            ("max_simulated_grid_levels", "Dashboard simulation depth (levels)"),
            ("reference_adverse_move_usd", "Reference adverse move ($)"),
        ]):
            row_i, col_i = divmod(i, 2)
            cell = ttk.Frame(lf)
            cell.grid(row=row_i, column=col_i, sticky="w", padx=8, pady=3)
            ttk.Label(cell, text=label).pack(side="left")
            var = tk.StringVar(value=str(getattr(th, key)))
            ttk.Entry(cell, textvariable=var, width=8).pack(side="left", padx=6)
            self.th_entries[key] = var
        ttk.Button(lf, text="Apply Thresholds", command=self.apply_thresholds).grid(
            row=3, column=0, sticky="w", padx=8, pady=6)

    def apply_thresholds(self) -> None:
        th = self.state.thresholds
        for key, var in self.th_entries.items():
            try:
                val = float(var.get())
                cur = getattr(th, key)
                setattr(th, key, int(val) if isinstance(cur, int) else val)
            except ValueError:
                messagebox.showerror("Invalid threshold", f"{key}: must be a number")
                return
        self.state.notify_changed()
        self.refresh()

    def refresh(self) -> None:
        st = self.state
        try:
            s = build_risk_summary(st.config, st.profile, st.account, st.rules(),
                                   st.capital, st.thresholds)
        except ValueError as exc:
            messagebox.showerror("Risk summary failed", str(exc))
            return
        rows = [
            ("Capital ($)", fmt(s.capital)),
            ("Base Lot", fmt(s.base_lot)),
            ("Grid Step ($)", fmt(s.grid_step)),
            ("Lot Multiplier", fmt(s.lot_multiplier)),
            ("Max Simulated Grid", str(s.max_simulated_grid)),
            ("Total Lots", fmt(s.total_lots)),
            ("Estimated Exposure ($)", fmt(s.estimated_exposure)),
            ("Estimated Worst Floating Loss ($)", fmt(s.estimated_worst_floating_loss)),
            ("Estimated DD (%)", fmt(s.estimated_dd_percent)),
            ("Margin Used ($)", fmt(s.margin_used)),
            ("Margin Usage (%)", fmt(s.margin_usage_percent)),
            ("Remaining Equity ($)", fmt(s.remaining_equity)),
            ("Basket Target ($)", fmt(s.basket_target) if s.basket_target is not None else "off"),
        ]
        self.tree.delete(*self.tree.get_children())
        for name, value in rows:
            tag = "warn" if name.startswith(("Estimated Worst", "Estimated DD")) and \
                (s.estimated_worst_floating_loss < 0) else ""
            self.tree.insert("", "end", tags=(tag,) if tag else "", values=(name, value))

        self.flags_tree.delete(*self.flags_tree.get_children())
        for fl in s.flags:
            tag = "warn" if fl.severity == "warning" else "unk"
            self.flags_tree.insert("", "end", tags=(tag,), values=(fl.flag, fl.detail))

    def on_show(self) -> None:
        for key, var in self.th_entries.items():
            var.set(str(getattr(self.state.thresholds, key)))
        self.refresh()
