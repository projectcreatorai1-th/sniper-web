"""Set Comparison page (Module 9)."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from desktop.theme import make_table


class ComparePage(ttk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent)
        self.state = state
        ttk.Label(self, text="Compare", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="All saved sets in one table — data only, no ranking.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(0, 6))

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Button(top, text="Save Current Config as Set…",
                   command=self.save_current).pack(side="left")
        ttk.Button(top, text="Load Set to App", command=self.load_set).pack(side="left", padx=6)
        ttk.Button(top, text="Duplicate…", command=self.duplicate_set).pack(side="left")
        ttk.Button(top, text="Delete", command=self.delete_set).pack(side="left", padx=6)
        ttk.Button(top, text="Export Set…", command=self.export_set).pack(side="left")
        ttk.Button(top, text="Import Set…", command=self.import_set).pack(side="left", padx=6)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left")

        table_frame, self.tree = make_table(self, [
            ("name", "Set Name", 160, "w"),
            ("capital", "Capital", 70, "e"),
            ("step", "Grid Step", 70, "e"),
            ("lot", "Base Lot", 60, "e"),
            ("mult", "Multiplier", 70, "e"),
            ("basket", "Basket Target", 90, "e"),
            ("grid", "Max Grid", 70, "e"),
            ("lots", "Total Lots", 80, "e"),
            ("dd", "Est. DD %", 80, "e"),
            ("margin", "Margin $", 80, "e"),
            ("warnings", "Warnings", 340, "w"),
        ])
        table_frame.pack(fill="both", expand=True, pady=6)

    def _selected_name(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a set", "Select a set row first.")
            return None
        return str(self.tree.item(sel[0])["values"][0])

    def refresh(self) -> None:
        from core.setbuilder import evaluate_set
        st = self.state
        self.tree.delete(*self.tree.get_children())
        for name in st.set_store.names():
            data = st.set_store.get_set(name)
            if not data:
                continue
            from core.config import EAConfig
            from core.symbol_profile import SymbolProfile, AccountSettings
            cfg = EAConfig.from_dict(data.get("config", {}))
            capital = float(data.get("capital", 0) or 0)
            # evaluate with CURRENT symbol profile/account/model so the table
            # always reflects consistent math from the single calculation core
            try:
                m = evaluate_set(cfg, st.profile, st.account, st.rules(), capital,
                                 cfg.GridStepUSD, cfg.BaseLot, cfg.LotMultiplier,
                                 cfg.BasketCloseAllUSD,
                                 st.thresholds.max_simulated_grid_levels)
                lots, dd, margin = m.total_lots, m.estimated_dd_percent, m.estimated_margin
                warns = "; ".join(m.warnings[:3])
            except Exception as exc:
                lots, dd, margin = None, None, None
                warns = f"evaluation failed: {exc}"
            self.tree.insert("", "end", values=(
                name, capital, cfg.GridStepUSD, cfg.BaseLot, cfg.LotMultiplier,
                cfg.BasketCloseAllUSD, st.thresholds.max_simulated_grid_levels,
                f"{lots:.2f}" if lots is not None else "N/A",
                f"{dd:.1f}" if dd is not None else "N/A",
                f"{margin:.0f}" if margin is not None else "N/A",
                warns))

    def save_current(self) -> None:
        st = self.state
        name = simpledialog.askstring("Save set", "Set name:")
        if not name:
            return
        st.set_store.save_set(name, st.config, st.capital)
        st.notify_changed()
        self.refresh()

    def load_set(self) -> None:
        name = self._selected_name()
        if not name:
            return
        data = self.state.set_store.get_set(name)
        from core.config import EAConfig
        self.state.config = EAConfig.from_dict(data.get("config", {}))
        self.state.capital = float(data.get("capital", 0) or 0)
        self.state.notify_changed()
        messagebox.showinfo("Loaded", f"Set '{name}' loaded into the app.")

    def duplicate_set(self) -> None:
        name = self._selected_name()
        if not name:
            return
        new_name = simpledialog.askstring("Duplicate set", "New name:",
                                          initialvalue=name + " copy")
        if not new_name:
            return
        try:
            self.state.set_store.duplicate_set(name, new_name)
            self.refresh()
        except (KeyError, ValueError) as exc:
            messagebox.showerror("Duplicate failed", str(exc))

    def delete_set(self) -> None:
        name = self._selected_name()
        if not name:
            return
        if not messagebox.askyesno("Delete set", f"Delete set '{name}'?"):
            return
        try:
            self.state.set_store.delete_set(name)
            self.refresh()
        except KeyError as exc:
            messagebox.showerror("Delete failed", str(exc))

    def export_set(self) -> None:
        name = self._selected_name()
        if not name:
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            initialfile=name,
                                            filetypes=[("Set JSON", "*.json")])
        if not path:
            return
        try:
            self.state.set_store.export_set(name, path)
            messagebox.showinfo("Export", "Set exported.")
        except (KeyError, OSError) as exc:
            messagebox.showerror("Export failed", str(exc))

    def import_set(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Set JSON", "*.json")])
        if not path:
            return
        try:
            name = self.state.set_store.import_set(path)
            self.refresh()
            messagebox.showinfo("Import", f"Set '{name}' imported.")
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Import failed", str(exc))

    def on_show(self) -> None:
        self.refresh()
