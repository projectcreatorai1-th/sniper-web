"""Grid Calculator page (Module 2) + Basket/Partial Close panel (Module 4)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from core.basket import simulate_basket
from core.grid import build_grid_table
from desktop.theme import make_table, section_label, fmt


class GridCalculatorPage(ttk.Frame):
    LEVEL_CHOICES = ["5", "10", "20", "30", "50", "100"]

    def __init__(self, parent, state):
        super().__init__(parent)
        self.state = state
        ttk.Label(self, text="Grid Calculator", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="Simulation Model — not verified internal EA formula",
                  style="Banner.TLabel").pack(fill="x", pady=(4, 8))

        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=2)
        ttk.Label(controls, text="Side:").pack(side="left")
        self.side_var = tk.StringVar(value="BUY")
        ttk.Combobox(controls, textvariable=self.side_var, width=8, state="readonly",
                     values=["BUY", "SELL"]).pack(side="left", padx=(4, 12))
        ttk.Label(controls, text="Grid Levels:").pack(side="left")
        self.levels_var = tk.StringVar(value="10")
        ttk.Combobox(controls, textvariable=self.levels_var, width=6, state="readonly",
                     values=self.LEVEL_CHOICES).pack(side="left", padx=(4, 2))
        ttk.Label(controls, text="Custom:").pack(side="left")
        self.custom_var = tk.StringVar(value="")
        ttk.Entry(controls, textvariable=self.custom_var, width=6).pack(side="left", padx=(4, 12))
        ttk.Label(controls, text="Start Price:").pack(side="left")
        self.start_var = tk.StringVar(value="")
        ttk.Entry(controls, textvariable=self.start_var, width=10).pack(side="left", padx=(4, 12))
        ttk.Label(controls, text="Basket depth (Module 4):").pack(side="left")
        self.basket_depth_var = tk.StringVar(value="5")
        ttk.Combobox(controls, textvariable=self.basket_depth_var, width=6,
                     state="readonly", values=["1", "3", "5", "10", "20"]).pack(side="left", padx=4)
        ttk.Button(controls, text="Calculate", command=self.calculate,
                   style="Accent.TButton").pack(side="left", padx=12)

        table_frame, self.tree = make_table(self, [
            ("level", "Level", 50, "e"),
            ("distance", "Price Distance ($)", 120, "e"),
            ("entry", "Entry Price", 100, "e"),
            ("lot", "Lot", 70, "e"),
            ("cumlot", "Cumulative Lot", 110, "e"),
            ("exposure", "Est. Exposure ($)", 120, "e"),
            ("floating", "Est. Floating P/L ($)", 130, "e"),
            ("margin", "Margin Estimate ($)", 130, "e"),
            ("avg", "Avg Entry", 100, "e"),
        ])
        table_frame.pack(fill="both", expand=True, pady=6)

        self.summary_lbl = ttk.Label(self, text="", style="Muted.TLabel")
        self.summary_lbl.pack(anchor="w")

        # ---- Basket / Partial close panel (Module 4) -----------------------
        basket_lf = ttk.LabelFrame(self, text="Basket / Partial Close Simulation (Module 4)", padding=8)
        basket_lf.pack(fill="x", pady=8)
        self.basket_lbl = ttk.Label(basket_lf, text="Press Calculate to evaluate the basket.",
                                    wraplength=1000, justify="left")
        self.basket_lbl.pack(anchor="w")

    # ------------------------------------------------------------------
    def calculate(self) -> None:
        st = self.state
        try:
            levels = int(self.custom_var.get() or self.levels_var.get())
            if levels < 1 or levels > 500:
                raise ValueError("levels must be 1..500")
            start = float(self.start_var.get()) if self.start_var.get().strip() else None
            table = build_grid_table(st.config, st.profile, st.account, st.rules(),
                                     levels, self.side_var.get(), start)
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return

        self.tree.delete(*self.tree.get_children())
        for r in table.rows:
            self.tree.insert("", "end", values=(
                r.level, f"{r.distance_from_start:.1f}", f"{r.entry_price:.2f}",
                f"{r.lot:.2f}", f"{r.cumulative_lot:.2f}", fmt(r.exposure),
                fmt(r.floating_pl_at_open), fmt(r.margin),
                f"{r.avg_entry:.2f}" if r.avg_entry else "N/A"))
        self.summary_lbl.configure(text=(
            f"Total lots {fmt(table.total_lot, 2)} · Exposure at start price {fmt(table.total_exposure)} · "
            f"Margin at start price {fmt(table.total_margin)} · Avg entry "
            f"{fmt(table.avg_entry, 2) if table.avg_entry else 'N/A'} · Model: {st.rules().model_version}"))

        try:
            depth = int(self.basket_depth_var.get())
            sim = simulate_basket(st.config, st.profile, st.rules(),
                                  self.side_var.get(), depth, start)
            lines = [
                f"Basket at depth {depth}: total lots {sim.total_lots} · avg entry "
                f"{sim.avg_entry and round(sim.avg_entry, 2)} · current basket P/L "
                f"{fmt(sim.current_basket_pl)} (price {sim.current_price})",
                f"Partial trigger {sim.partial_trigger if sim.partial_trigger is not None else 'off'}"
                f" → closes {sim.partial_close_volume} lots, realizes ≈ {fmt(sim.partial_realized_pl)}; "
                f"remaining {sim.partial_remaining_lots} lots. Pending: {'yes' if sim.partial_pending else 'no'}.",
                f"Basket target {sim.basket_target if sim.basket_target is not None else 'off'} → "
                f"needs price move {fmt(sim.price_move_to_target, 3)} from current (partial trigger move "
                f"{fmt(sim.price_move_to_partial, 3)}).",
                "Note: basket/partial calculations are SIMULATION - internal EX5 logic not confirmed "
                "(PARTIAL_CLOSE_ASSUMPTION_001, BASKET_SCOPE_ASSUMPTION_001).",
            ]
            self.basket_lbl.configure(text="\n".join(lines))
        except Exception as exc:
            self.basket_lbl.configure(text=f"Basket simulation failed: {exc}")

    def on_show(self) -> None:
        if not self.start_var.get().strip():
            self.start_var.set(str(self.state.profile.reference_price))
