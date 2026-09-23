"""Dashboard page - instant overview + global toolbar actions live in app.py."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from desktop.theme import (
    MetricCard, section_label, C_WARN, C_OK, C_UNKNOWN, fmt,
)
from core.validation import validate_config, worst_severity, WARNING


class DashboardPage(ttk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent)
        self.state = state
        ttk.Label(self, text="Dashboard", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="SNIPER CashFlow V1.68 — Analyzer / Calculator / Simulator (read-only, no trading)",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(0, 8))

        cards = ttk.Frame(self)
        cards.pack(fill="x", pady=6)
        self.card_capital = MetricCard(cards, "Capital ($)")
        self.card_step = MetricCard(cards, "Grid Step ($)")
        self.card_baselot = MetricCard(cards, "Base Lot")
        self.card_mult = MetricCard(cards, "Multiplier")
        self.card_maxgrid = MetricCard(cards, "Max Simulated Grid")
        self.card_dd = MetricCard(cards, "Estimated DD %")
        self.card_margin = MetricCard(cards, "Margin Used ($)")
        self.card_equity = MetricCard(cards, "Remaining Equity ($)")
        for card in (self.card_capital, self.card_step, self.card_baselot, self.card_mult,
                     self.card_maxgrid, self.card_dd, self.card_margin, self.card_equity):
            card.pack(side="left", fill="both", expand=True, padx=4, pady=2)

        self.banner = ttk.Label(
            self, style="Banner.TLabel",
            text="Simulation Model — not verified internal EA formula. "
                 "All estimates depend on model assumptions (see Assumption Registry).")
        self.banner.pack(fill="x", pady=8)

        section_label(self, "Risk Warnings")
        self.warnings_box = tk.Text(self, height=9, wrap="word", relief="flat",
                                    background="#ffffff", highlightthickness=1,
                                    highlightbackground="#d7dbe5", font=("Segoe UI", 9))
        self.warnings_box.pack(fill="both", expand=True)
        self.warnings_box.tag_configure("warn", foreground=C_WARN)
        self.warnings_box.tag_configure("ok", foreground=C_OK)
        self.warnings_box.tag_configure("unk", foreground=C_UNKNOWN)
        self.warnings_box.configure(state="disabled")

        section_label(self, "Model Status")
        self.model_lbl = ttk.Label(self, text="", style="Muted.TLabel", wraplength=900)
        self.model_lbl.pack(anchor="w")

        self.state.add_listener(self.refresh)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        from core.risk import build_risk_summary
        st = self.state
        self.card_capital.set(fmt(st.capital))
        self.card_step.set(fmt(st.config.GridStepUSD, 1))
        self.card_baselot.set(fmt(st.config.BaseLot, 2))
        self.card_mult.set(fmt(st.config.LotMultiplier, 2))
        try:
            summary = build_risk_summary(st.config, st.profile, st.account,
                                         st.rules(), st.capital, st.thresholds)
            self.card_maxgrid.set(str(summary.max_simulated_grid))
            dd_color = C_WARN if summary.estimated_dd_percent >= st.thresholds.high_dd_percent else C_OK
            self.card_dd.set(f"{summary.estimated_dd_percent:.1f}%", dd_color)
            self.card_margin.set(fmt(summary.margin_used))
            eq_color = C_OK if summary.remaining_equity > st.capital * 0.5 else C_WARN
            self.card_equity.set(fmt(summary.remaining_equity), eq_color)
            self._render_warnings(summary)
        except Exception as exc:  # never crash the dashboard
            self.card_maxgrid.set("-")
            self.card_dd.set("-")
            self.card_margin.set("-")
            self.card_equity.set("-")
            self._set_text("Risk summary unavailable: " + str(exc), "warn")

        rules = st.rules()
        n_ver = len(st.registry.by_status("VERIFIED_FROM_DOCUMENTATION"))
        n_obs = len(st.registry.by_status("OBSERVED_FROM_TESTING"))
        n_ass = len(st.registry.by_status("MODEL_ASSUMPTION"))
        n_unk = len(st.registry.by_status("UNKNOWN"))
        self.model_lbl.configure(text=(
            f"Simulation model {rules.model_version} (lot={rules.lot_formula}, "
            f"grid={rules.grid_spacing_rule}, basket={rules.basket_scope}, "
            f"partial={rules.partial_close_rule})  ·  Assumptions: "
            f"{n_ver} verified-from-doc, {n_obs} observed, {n_ass} model, {n_unk} unknown"))

    def _render_warnings(self, summary) -> None:
        st = self.state
        lines = []
        for fl in summary.flags:
            tag = "warn" if fl.severity == "warning" else "unk"
            lines.append((f"[{fl.severity.upper()}] {fl.flag} — {fl.detail}", tag))
        for issue in validate_config(st.config, st.profile, st.account, st.capital):
            tag = "warn" if issue.severity == "ERROR" else "unk"
            lines.append((f"[{issue.severity}] {issue.code}: {issue.message}", tag))
        if not lines:
            lines.append(("No warnings for current settings.", "ok"))
        self.warnings_box.configure(state="normal")
        self.warnings_box.delete("1.0", "end")
        for text, tag in lines:
            self.warnings_box.insert("end", text + "\n", tag)
        self.warnings_box.configure(state="disabled")

    def _set_text(self, text: str, tag: str) -> None:
        self.warnings_box.configure(state="normal")
        self.warnings_box.delete("1.0", "end")
        self.warnings_box.insert("end", text + "\n", tag)
        self.warnings_box.configure(state="disabled")

    def on_show(self) -> None:
        self.refresh()
