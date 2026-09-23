"""EA Settings page (Module 1): all 27 parameters, presets, validation,
save/load/export/import of the versioned config."""
from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.config import EAConfig, builtin_presets
from core.validation import validate_config, worst_severity, ERROR
from desktop.theme import make_table, section_label, C_WARN, C_OK, C_UNKNOWN


class EASettingsPage(ttk.Frame):
    def __init__(self, parent, state):
        super().__init__(parent)
        self.state = state
        self._widgets = {}      # key -> (widget, kind)

        ttk.Label(self, text="EA Settings", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="All 27 parameters of SNIPER CashFlow V1.68 "
                             "(baseline from the seller's PDF manual)",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(0, 6))

        top = ttk.Frame(self)
        top.pack(fill="x", pady=4)
        ttk.Label(top, text="Preset:").pack(side="left")
        self.preset_var = tk.StringVar(value=builtin_presets().keys().__iter__().__next__())
        self.preset_cb = ttk.Combobox(top, textvariable=self.preset_var, state="readonly",
                                      width=32, values=list(builtin_presets().keys()))
        self.preset_cb.pack(side="left", padx=6)
        ttk.Button(top, text="Apply Preset", command=self.apply_preset).pack(side="left")
        ttk.Label(top, text="Capital ($):", style="Muted.TLabel").pack(side="left", padx=(16, 4))
        self.capital_var = tk.StringVar(value="500.0")
        ttk.Entry(top, textvariable=self.capital_var, width=10).pack(side="left")
        ttk.Button(top, text="Validate", command=self.run_validation).pack(side="left", padx=12)
        ttk.Button(top, text="Reset to Default", command=self.reset_default).pack(side="left", padx=4)
        ttk.Button(top, text="Export JSON", command=self.export_json).pack(side="left", padx=4)
        ttk.Button(top, text="Import JSON", command=self.import_json).pack(side="left", padx=4)
        ttk.Button(top, text="Save Config", command=self.save_config).pack(side="left", padx=4)
        ttk.Button(top, text="Load Config", command=self.load_config).pack(side="left", padx=4)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, pady=6)
        self.param_canvas_wrapper = ttk.Frame(body)
        self.param_canvas_wrapper.pack(side="left", fill="both", expand=True)
        canvas = tk.Canvas(self.param_canvas_wrapper, highlightthickness=0, bg="#f5f6fa")
        vsb = ttk.Scrollbar(self.param_canvas_wrapper, orient="vertical", command=canvas.yview)
        self.param_inner = ttk.Frame(canvas)
        self.param_inner.bind("<Configure>",
                              lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.param_inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * int(e.delta / 120), "units"))
        self._canvas = canvas

        right = ttk.Frame(body, width=420)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)
        section_label(right, "Validation")
        self.valid_box = tk.Text(right, height=14, wrap="word", relief="flat",
                                 background="#ffffff", highlightthickness=1,
                                 highlightbackground="#d7dbe5", font=("Segoe UI", 9))
        self.valid_box.pack(fill="x")
        self.valid_box.tag_configure("warn", foreground=C_WARN)
        self.valid_box.tag_configure("ok", foreground=C_OK)
        self.valid_box.tag_configure("unk", foreground=C_UNKNOWN)
        self.valid_box.insert("end", "Press Validate to check the configuration.\n")

        self._build_param_form()
        self.load_from_state()

    # ------------------------------------------------------------------
    def _build_param_form(self) -> None:
        meta = EAConfig.parameter_meta()
        current_group = None
        group_frame = None
        for m in meta:
            if m["group"] != current_group:
                current_group = m["group"]
                gf = ttk.LabelFrame(self.param_inner, text=current_group, padding=8)
                gf.pack(fill="x", pady=6, padx=6)
                group_frame = gf
            row = ttk.Frame(group_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=m["label"], width=42, anchor="w").pack(side="left")
            kind = m["kind"]
            var = tk.StringVar()
            if kind == "bool":
                w = ttk.Combobox(row, textvariable=var, width=8, state="readonly",
                                 values=["true", "false"])
            elif kind == "time":
                w = ttk.Entry(row, textvariable=var, width=10)
            elif kind == "str":
                w = ttk.Entry(row, textvariable=var, width=24)
            else:
                w = ttk.Entry(row, textvariable=var, width=12)
            w.pack(side="left")
            self._widgets[m["key"]] = (w, kind, var)

    def load_from_state(self) -> None:
        cfg = self.state.config
        for key, (w, kind, var) in self._widgets.items():
            val = getattr(cfg, key)
            if kind == "bool":
                var.set("true" if val else "false")
            else:
                var.set(str(val))
        self.capital_var.set(str(self.state.capital))

    def apply_to_state(self) -> bool:
        cfg = self.state.config
        for key, (w, kind, var) in self._widgets.items():
            raw = var.get().strip()
            try:
                if kind == "bool":
                    setattr(cfg, key, raw.lower() in ("1", "true", "yes", "on"))
                elif kind == "float":
                    if raw:
                        setattr(cfg, key, float(raw))
                else:
                    setattr(cfg, key, raw)
            except ValueError:
                messagebox.showerror("Invalid value",
                                     f"{key}: '{raw}' is not a valid {kind}")
                return False
        try:
            self.state.capital = max(0.0, float(self.capital_var.get() or 0))
        except ValueError:
            messagebox.showerror("Invalid value", "Capital must be a number")
            return False
        self.state.notify_changed()
        return True

    def apply_preset(self) -> None:
        presets = builtin_presets()
        cfg = presets.get(self.preset_var.get())
        if cfg is None:
            return
        self.state.config = cfg.copy()
        self.load_from_state()
        self.state.notify_changed()
        messagebox.showinfo("Preset applied",
                            f"Applied preset: {self.preset_var.get()}\n"
                            "(values from the seller's documentation - not a "
                            "safety recommendation)")

    def reset_default(self) -> None:
        self.state.config = EAConfig()
        self.load_from_state()
        self.state.notify_changed()

    def run_validation(self) -> None:
        if not self.apply_to_state():
            return
        issues = validate_config(self.state.config, self.state.profile,
                                 self.state.account, self.state.capital)
        self.valid_box.configure(state="normal")
        self.valid_box.delete("1.0", "end")
        if not issues:
            self.valid_box.insert("end", "No issues found.\n", "ok")
        for i in issues:
            tag = "warn" if i.severity == ERROR else ("unk" if i.severity == "WARNING" else "ok")
            self.valid_box.insert("end", f"[{i.severity}] {i.code}\n    {i.message}\n", tag)
            if i.assumption:
                self.valid_box.insert("end", f"    assumption: {i.assumption}\n", "unk")
        self.valid_box.configure(state="disabled")

    def export_json(self) -> None:
        if not self.apply_to_state():
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.state.config.to_dict(), f, ensure_ascii=False, indent=2)
        messagebox.showinfo("Export", f"Config exported to {os.path.basename(path)}")

    def import_json(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.state.config = EAConfig.from_dict(data)
            self.load_from_state()
            self.state.notify_changed()
            messagebox.showinfo("Import", "Config imported.")
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc))

    def save_config(self) -> None:
        if not self.apply_to_state():
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("EA config JSON", "*.json")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.state.config.to_dict(), f, ensure_ascii=False, indent=2)

    def load_config(self) -> None:
        self.import_json()

    def on_show(self) -> None:
        self.load_from_state()
