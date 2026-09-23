import sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import tkinter as tk
    from desktop import theme as th
    from desktop.app_state import AppState
    from desktop.app import MainWindow
    PAGES = MainWindow.PAGES

    root = tk.Tk()
    th.apply_theme(root)
    state = AppState()
    win = MainWindow(root, state)
    root.update_idletasks()
    # visit every page to force construction + on_show
    for name, _cls in PAGES:
        win.show(name)
        root.update_idletasks()
    print("pages OK:", [n for n, _ in PAGES])
    root.destroy()
    print("GUI SMOKE OK")
except Exception:
    import traceback
    traceback.print_exc()
    sys.exit(1)
