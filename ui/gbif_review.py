import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from datetime import datetime
import os
import getpass
import tkinter.font as tkFont
from typing import List, Dict, Any, Optional
from config import sc
from ui.state import app_bus, DATABASE_UPDATED

FONT_UI = ("sans-serif", 10)
FONT_UI_BOLD = ("sans-serif", 10, "bold")
FONT_UI_LG = ("sans-serif", 12, "bold")
FONT_UI_XL = ("sans-serif", 16, "bold")
FONT_MONO = ("Consolas", 10)
FONT_MONO_SM = ("Consolas", 8)

_fonts_initialized = False
def init_fonts():
    global _fonts_initialized, FONT_UI, FONT_UI_BOLD, FONT_UI_LG, FONT_UI_XL, FONT_MONO, FONT_MONO_SM
    if _fonts_initialized:
        return
    families = tkFont.families()
    ui_family = "Hanken Grotesk" if "Hanken Grotesk" in families else "Helvetica" if "Helvetica" in families else "Segoe UI" if "Segoe UI" in families else "sans-serif"
    mono_family = "JetBrains Mono" if "JetBrains Mono" in families else "Consolas" if "Consolas" in families else "Courier New"

    FONT_UI = (ui_family, sc(10))
    FONT_UI_BOLD = (ui_family, sc(10), "bold")
    FONT_UI_LG = (ui_family, sc(12), "bold")
    FONT_UI_XL = (ui_family, sc(16), "bold")
    FONT_MONO = (mono_family, sc(10))
    FONT_MONO_SM = (mono_family, sc(8))
    _fonts_initialized = True

COLORS = {
    "bg": "#fbfaf8",
    "surface": "#ffffff",
    "surface_dim": "#e9ece5",
    "border": "#d1d1d1",
    "text": "#2c302e",
    "text_muted": "#444748",
    "primary": "#2c302e",
    "on_primary": "#ffffff",
    "error_bg": "#fef2f2",
    "error_border": "#c93a40",
    "error_text": "#c93a40",
    "success_bg": "#f0fdf4",
    "success_border": "#3a7d44",
    "success_text": "#2b8a3e",
    "warning": "#f59e0b",
    "chip_tag": "#757d77"
}


class GBIFReviewDialog(tk.Toplevel):
    """
    Gold-standard Taxonomic Reconciliation & Review dialog modeled after HistoricalConflictResolverWindow.
    Provides clear before/after comparison chips, selective field application, and full audit logging.
    """
    def __init__(self, parent, app_state, diff_results: List[Dict[str, Any]], on_applied_callback=None):
        super().__init__(parent)
        init_fonts()
        self.parent = parent
        self.app_state = app_state
        self.diff_results = diff_results
        self.on_applied_callback = on_applied_callback

        self.title("GBIF Taxonomic Review & Reconciliation")
        self.configure(bg=COLORS["bg"])

        import utils
        utils.center_and_fit_toplevel(self, sc(1100), sc(700))
        self.minsize(sc(750), sc(500))

        # Flatten changes & state
        self.item_cards = {}
        self.specimen_frames = {}
        self.field_vars = {}  # (oid, field_name) -> BooleanVar

        self._build_ui()
        self.transient(parent)
        self.grab_set()

    def _build_ui(self):
        # 1. Header Bar
        header = tk.Frame(self, bg=COLORS["surface"], height=sc(48))
        header.pack(fill="x", side="top")
        tk.Frame(header, bg=COLORS["border"], height=sc(1)).pack(fill="x", side="bottom")

        tk.Label(
            header,
            text="GBIF_TAXONOMIC_REVIEW_AND_RECONCILIATION",
            font=FONT_UI_LG,
            fg=COLORS["primary"],
            bg=COLORS["surface"]
        ).pack(side="left", padx=sc(16), pady=sc(12))

        # 2. Main content area (Split View: Left Sidebar Directory + Right Cards)
        main_area = tk.Frame(self, bg=COLORS["bg"])
        main_area.pack(fill="both", expand=True)

        # --- Left Sidebar (Specimen Directory) ---
        sidebar = tk.Frame(main_area, width=sc(280), bg=COLORS["surface_dim"])
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Frame(sidebar, bg=COLORS["border"], width=sc(1)).pack(side="right", fill="y")

        dir_header = tk.Frame(sidebar, bg=COLORS["border"], height=sc(40))
        dir_header.pack(fill="x")
        tk.Label(
            dir_header,
            text="SPECIMEN_DIRECTORY",
            font=FONT_MONO_SM,
            fg=COLORS["text_muted"],
            bg=COLORS["border"]
        ).pack(side="left", padx=sc(12), pady=sc(12))

        self.dir_canvas = tk.Canvas(sidebar, bg=COLORS["surface_dim"], highlightthickness=0)
        dir_scrollbar = ttk.Scrollbar(sidebar, orient="vertical", command=self.dir_canvas.yview)
        self.dir_list = tk.Frame(self.dir_canvas, bg=COLORS["surface_dim"])

        self.dir_list.bind(
            "<Configure>",
            lambda e: self.dir_canvas.configure(scrollregion=self.dir_canvas.bbox("all")) if e.widget == self.dir_list else None
        )
        dir_canvas_window = self.dir_canvas.create_window((0, 0), window=self.dir_list, anchor="nw")
        self.dir_canvas.configure(yscrollcommand=dir_scrollbar.set)
        self.dir_canvas.bind("<Configure>", lambda e: self.dir_canvas.itemconfig(dir_canvas_window, width=e.width))

        self.dir_canvas.pack(side="left", fill="both", expand=True)
        dir_scrollbar.pack(side="right", fill="y")
        self.dir_canvas.bind("<MouseWheel>", self._on_dir_mousewheel)

        # --- Right Main Area (Scrollable Cards) ---
        right_area = tk.Frame(main_area, bg=COLORS["bg"])
        right_area.pack(side="left", fill="both", expand=True)

        # Context Header
        ctx_header = tk.Frame(right_area, bg=COLORS["surface"], height=sc(70))
        ctx_header.pack(fill="x")
        tk.Frame(ctx_header, bg=COLORS["border"], height=sc(1)).pack(side="bottom", fill="x")

        total_changes = sum(len(d.get("changes", [])) for d in self.diff_results)
        tk.Label(
            ctx_header,
            text=f"REVIEW: {len(self.diff_results)} SPECIMENS WITH TAXONOMIC UPDATES",
            font=FONT_UI_XL,
            fg=COLORS["primary"],
            bg=COLORS["surface"]
        ).pack(anchor="w", padx=sc(24), pady=(sc(12), sc(2)))

        tk.Label(
            ctx_header,
            text=f"Detected {total_changes} suggested field updates from GBIF. Check the boxes for each change you wish to apply.",
            font=FONT_UI,
            fg=COLORS["text_muted"],
            bg=COLORS["surface"]
        ).pack(anchor="w", padx=sc(24), pady=(0, sc(12)))

        # Scrollable Canvas for Specimen Cards
        self.canvas = tk.Canvas(right_area, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(right_area, orient="vertical", command=self.canvas.yview)
        self.cards_frame = tk.Frame(self.canvas, bg=COLORS["bg"], padx=sc(20), pady=sc(16))

        self.cards_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")) if e.widget == self.cards_frame else None
        )
        canvas_window = self.canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        self.canvas.bind("<Configure>", lambda e, cw=canvas_window: self.canvas.itemconfig(cw, width=e.width))

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.bind("<MouseWheel>", self._on_main_mousewheel)

        # Populate Directory & Cards
        self._populate_all()

        # 3. Bottom Action Bar
        bottom_bar = tk.Frame(self, bg=COLORS["surface"], height=sc(56))
        bottom_bar.pack(fill="x", side="bottom")
        tk.Frame(bottom_bar, bg=COLORS["border"], height=sc(1)).pack(side="top", fill="x")

        b_content = tk.Frame(bottom_bar, bg=COLORS["surface"], padx=sc(16), pady=sc(10))
        b_content.pack(fill="both", expand=True)

        # Quick selection buttons
        sel_all_btn = tk.Button(
            b_content, text="Select All", command=self._select_all,
            font=FONT_UI_BOLD, bg=COLORS["surface_dim"], fg=COLORS["text"],
            relief="flat", bd=0, cursor="hand2", padx=sc(12), pady=sc(4)
        )
        sel_all_btn.pack(side="left", padx=(0, sc(8)))

        desel_all_btn = tk.Button(
            b_content, text="Deselect All", command=self._deselect_all,
            font=FONT_UI_BOLD, bg=COLORS["surface_dim"], fg=COLORS["text"],
            relief="flat", bd=0, cursor="hand2", padx=sc(12), pady=sc(4)
        )
        desel_all_btn.pack(side="left")

        # Summary label
        self.summary_label = tk.Label(
            b_content,
            text="",
            font=FONT_UI_BOLD,
            fg=COLORS["text_muted"],
            bg=COLORS["surface"]
        )
        self.summary_label.pack(side="left", padx=sc(24))

        # Action Buttons
        cancel_btn = tk.Button(
            b_content, text="Cancel", command=self.destroy,
            font=FONT_UI_BOLD, bg=COLORS["surface_dim"], fg=COLORS["text"],
            relief="flat", bd=0, cursor="hand2", padx=sc(16), pady=sc(6)
        )
        cancel_btn.pack(side="right", padx=(sc(8), 0))

        self.apply_btn = tk.Button(
            b_content, text="Apply Selected Updates", command=self._apply_selected,
            font=FONT_UI_BOLD, bg=COLORS["success_border"], fg=COLORS["on_primary"],
            relief="flat", bd=0, cursor="hand2", padx=sc(20), pady=sc(6)
        )
        self.apply_btn.pack(side="right")

        self._update_summary()

    def _populate_all(self):
        for diff in self.diff_results:
            oid = str(diff.get("oid", ""))
            status = diff.get("status", "ACCEPTED")
            changes = diff.get("changes", [])

            # --- 1. Left Sidebar Entry ---
            f_frame = tk.Frame(self.dir_list, bg=COLORS["surface_dim"], cursor="hand2", padx=sc(8), pady=sc(6))
            f_frame.pack(fill="x", pady=sc(1))

            tag_color = COLORS["warning"] if status == "SYNONYM" else COLORS["success_border"]
            tag_text = status.upper()

            tk.Label(f_frame, text=f"#{oid}", font=FONT_MONO, fg=COLORS["text"], bg=COLORS["surface_dim"]).pack(side="left")
            tk.Label(f_frame, text=f"({len(changes)} chg)", font=FONT_MONO_SM, fg=COLORS["text_muted"], bg=COLORS["surface_dim"]).pack(side="left", padx=sc(4))
            tk.Label(f_frame, text=tag_text, font=FONT_MONO_SM, fg=tag_color, bg=COLORS["surface_dim"]).pack(side="right")

            def _scroll_to(target_oid=oid):
                if target_oid in self.item_cards:
                    card = self.item_cards[target_oid]
                    y = card.winfo_y()
                    if self.cards_frame.winfo_height() > 0:
                        self.canvas.yview_moveto(max(0, (y - 20) / self.cards_frame.winfo_height()))

            f_frame.bind("<Button-1>", lambda e, f=_scroll_to: f())
            for child in f_frame.winfo_children():
                child.bind("<Button-1>", lambda e, f=_scroll_to: f())

            self.specimen_frames[oid] = f_frame

            # --- 2. Right Card Frame ---
            card = tk.Frame(
                self.cards_frame,
                bg=COLORS["surface"],
                highlightbackground=COLORS["border"],
                highlightthickness=1,
                padx=sc(16),
                pady=sc(14)
            )
            card.pack(fill="x", pady=(0, sc(14)))
            self.item_cards[oid] = card

            # Card Header
            c_header = tk.Frame(card, bg=COLORS["surface"])
            c_header.pack(fill="x", pady=(0, sc(10)))

            tk.Label(
                c_header,
                text=f"SPECIMEN #{oid}",
                font=FONT_UI_BOLD,
                fg=COLORS["primary"],
                bg=COLORS["surface"]
            ).pack(side="left")

            match_type = diff.get("match_type", "MATCH")
            badge_bg = COLORS["warning"] if status == "SYNONYM" else COLORS["surface_dim"]
            badge_fg = "#000000" if status == "SYNONYM" else COLORS["text_muted"]
            tk.Label(
                c_header,
                text=f"[{status} | {match_type}]",
                font=FONT_MONO_SM,
                fg=badge_fg,
                bg=badge_bg,
                padx=sc(6),
                pady=sc(2)
            ).pack(side="right")

            # Field Rows
            for chg in changes:
                field = chg["field"]
                old_val = str(chg["old"])
                new_val = str(chg["new"])

                var = tk.BooleanVar(value=True)
                self.field_vars[(oid, field)] = (var, chg)

                row_frame = tk.Frame(card, bg=COLORS["surface"], pady=sc(4))
                row_frame.pack(fill="x", pady=(0, sc(6)))

                # Top line: Checkbox with field name
                chk = tk.Checkbutton(
                    row_frame,
                    text=field,
                    variable=var,
                    font=FONT_UI_BOLD,
                    fg=COLORS["text"],
                    bg=COLORS["surface"],
                    activebackground=COLORS["surface"],
                    activeforeground=COLORS["primary"],
                    selectcolor=COLORS["surface"],
                    cursor="hand2",
                    command=self._update_summary
                )
                chk.pack(anchor="w", pady=(0, sc(4)))

                # Chips Grid
                grid_frame = tk.Frame(row_frame, bg=COLORS["surface"], padx=sc(20))
                grid_frame.pack(fill="x")
                grid_frame.columnconfigure(0, weight=1)
                grid_frame.columnconfigure(1, weight=1)

                # Database (Old) Chip
                db_chip = tk.Frame(
                    grid_frame,
                    bg=COLORS["error_bg"],
                    highlightbackground=COLORS["error_border"],
                    highlightthickness=1,
                    padx=sc(10),
                    pady=sc(6)
                )
                db_chip.grid(row=0, column=0, sticky="ew", padx=(0, sc(6)))

                tk.Label(
                    db_chip,
                    text="YOUR DATABASE VALUE",
                    font=FONT_MONO_SM,
                    fg=COLORS["error_text"],
                    bg=COLORS["error_bg"]
                ).pack(anchor="w")

                tk.Label(
                    db_chip,
                    text=old_val or "(Empty)",
                    font=FONT_MONO,
                    fg=COLORS["text"] if old_val else COLORS["text_muted"],
                    bg=COLORS["error_bg"]
                ).pack(anchor="w")

                # GBIF (New) Chip
                gbif_chip = tk.Frame(
                    grid_frame,
                    bg=COLORS["success_bg"],
                    highlightbackground=COLORS["success_border"],
                    highlightthickness=1,
                    padx=sc(10),
                    pady=sc(6)
                )
                gbif_chip.grid(row=0, column=1, sticky="ew", padx=(sc(6), 0))

                tk.Label(
                    gbif_chip,
                    text="GBIF SUGGESTED VALUE",
                    font=FONT_MONO_SM,
                    fg=COLORS["success_text"],
                    bg=COLORS["success_bg"]
                ).pack(anchor="w")

                tk.Label(
                    gbif_chip,
                    text=new_val,
                    font=FONT_MONO,
                    fg=COLORS["success_text"],
                    bg=COLORS["success_bg"]
                ).pack(anchor="w")

    def _on_dir_mousewheel(self, event):
        if event.delta:
            self.dir_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_main_mousewheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _select_all(self):
        for var, _ in self.field_vars.values():
            var.set(True)
        self._update_summary()

    def _deselect_all(self):
        for var, _ in self.field_vars.values():
            var.set(False)
        self._update_summary()

    def _update_summary(self):
        sel_count = sum(1 for var, _ in self.field_vars.values() if var.get())
        total_count = len(self.field_vars)
        self.summary_label.config(text=f"Selected: {sel_count} / {total_count} field updates")
        self.apply_btn.config(text=f"Apply Selected Updates ({sel_count})")

    def _apply_selected(self):
        selected_updates = [
            (oid, chg)
            for (oid, field), (var, chg) in self.field_vars.items()
            if var.get()
        ]

        if not selected_updates:
            messagebox.showwarning(
                "No Changes Selected",
                "Please select at least one taxonomic update to apply.",
                parent=self
            )
            return

        with self.app_state.df_lock:
            if self.app_state.df_reg is None:
                messagebox.showerror("Error", "No active database loaded.", parent=self)
                return

            if not hasattr(self.app_state, "_log_records") or not self.app_state._log_records:
                if self.app_state.df_log is not None and not self.app_state.df_log.empty:
                    self.app_state._log_records = self.app_state.df_log.to_dict(orient="records")
                else:
                    self.app_state._log_records = []

            problem_to_field = {}
            if getattr(self.app_state, "config", None):
                problems_cfg = self.app_state.config.get("ui_sections", {}).get("problems", [])
                for p in problems_cfg:
                    name = p.get("name")
                    maps_to = p.get("maps_to") or p.get("target")
                    if name and maps_to and maps_to != "Other" and name != "Other_problem":
                        problem_to_field[name] = maps_to

            # Group updates by oid
            by_oid = {}
            for oid, chg in selected_updates:
                by_oid.setdefault(oid, []).append(chg)

            applied_count = 0
            ts = datetime.now().isoformat(timespec="seconds")
            user_name = getpass.getuser()

            for oid, chg_list in by_oid.items():
                reg_oid = oid
                if reg_oid not in self.app_state.df_reg.index:
                    if str(oid).isdigit() and int(oid) in self.app_state.df_reg.index:
                        reg_oid = int(oid)
                    else:
                        matches = [idx for idx in self.app_state.df_reg.index if str(idx).strip() == str(oid).strip()]
                        if matches:
                            reg_oid = matches[0]
                        else:
                            continue

                changed_fields = []
                changed_diffs = []
                prob_changed = []
                prob_diffs = []

                for item in chg_list:
                    f = item["field"]
                    new_v = item["new"]
                    old_v = item["old"]

                    if f in self.app_state.df_reg.columns:
                        self.app_state.df_reg.at[reg_oid, f] = new_v
                        changed_fields.append(f)
                        changed_diffs.append(f'{f}: "{old_v}" -> "{new_v}"')
                        applied_count += 1

                # Auto-clear mapped problem flags
                if self.app_state.df_obs is not None and problem_to_field:
                    for f in changed_fields:
                        for pc, mf in problem_to_field.items():
                            if mf.lower().replace("_", " ").strip() == f.lower().replace("_", " ").strip():
                                if reg_oid in self.app_state.df_obs.index and pc in self.app_state.df_obs.columns:
                                    val = self.app_state.df_obs.at[reg_oid, pc]
                                    if pd.notna(val) and bool(val):
                                        self.app_state.df_obs.at[reg_oid, pc] = False
                                        if pc not in prob_changed:
                                            prob_changed.append(pc)
                                            prob_diffs.append(f'{pc}: "True" -> "False"')

                if changed_fields or prob_changed:
                    log_entry = {
                        "Timestamp": ts,
                        "User": user_name,
                        "Action": "GBIF_UPDATE",
                        "ObjectID": str(oid),
                        "Reviewed": "",
                        "ChangedFields": ", ".join(changed_fields),
                        "ChangedValues": " | ".join(changed_diffs),
                        "ProblemsChanged": ", ".join(prob_changed),
                        "ProblemsChangedValues": " | ".join(prob_diffs),
                        "LocationChanged": "",
                        "LocationChangedValues": "",
                        "SourceFile": os.path.basename(self.app_state.excel_path or ""),
                        "OutputFile": os.path.basename(self.app_state.output_path or self.app_state.excel_path or "")
                    }
                    self.app_state._log_records.append(log_entry)

            self.app_state.df_log = pd.DataFrame(self.app_state._log_records)
            self.app_state.dirty = True

        if self.on_applied_callback:
            try:
                self.on_applied_callback(applied_count, len(by_oid))
            except Exception:
                pass

        messagebox.showinfo(
            "GBIF Updates Applied",
            f"Successfully applied {applied_count} taxonomic changes across {len(by_oid)} objects.",
            parent=self.parent
        )
        self.destroy()


def rollback_gbif_updates(app_state, main_window=None):
    """
    Roll back the latest un-reverted GBIF_UPDATE batch by inspecting df_log.
    """
    with app_state.df_lock:
        if app_state.df_reg is None:
            if main_window:
                messagebox.showerror("Error", "No active database loaded.")
            return False, "No active database loaded"

        if not hasattr(app_state, "_log_records") or not app_state._log_records:
            if app_state.df_log is not None and not app_state.df_log.empty:
                app_state._log_records = app_state.df_log.to_dict(orient="records")
            else:
                app_state._log_records = []

        def _norm_ts(ts):
            if not ts:
                return ""
            return str(ts).strip().replace(" ", "T").split(".")[0]

        # Identify batches that were already rolled back
        rolled_back_ts = set()
        for e in app_state._log_records:
            if e.get("Action") == "GBIF_ROLLBACK":
                cf = str(e.get("ChangedFields", ""))
                if "from GBIF update at " in cf:
                    ts_part = cf.split("from GBIF update at ", 1)[1].strip()
                    rolled_back_ts.add(_norm_ts(ts_part))

        gbif_entries = [
            e for e in app_state._log_records
            if e.get("Action") == "GBIF_UPDATE" and _norm_ts(e.get("Timestamp", "")) not in rolled_back_ts
        ]
        if not gbif_entries:
            if main_window:
                messagebox.showinfo("No Updates Found", "No GBIF taxonomic updates found in the audit log to roll back.")
            return False, "No GBIF updates found in log"

        latest_ts = gbif_entries[-1].get("Timestamp")
        norm_latest = _norm_ts(latest_ts)
        target_entries = [e for e in gbif_entries if _norm_ts(e.get("Timestamp")) == norm_latest]

        reverted_count = 0
        for entry in target_entries:
            oid = str(entry.get("ObjectID", "")).strip()
            if not oid:
                continue

            reg_oid = oid
            if reg_oid not in app_state.df_reg.index:
                if str(oid).isdigit() and int(oid) in app_state.df_reg.index:
                    reg_oid = int(oid)
                else:
                    matches = [idx for idx in app_state.df_reg.index if str(idx).strip() == oid]
                    if matches:
                        reg_oid = matches[0]
                    else:
                        continue

            cv_str = str(entry.get("ChangedValues", ""))
            diffs = cv_str.split(" | ")
            for d in diffs:
                if ' -> ' in d and ': "' in d:
                    parts = d.split(': "', 1)
                    field = parts[0].strip()
                    val_parts = parts[1].split('" -> "', 1)
                    old_val = val_parts[0]
                    if field in app_state.df_reg.columns:
                        app_state.df_reg.at[reg_oid, field] = old_val
                        reverted_count += 1

            # Restore cleared problems if recorded
            pcv_str = str(entry.get("ProblemsChangedValues", ""))
            if pcv_str and app_state.df_obs is not None:
                prob_diffs = pcv_str.split(" | ")
                for pd_item in prob_diffs:
                    if ' -> ' in pd_item and ': "' in pd_item:
                        p_parts = pd_item.split(': "', 1)
                        p_col = p_parts[0].strip()
                        p_val_parts = p_parts[1].split('" -> "', 1)
                        p_old_val = p_val_parts[0].strip().lower() == "true"
                        if reg_oid in app_state.df_obs.index and p_col in app_state.df_obs.columns:
                            app_state.df_obs.at[reg_oid, p_col] = p_old_val

        rollback_log = {
            "Timestamp": datetime.now().isoformat(timespec="seconds"),
            "User": getpass.getuser(),
            "Action": "GBIF_ROLLBACK",
            "ObjectID": "BATCH",
            "Reviewed": "",
            "ChangedFields": f"Rolled back {reverted_count} fields from GBIF update at {latest_ts}",
            "ChangedValues": "",
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "",
            "LocationChangedValues": "",
            "SourceFile": os.path.basename(app_state.excel_path or ""),
            "OutputFile": os.path.basename(app_state.output_path or app_state.excel_path or "")
        }
        from repository import _normalise_log_dataframe
        app_state._log_records.append(rollback_log)
        app_state.df_log = _normalise_log_dataframe(pd.DataFrame(app_state._log_records))
        app_state.dirty = True

    if main_window:
        if hasattr(main_window, "_invalidate_row_cache"):
            main_window._invalidate_row_cache()
        if hasattr(main_window, "invalidate_search_index"):
            main_window.invalidate_search_index()
        if hasattr(main_window, "display_object") and getattr(app_state, "current_object_id", None):
            main_window.display_object(app_state.current_object_id)
        if hasattr(main_window, "object_list") and hasattr(main_window.object_list, "refresh_all_cards"):
            main_window.object_list.refresh_all_cards()
        messagebox.showinfo("Rollback Complete", f"Successfully rolled back {reverted_count} taxonomic changes from {latest_ts}.")

    return True, f"Rolled back {reverted_count} changes"
