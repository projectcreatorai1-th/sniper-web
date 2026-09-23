"""Set Builder page (Module 8)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from core.setbuilder import (build_combinations, evaluate_set, apply_filters,
                             BuilderFilters, MAX_COMBINATIONS)
from desktop.theme import make_table, section_label


class SetBuilderPage(ttk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent)
        self.state = state
        self.results = []      # list[SetMetrics]
        ttk.Label(self, text="Set Builder", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="Generate parameter combinations and filter by YOUR constraints. "
                             "Sets are listed in generation order - no ranking.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(0, 6))

        top = ttk.Frame(self)
        top.pack(fill="x")
        grid = ttk.Frame(top)
        grid.pack(side="left", fill="x", expand=True)
        self.inputs = {}
        defaults = {
            "capital": "500",
            "grid_step": "5.0, 8.0",
            "base_lot": "0.1",
            "multiplier": "1.1",
            "basket_target": "1.68",
            "max_grid": "10, 20",
        }
        labels = {
            "capital": "Capital ($) list",
            "grid_step": "GridStep ($) list",
            "base_lot": "BaseLot list",
            "multiplier": "Multiplier list",
            "basket_target": "Basket target ($) list",
            "max_grid": "Max grid list",
        }
        for i, key in enumerate(defaults):
            row_i, col_i = divmod(i, 3)
            cell = ttk.Frame(grid)
            cell.grid(row=row_i, column=col_i, sticky="w", padx=6, pady=3)
            ttk.Label(cell, text=labels[key]).pack(side="left")
            var = tk.StringVar(value=defaults[key])
            ttk.Entry(cell, textvariable=var, width=22).pack(side="left", padx=4)
            self.inputs[key] = var

        filters = ttk.LabelFrame(top, text="Filters (blank = off)", padding=6)
        filters.pack(side="right", padx=8)
        self.filter_vars = {}
        for key, label in [
            ("max_dd_percent", "Max DD ≤ %"),
            ("max_grid", "Max grid ≤"),
            ("max_lot", "Max lot ≤"),
            ("max_margin_usage_percent", "Margin usage ≤ %"),
        ]:
            row = ttk.Frame(filters)
            row.pack(anchor="w", pady=2)
            ttk.Label(row, text=label, width=16, anchor="w").pack(side="left")
            var = tk.StringVar(value="")
            ttk.Entry(row, textvariable=var, width=8).pack(side="left")
            self.filter_vars[key] = var

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=4)
        ttk.Button(actions, text="Generate", style="Accent.TButton",
                   command=self.generate).pack(side="left")
        ttk.Button(actions, text="Save Selected Set…", command=self.save_selected).pack(
            side="left", padx=8)
        self.count_lbl = ttk.Label(actions, text="", style="Muted.TLabel")
        self.count_lbl.pack(side="left", padx=8)

        table_frame, self.tree = make_table(self, [
            ("idx", "#", 40, "e"),
            ("capital", "Capital", 70, "e"),
            ("step", "GridStep", 70, "e"),
            ("lot", "BaseLot", 60, "e"),
            ("mult", "Mult", 60, "e"),
            ("basket", "Basket $", 70, "e"),
            ("grid", "MaxGrid", 70, "e"),
            ("lots", "Total Lots", 80, "e"),
            ("dd", "Est. DD %", 80, "e"),
            ("margin", "Est. Margin $", 90, "e"),
            ("marginpct", "Margin %", 70, "e"),
            ("capacity", "Grid Capacity", 90, "e"),
            ("pass", "Filter", 70, "center"),
            ("reasons", "Filter reasons", 220, "w"),
        ])
        table_frame.pack(fill="both", expand=True, pady=4)
        self.tree.bind("<Double-1>", lambda e: self.save_selected())

    def _parse_list(self, text: str) -> list:
        vals = []
        for part in text.replace(";", ",").split(","):
            part = part.strip()
            if not part:
                continue
            vals.append(float(part))
        return vals

    def generate(self) -> None:
        st = self.state
        try:
            values = {k: self._parse_list(v.get()) for k, v in self.inputs.items()}
            if any(len(v) == 0 for v in values.values()):
                raise ValueError("every input list needs at least one value")
            combos = build_combinations(values)
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        filters = BuilderFilters()
        for key, var in self.filter_vars.items():
            raw = var.get().strip()
            if raw:
                try:
                    setattr(filters, key, float(raw))
                except ValueError:
                    messagebox.showerror("Invalid filter", f"{key}: must be a number")
                    return
        self.results = []
        self.tree.delete(*self.tree.get_children())
        shown = 0
        for i, combo in enumerate(combos):
            try:
                metrics = evaluate_set(
                    st.config, st.profile, st.account, st.rules(),
                    capital=combo["capital"], grid_step=combo["grid_step"],
                    base_lot=combo["base_lot"], multiplier=combo["multiplier"],
                    basket_target=combo["basket_target"],
                    max_grid=int(combo["max_grid"]))
            except ValueError as exc:
                messagebox.showerror("Evaluation failed", str(exc))
                return
            passed, reasons = apply_filters(metrics, filters)
            metrics_dict = metrics.to_dict()
            metrics_dict["_passed"] = passed
            metrics_dict["_reasons"] = "; ".join(reasons)
            self.results.append(metrics_dict)
            shown += 1
            if shown > MAX_COMBINATIONS:
                break
            tag = "ok" if passed else "warn"
            self.tree.insert("", "end", tags=(tag,), values=(
                i + 1, combo["capital"], combo["grid_step"], combo["base_lot"],
                combo["multiplier"], combo["basket_target"], int(combo["max_grid"]),
                f"{metrics.total_lots:.2f}", f"{metrics.estimated_dd_percent:.1f}",
                f"{metrics.estimated_margin:.0f}", f"{metrics.margin_usage_percent:.0f}",
                metrics.grid_capacity_levels, "PASS" if passed else "FAIL",
                "; ".join(reasons)))
        self.count_lbl.configure(
            text=f"{len(combos)} combinations generated · {shown} shown · model "
                 f"{st.rules().model_version}")

    def save_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a row", "Select a combination row first.")
            return
        item = self.tree.item(sel[0])
        idx = int(item["values"][0]) - 1
        m = self.results[idx]
        st = self.state
        from tkinter import simpledialog
        name = simpledialog.askstring("Save set", "Set name:")
        if not name:
            return
        cfg = st.config.copy()
        cfg.GridStepUSD = m["grid_step"]
        cfg.BaseLot = m["base_lot"]
        cfg.LotMultiplier = m["multiplier"]
        cfg.BasketCloseAllUSD = m["basket_target"]
        st.set_store.save_set(name, cfg, m["capital"], metrics=None)
        self.state.notify_changed()
        messagebox.showinfo("Saved", f"Set '{name}' saved to the Compare page.")

    def on_show(self) -> None:
        pass
