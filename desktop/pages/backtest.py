"""Backtest page (Modules 6 & 7): import + analysis + balance curve."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.backtest_io import parse_backtest_file
from desktop.theme import make_table, section_label, fmt, C_MUTED


class BacktestPage(ttk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent)
        self.state = state
        ttk.Label(self, text="Backtest", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="Import MT5 Strategy Tester results (CSV / HTML / TXT). "
                             "Missing data is shown as N/A - nothing is invented.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(0, 6))

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Button(top, text="Import Backtest File…", style="Accent.TButton",
                   command=self.import_file).pack(side="left")
        self.file_lbl = ttk.Label(top, text="No file imported.", style="Muted.TLabel")
        self.file_lbl.pack(side="left", padx=10)

        summary_frame, self.tree = make_table(self, [
            ("metric", "Metric", 220, "w"),
            ("value", "Value", 200, "e"),
        ])
        summary_frame.pack(fill="both", expand=True, pady=4)

        section_label(self, "Analysis (needs deal-level data)")
        analysis_frame, self.analysis_tree = make_table(self, [
            ("metric", "Metric", 260, "w"),
            ("value", "Value", 420, "w"),
        ])
        analysis_frame.pack(fill="both", expand=True, pady=4)

        curve_lf = ttk.LabelFrame(self, text="Equity / Balance Curve (when available)", padding=4)
        curve_lf.pack(fill="both", expand=False, pady=6)
        self.canvas = tk.Canvas(curve_lf, height=160, background="#ffffff",
                                highlightthickness=1, highlightbackground="#d7dbe5")
        self.canvas.pack(fill="x")
        self._draw_placeholder()

        self.state.add_listener(self._auto_refresh)

    def _draw_placeholder(self) -> None:
        self.canvas.delete("all")
        self.canvas.create_text(200, 80, text="No balance curve available (import a report "
                                              "with a Balance column / Deals table)",
                                fill=C_MUTED, font=("Segoe UI", 9))

    def import_file(self) -> None:
        path = filedialog.askopenfilename(filetypes=[
            ("MT5 reports", "*.csv *.html *.htm *.txt *.log"),
            ("All files", "*.*")])
        if not path:
            return
        try:
            summary = parse_backtest_file(path)
        except Exception as exc:
            messagebox.showerror("Import failed", f"{os.path.basename(path)}:\n{exc}")
            return
        self.state.set_backtest(summary)
        self.file_lbl.configure(text=f"{summary.source_file} ({summary.source_format})")
        self.render()

    def _auto_refresh(self) -> None:
        if self.state.backtest_summary is not None:
            self.render()

    def render(self) -> None:
        s = self.state.backtest_summary
        a = self.state.backtest_analysis
        if s is None:
            return
        self.tree.delete(*self.tree.get_children())
        rows = [
            ("Net Profit ($)", fmt(s.net_profit)),
            ("Gross Profit ($)", fmt(s.gross_profit)),
            ("Gross Loss ($)", fmt(s.gross_loss)),
            ("Profit Factor", fmt(s.profit_factor)),
            ("Expected Payoff ($)", fmt(s.expected_payoff)),
            ("Max Drawdown ($)", fmt(s.max_drawdown)),
            ("Max Drawdown (%)", fmt(s.max_drawdown_percent)),
            ("Relative Drawdown (%)", fmt(s.relative_drawdown)),
            ("Trades", fmt(s.trades, 0)),
            ("Winning Trades", fmt(s.winning_trades, 0)),
            ("Losing Trades", fmt(s.losing_trades, 0)),
            ("Largest Profit ($)", fmt(s.largest_profit)),
            ("Largest Loss ($)", fmt(s.largest_loss)),
            ("Average Profit ($)", fmt(s.average_profit)),
            ("Average Loss ($)", fmt(s.average_loss)),
            ("Initial Deposit ($)", fmt(s.initial_deposit)),
        ]
        for name, value in rows:
            self.tree.insert("", "end", values=(name, value))

        self.analysis_tree.delete(*self.analysis_tree.get_children())
        if a is None:
            return
        arows = [
            ("Deal data available", "yes" if a.has_deal_data else "no"),
            ("Entry / Exit deals", f"{a.entry_deals} / {a.exit_deals}"),
            ("Max Grid Depth (total)", a.max_grid_depth_total),
            ("Max Grid Depth (buy / sell)", f"{a.max_grid_depth_buy} / {a.max_grid_depth_sell}"),
            ("Max Lot", fmt(a.max_lot, 2)),
            ("Average Lot", fmt(a.avg_lot, 2)),
            ("Total Volume", fmt(a.total_volume, 2)),
            ("Max Drawdown Episode",
             (f"{a.max_drawdown_episode.depth:.2f} ({a.max_drawdown_episode.depth_percent:.1f}%) "
              f"{a.max_drawdown_episode.duration_label}") if a.max_drawdown_episode else "N/A"),
            ("Longest Recovery",
             a.longest_recovery_episode.duration_label if a.longest_recovery_episode else "N/A"),
            ("Worst Losing Streak", f"{a.worst_losing_streak_deals} deals, "
                                    f"{fmt(a.worst_losing_streak_amount)} $"
             if a.worst_losing_streak_deals else "N/A"),
        ]
        for name, value in arows:
            self.analysis_tree.insert("", "end", values=(name, value))
        for note in a.notes:
            self.analysis_tree.insert("", "end", tags=("muted",), values=("Note", note))
        self._draw_curve(a.balance_curve)

    def _draw_curve(self, curve) -> None:
        self.canvas.delete("all")
        w = int(self.canvas.winfo_width()) or 800
        h = 160
        if not curve or len(curve) < 2:
            self.canvas.create_text(w / 2, h / 2,
                                    text="No balance curve available",
                                    fill=C_MUTED, font=("Segoe UI", 9))
            return
        lo, hi = min(curve), max(curve)
        span = (hi - lo) or 1.0
        n = len(curve)
        pts = []
        for i, v in enumerate(curve):
            x = 8 + i * (w - 16) / (n - 1)
            y = 8 + (1 - (v - lo) / span) * (h - 24)
            pts.extend([x, y])
        self.canvas.create_line(*pts, fill="#16213e", width=2)
        self.canvas.create_text(10, h - 8, anchor="w", text=f"min {lo:,.2f}",
                                fill=C_MUTED, font=("Segoe UI", 8))
        self.canvas.create_text(w - 10, h - 8, anchor="e", text=f"max {hi:,.2f} · {n} points",
                                fill=C_MUTED, font=("Segoe UI", 8))

    def on_show(self) -> None:
        if self.state.backtest_summary is not None:
            self.render()
