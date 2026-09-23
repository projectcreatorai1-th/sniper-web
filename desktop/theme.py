"""Application-wide ttk theme and shared widgets."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# palette
C_SIDEBAR = "#16213e"
C_SIDEBAR_HOVER = "#1f2d55"
C_ACCENT = "#c9a227"
C_BG = "#f5f6fa"
C_CARD = "#ffffff"
C_TEXT = "#1a1a2e"
C_MUTED = "#6b7280"
C_WARN = "#b3261e"
C_OK = "#1a7a2e"
C_UNKNOWN = "#b8860b"
C_BORDER = "#d7dbe5"

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_SUB = ("Segoe UI", 9)
FONT_SMALL = ("Segoe UI", 8)
FONT_KPI = ("Segoe UI", 15, "bold")


def apply_theme(root: tk.Tk) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    root.configure(bg=C_BG)
    style.configure(".", background=C_BG, foreground=C_TEXT, font=FONT)
    style.configure("TFrame", background=C_BG)
    style.configure("Card.TFrame", background=C_CARD, relief="flat")
    style.configure("TLabel", background=C_BG, foreground=C_TEXT)
    style.configure("Card.TLabel", background=C_CARD, foreground=C_TEXT)
    style.configure("Muted.TLabel", background=C_BG, foreground=C_MUTED, font=FONT_SUB)
    style.configure("CardMuted.TLabel", background=C_CARD, foreground=C_MUTED, font=FONT_SMALL)
    style.configure("Title.TLabel", font=FONT_TITLE, background=C_BG)
    style.configure("Subtitle.TLabel", font=FONT_SUB, background=C_BG, foreground=C_MUTED)
    style.configure("Banner.TLabel", background="#fff3cd", foreground="#7a5c00",
                    font=FONT_SUB, padding=8)
    style.configure("TButton", padding=(10, 5))
    style.configure("Accent.TButton", background=C_ACCENT, foreground="#1a1a2e",
                    font=FONT_BOLD, padding=(12, 6))
    style.map("Accent.TButton",
              background=[("active", "#d9b53f"), ("pressed", "#b08f1d")])
    style.configure("TEntry", padding=3)
    style.configure("TCombobox", padding=3)
    style.configure("Treeview", rowheight=24, font=FONT)
    style.configure("Treeview.Heading", font=FONT_BOLD, background="#e8eaf2")
    style.configure("TLabelframe", background=C_BG, bordercolor=C_BORDER)
    style.configure("TLabelframe.Label", background=C_BG, font=FONT_BOLD)
    # status bar
    style.configure("Status.TLabel", background="#e8eaf2", foreground=C_MUTED, font=FONT_SMALL)


class MetricCard(ttk.Frame):
    def __init__(self, parent, title: str, value: str = "-", color: str = C_TEXT):
        super().__init__(parent, style="Card.TFrame", padding=10)
        self._title = ttk.Label(self, text=title, style="CardMuted.TLabel")
        self._title.pack(anchor="w")
        self._value = ttk.Label(self, text=value, style="Card.TLabel", font=FONT_KPI,
                                foreground=color)
        self._value.pack(anchor="w", pady=(2, 0))

    def set(self, value: str, color: str | None = None) -> None:
        self._value.configure(text=value, foreground=color or C_TEXT)


def make_table(parent, columns: list, stretch: bool = True):
    """columns: list of (id, heading, width, anchor). Returns tree widget."""
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=14)
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    for cid, heading, width, anchor in columns:
        tree.heading(cid, text=heading)
        tree.column(cid, width=width, anchor=anchor, stretch=stretch)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    tree.tag_configure("warn", foreground=C_WARN)
    tree.tag_configure("ok", foreground=C_OK)
    tree.tag_configure("unk", foreground=C_UNKNOWN)
    tree.tag_configure("muted", foreground=C_MUTED)
    return frame, tree


def fmt(v, decimals: int = 2, na: str = "N/A") -> str:
    if v is None:
        return na
    try:
        return f"{float(v):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(v)


def labeled_row(parent, label: str, widget) -> None:
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=2)
    ttk.Label(row, text=label, width=26, anchor="w").pack(side="left")
    widget.pack(side="left", fill="x", expand=True, padx=(4, 0))


def section_label(parent, text: str) -> ttk.Label:
    lbl = ttk.Label(parent, text=text, font=("Segoe UI", 11, "bold"))
    lbl.pack(anchor="w", pady=(10, 4))
    return lbl
