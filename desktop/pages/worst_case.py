"""Worst Case Simulator page (Module 3)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from core.worst_case import (simulate_worst_case, DEFAULT_MOVE_PRESETS,
                             BUY_ADVERSE, SELL_ADVERSE, BOTH_SIDES, SCENARIOS)
from desktop.theme import make_table, fmt


class WorstCasePage(ttk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent)
        self.state = state
        ttk.Label(self, text="Worst Case Simulator", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="One-directional adverse move — SIMULATION MODEL, not EA output "
                             "and not a substitute for a Strategy Tester run",
                  style="Banner.TLabel").pack(fill="x", pady=(4, 8))

        controls = ttk.Frame(self)
        controls.pack(fill="x")
        ttk.Label(controls, text="Moves ($):").pack(side="left")
        self.move_vars = []
        for mv in DEFAULT_MOVE_PRESETS:
            var = tk.BooleanVar(value=(mv in (30.0, 50.0)))
            cb = ttk.Checkbutton(controls, text=f"{mv:.0f}", variable=var)
            cb.pack(side="left", padx=2)
            self.move_vars.append((mv, var))
        ttk.Label(controls, text="Custom ($):").pack(side="left", padx=(12, 2))
        self.custom_var = tk.StringVar(value="")
        ttk.Entry(controls, textvariable=self.custom_var, width=8).pack(side="left")
        ttk.Label(controls, text="Start price:").pack(side="left", padx=(12, 2))
        self.start_var = tk.StringVar(value="")
        ttk.Entry(controls, textvariable=self.start_var, width=10).pack(side="left")
        ttk.Button(controls, text="Simulate", style="Accent.TButton",
                   command=self.simulate).pack(side="left", padx=12)

        table_frame, self.tree = make_table(self, [
            ("scenario", "Scenario", 110, "w"),
            ("move", "Move ($)", 70, "e"),
            ("levels", "Grid Levels", 80, "e"),
            ("lots", "Total Lots", 80, "e"),
            ("floating", "Est. Floating P/L ($)", 130, "e"),
            ("margin", "Est. Margin ($)", 110, "e"),
            ("equity", "Est. Equity ($)", 110, "e"),
            ("dd", "Drawdown %", 90, "e"),
            ("mlvl", "Margin Level %", 100, "e"),
            ("remaining", "Remaining ($)", 100, "e"),
            ("emerg", "Emergency", 90, "center"),
        ])
        table_frame.pack(fill="both", expand=True, pady=6)

        self.note_lbl = ttk.Label(self, text="", style="Muted.TLabel", wraplength=1000,
                                  justify="left")
        self.note_lbl.pack(anchor="w", fill="x")

    def simulate(self) -> None:
        st = self.state
        moves = [mv for mv, var in self.move_vars if var.get()]
        raw = self.custom_var.get().strip()
        if raw:
            try:
                for part in raw.replace(";", ",").split(","):
                    if part.strip():
                        moves.append(float(part))
            except ValueError:
                messagebox.showerror("Invalid input", f"Custom move must be numbers: {raw}")
                return
        moves = sorted(set(moves))
        if not moves:
            messagebox.showinfo("Nothing selected", "Select at least one move size.")
            return
        try:
            start = float(self.start_var.get()) if self.start_var.get().strip() else None
        except ValueError:
            messagebox.showerror("Invalid input", "Start price must be a number")
            return
        self.tree.delete(*self.tree.get_children())
        for mv in moves:
            for scenario in SCENARIOS:
                try:
                    r = simulate_worst_case(st.config, st.profile, st.account, st.rules(),
                                            st.capital, mv, scenario, start)
                except ValueError as exc:
                    messagebox.showerror("Simulation error", str(exc))
                    return
                mlvl = f"{r.margin_level_pct:.0f}" if r.margin_level_pct is not None else "N/A"
                tag = "warn" if r.floating_pl < -st.capital * st.thresholds.high_dd_percent / 100 else ""
                self.tree.insert("", "end", tags=(tag,) if tag else "", values=(
                    r.scenario, f"{mv:.0f}", r.grid_levels, f"{r.total_lots:.2f}",
                    fmt(r.floating_pl), fmt(r.estimated_margin_used), fmt(r.equity),
                    f"{r.drawdown_pct:.1f}", mlvl, fmt(r.remaining_capital),
                    "TRIG" if r.emergency_triggered else "-"))
        self.note_lbl.configure(text=(
            "Emergency note (last simulated move): " +
            (simulate_worst_case(st.config, st.profile, st.account, st.rules(),
                                 st.capital, moves[-1], BOTH_SIDES, start).emergency_note) +
            "  ·  Estimates exclude spread/commission/swap (PL_CONVERSION_ASSUMPTION_001)."))

    def on_show(self) -> None:
        if not self.start_var.get().strip():
            self.start_var.set(str(self.state.profile.reference_price))
