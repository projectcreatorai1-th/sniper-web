"""Main application window: sidebar navigation + toolbar + pages."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from desktop import theme as th
from desktop.app_state import AppState
from desktop.pages.dashboard import DashboardPage
from desktop.pages.ea_settings import EASettingsPage
from desktop.pages.grid_calculator import GridCalculatorPage
from desktop.pages.worst_case import WorstCasePage
from desktop.pages.risk import RiskPage
from desktop.pages.backtest import BacktestPage
from desktop.pages.set_builder import SetBuilderPage
from desktop.pages.compare import ComparePage
from desktop.pages.behavior import BehaviorPage
from desktop.pages.reports import ReportsPage
from desktop.pages.settings import SettingsPage

APP_TITLE = "SNIPER CashFlow Analyzer — V1.68 (Analyzer / Calculator / Simulator)"


class NavButton(tk.Label):
    def __init__(self, parent, text, command):
        super().__init__(parent, text=text, anchor="w", padx=16, pady=8,
                         bg=th.C_SIDEBAR, fg="#cfd3e0", font=("Segoe UI", 10),
                         cursor="hand2")
        self._command = command
        self.bind("<Button-1>", lambda e: command())
        self.bind("<Enter>", lambda e: self.configure(bg=th.C_SIDEBAR_HOVER)
                  if not self._active else None)
        self.bind("<Leave>", lambda e: self.configure(bg=th.C_SIDEBAR)
                  if not self._active else None)
        self._active = False

    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            self.configure(bg=th.C_ACCENT, fg="#1a1a2e",
                           font=("Segoe UI", 10, "bold"))
        else:
            self.configure(bg=th.C_SIDEBAR, fg="#cfd3e0",
                           font=("Segoe UI", 10))


class MainWindow:
    PAGES = [
        ("Dashboard", DashboardPage),
        ("EA Settings", EASettingsPage),
        ("Grid Calculator", GridCalculatorPage),
        ("Worst Case", WorstCasePage),
        ("Risk", RiskPage),
        ("Backtest", BacktestPage),
        ("Set Builder", SetBuilderPage),
        ("Compare", ComparePage),
        ("Behavior Verification", BehaviorPage),
        ("Reports", ReportsPage),
        ("Settings", SettingsPage),
    ]

    def __init__(self, root: tk.Tk, state: AppState):
        self.root = root
        self.state = state
        root.title(APP_TITLE)
        w, h = 1280, 800
        root.geometry(f"{w}x{h}")
        root.minsize(1024, 680)

        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(1, weight=1)

        # ---- header -----------------------------------------------------
        header = ttk.Frame(root, style="Card.TFrame", padding=(14, 8))
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(header, text="SNIPER CashFlow Analyzer", style="Card.TLabel",
                  font=("Segoe UI", 13, "bold")).pack(side="left")
        ttk.Label(header, text="  EA SUPERRICH SNIPER CASHFLOW V1.68 · read/analyze/test tool only",
                  style="CardMuted.TLabel").pack(side="left")
        for text, cmd in [
            ("New", self.new_project), ("Open…", self.open_project),
            ("Save", self.save_project), ("Import…", self.import_project),
            ("Export…", self.export_project), ("Reset", self.reset_app),
        ]:
            ttk.Button(header, text=text, command=cmd).pack(side="right", padx=3)

        # ---- sidebar ----------------------------------------------------
        sidebar = tk.Frame(root, bg=th.C_SIDEBAR, width=210)
        sidebar.grid(row=1, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        tk.Label(sidebar, text="ANALYZER", bg=th.C_SIDEBAR, fg=th.C_ACCENT,
                 font=("Segoe UI", 9, "bold"), anchor="w",
                 padx=16, pady=10).pack(fill="x")
        self._nav_buttons = {}
        for i, (name, _) in enumerate(self.PAGES):
            btn = NavButton(sidebar, name, command=lambda n=name: self.show(n))
            btn.pack(fill="x")
            self._nav_buttons[name] = btn
        self.model_lbl = tk.Label(sidebar, text="", bg=th.C_SIDEBAR, fg="#8b93b0",
                                  font=("Segoe UI", 8), anchor="w",
                                  padx=16, pady=8, wraplength=180, justify="left")
        self.model_lbl.pack(side="bottom", fill="x")

        # ---- content ------------------------------------------------------
        self.content = ttk.Frame(root, padding=(14, 10))
        self.content.grid(row=1, column=1, sticky="nsew")
        self.pages = {}
        for name, cls in self.PAGES:
            page = cls(self.content, self.state)
            self.pages[name] = page
        self.current_page = None

        # ---- status bar ------------------------------------------------------
        self.status = ttk.Label(root, style="Status.TLabel", anchor="w", padding=(10, 4),
                                text="Ready · Simulation Model — not verified internal EA formula")
        self.status.grid(row=2, column=0, columnspan=2, sticky="ew")

        self.state.add_listener(self._on_state_changed)
        self.show("Dashboard")

    # ------------------------------------------------------------------
    def show(self, name: str) -> None:
        for n, btn in self._nav_buttons.items():
            btn.set_active(n == name)
        if self.current_page:
            self.pages[self.current_page].pack_forget()
        self.current_page = name
        page = self.pages[name]
        page.pack(fill="both", expand=True)
        try:
            page.on_show()
        except Exception:
            pass

    def _on_state_changed(self) -> None:
        rules = self.state.rules()
        self.model_lbl.configure(
            text=f"Model {rules.model_version}\nlot={rules.lot_formula}\n"
                 f"grid={rules.grid_spacing_rule}\nbasket={rules.basket_scope}")
        self.status.configure(text=(
            ("● unsaved changes" if self.state.dirty else "○ saved") +
            f" · model {rules.model_version} · symbol {self.state.profile.name}"))

    # ---- toolbar actions -------------------------------------------------
    def new_project(self) -> None:
        if self.state.dirty and not messagebox.askyesno(
                "New project", "Discard unsaved changes?"):
            return
        self.state.reset()
        self.status.configure(text="New project · default configuration loaded")

    def open_project(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Project JSON", "*.json")])
        if not path:
            return
        from core.report import load_project
        try:
            data = load_project(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Open failed", str(exc))
            return
        self.state.load_project_data(data)
        self.state.project_path = path
        self.state.dirty = False
        self._on_state_changed()
        messagebox.showinfo("Open", f"Project loaded:\n{os.path.basename(path)}")

    def save_project(self) -> None:
        from core.report import save_project
        path = self.state.project_path
        if not path:
            path = filedialog.asksaveasfilename(defaultextension=".json",
                                                initialfile="sniper_project.json",
                                                filetypes=[("Project JSON", "*.json")])
            if not path:
                return
        save_project(path, self.state.to_project_data())
        self.state.project_path = path
        self.state.dirty = False
        self._on_state_changed()
        self.status.configure(text=f"Saved {os.path.basename(path)}")

    def import_project(self) -> None:
        self.open_project()

    def export_project(self) -> None:
        from core.report import ProjectData, save_project
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            initialfile="sniper_project_export.json",
                                            filetypes=[("Project JSON", "*.json")])
        if not path:
            return
        save_project(path, self.state.to_project_data())
        messagebox.showinfo("Export", f"Project exported to {os.path.basename(path)}")

    def reset_app(self) -> None:
        if not messagebox.askyesno("Reset", "Reset ALL app state to defaults "
                                            "(config, profile, thresholds, backtest)?"):
            return
        self.state.reset()


def main() -> None:
    root = tk.Tk()
    th.apply_theme(root)
    state = AppState()
    MainWindow(root, state)
    root.mainloop()


if __name__ == "__main__":
    main()
