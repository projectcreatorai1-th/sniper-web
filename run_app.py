"""SNIPER CashFlow Analyzer — entry point.

Run:  python run_app.py   (or double-click the desktop shortcut, which uses
pythonw.exe so no console window appears)
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _fatal_dialog(exc_text: str) -> None:
    """pythonw.exe has no console - surface startup crashes in a dialog."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("SNIPER CashFlow Analyzer — startup error", exc_text)
        root.destroy()
    except Exception:
        pass


def main() -> None:
    from desktop.app import MainWindow
    from desktop.app_state import AppState
    from desktop import theme as th
    import tkinter as tk

    root = tk.Tk()
    th.apply_theme(root)
    state = AppState()
    MainWindow(root, state)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _fatal_dialog(traceback.format_exc())
        sys.exit(1)
