"""Reports page (Module 12): build a report bundle and export JSON/CSV/HTML."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.grid import build_grid_table
from core.report import (ReportBundle, export_report_json, export_report_csv,
                         export_report_html)
from core.worst_case import simulate_worst_case, DEFAULT_MOVE_PRESETS, SCENARIOS
from core.basket import simulate_basket
from desktop.theme import section_label


class ReportsPage(ttk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent)
        self.state = state
        ttk.Label(self, text="Reports", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="Bundle: EA configuration · simulation parameters · grid table · "
                             "worst case · risk summary · backtest summary · assumptions · "
                             "warnings",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(0, 6))

        opts = ttk.LabelFrame(self, text="Report contents", padding=8)
        opts.pack(fill="x")
        self.include_grid = tk.BooleanVar(value=True)
        self.include_worst = tk.BooleanVar(value=True)
        self.include_basket = tk.BooleanVar(value=True)
        for i, (var, label) in enumerate([
            (self.include_grid, "Grid table"),
            (self.include_worst, "Worst case"),
            (self.include_basket, "Basket simulation"),
        ]):
            ttk.Checkbutton(opts, text=label, variable=var).grid(
                row=0, column=i, sticky="w", padx=10)
        row2 = ttk.Frame(opts)
        row2.grid(row=1, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Label(row2, text="Grid depth:").pack(side="left")
        self.depth_var = tk.StringVar(value="20")
        ttk.Combobox(row2, textvariable=self.depth_var, width=5, state="readonly",
                     values=["5", "10", "20", "30", "50"]).pack(side="left", padx=4)
        ttk.Label(row2, text="Worst moves:").pack(side="left", padx=(12, 2))
        self.moves_var = tk.StringVar(value="10,20,30,50,75,100")
        ttk.Entry(row2, textvariable=self.moves_var, width=16).pack(side="left")

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=8)
        ttk.Button(actions, text="Export JSON…", command=lambda: self.export("json")).pack(side="left")
        ttk.Button(actions, text="Export CSV…", command=lambda: self.export("csv")).pack(side="left", padx=6)
        ttk.Button(actions, text="Export HTML…", style="Accent.TButton",
                   command=lambda: self.export("html")).pack(side="left")
        ttk.Label(actions, text="(HTML is printable to PDF from any browser; no PDF "
                                "dependency is bundled)", style="Muted.TLabel").pack(
            side="left", padx=10)

        section_label(self, "Preview")
        self.preview = tk.Text(self, height=18, wrap="word", relief="flat",
                               background="#ffffff", highlightthickness=1,
                               highlightbackground="#d7dbe5", font=("Consolas", 9))
        self.preview.pack(fill="both", expand=True)

    def _build_bundle(self) -> ReportBundle:
        st = self.state
        grid_tables = []
        worst = []
        baskets = []
        if self.include_grid.get():
            depth = int(self.depth_var.get())
            for side in ("BUY", "SELL"):
                grid_tables.append(build_grid_table(st.config, st.profile, st.account,
                                                    st.rules(), depth, side))
        if self.include_worst.get():
            moves = []
            for part in self.moves_var.get().replace(";", ",").split(","):
                part = part.strip()
                if part:
                    try:
                        moves.append(float(part))
                    except ValueError:
                        pass
            moves = moves or list(DEFAULT_MOVE_PRESETS)
            for mv in moves:
                for scenario in SCENARIOS:
                    worst.append(simulate_worst_case(st.config, st.profile, st.account,
                                                     st.rules(), st.capital, mv, scenario))
        if self.include_basket.get():
            depth = int(self.depth_var.get())
            for side in ("BUY", "SELL"):
                baskets.append(simulate_basket(st.config, st.profile, st.rules(),
                                               side, min(depth, 20)))
        return ReportBundle(
            config=st.config, profile=st.profile, account=st.account,
            capital=st.capital, grid_tables=grid_tables, worst_cases=worst,
            basket_sims=baskets, backtest_summary=st.backtest_summary)

    def export(self, fmt: str) -> None:
        try:
            bundle = self._build_bundle()
            d = bundle.to_dict()
        except Exception as exc:
            messagebox.showerror("Report failed", str(exc))
            return
        ext = {"json": ".json", "csv": ".csv", "html": ".html"}[fmt]
        path = filedialog.asksaveasfilename(defaultextension=ext,
                                            initialfile=f"sniper_report{ext}",
                                            filetypes=[(fmt.upper(), f"*{ext}")])
        if not path:
            return
        try:
            if fmt == "json":
                export_report_json(bundle, path)
            elif fmt == "csv":
                export_report_csv(bundle, path)
            else:
                export_report_html(bundle, path)
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        self._preview(d)
        messagebox.showinfo("Export", f"Report written to {os.path.basename(path)}")

    def _preview(self, d: dict) -> None:
        self.preview.delete("1.0", "end")
        self.preview.insert("end", f"Report generated {d['generated']}\n")
        self.preview.insert("end", f"Model version: {self.state.rules().model_version}\n")
        self.preview.insert("end", f"Grid tables: {len(d['grid_tables'])} · "
                                   f"worst cases: {len(d['worst_case'])} · "
                                   f"basket sims: {len(d['basket_simulation'])}\n")
        if d["risk_summary"]:
            rs = d["risk_summary"]
            self.preview.insert(
                "end",
                f"Risk: DD {rs['estimated_dd_percent']}% · margin {rs['margin_used']} · "
                f"remaining equity {rs['remaining_equity']}\n")
            self.preview.insert("end", "Flags: " +
                                ", ".join(f["flag"] for f in rs["flags"]) + "\n")
        self.preview.insert("end", f"Assumptions attached: {len(d['assumptions'])}\n")
        self.preview.insert("end", f"Warnings: {len(d['warnings'])}\n")

    def on_show(self) -> None:
        pass
