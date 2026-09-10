import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from datetime import datetime
import os
import getpass
from config import sc


class GBIFReviewDialog(tk.Toplevel):
    def __init__(self, parent, app_state, diff_results, on_applied_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.app_state = app_state
        self.diff_results = diff_results
        self.on_applied_callback = on_applied_callback

        try:
            self.title("Review GBIF Taxonomic Updates")
            import utils
            utils.center_and_fit_toplevel(self, sc(860), sc(620))
            self.minsize(sc(640), sc(420))
        except Exception:
            pass

        # Check dark mode
        is_dark = getattr(self.app_state, "dark_mode_active", False) if hasattr(self.app_state, "dark_mode_active") else False
        self.bg_color = "#181c19" if is_dark else "#fbfaf8"
        self.fg_title = "#e8ebe9" if is_dark else "#2c302e"
        self.fg_muted = "#a6adc8" if is_dark else "#757d77"
        self.border_color = "#2c302e" if is_dark else "#dadada"
        self.card_bg = "#111412" if is_dark else "#ffffff"
        self.chip_old_bg = "#231515" if is_dark else "#fef2f2"
        self.chip_old_fg = "#c93a40"
        self.chip_new_bg = "#122416" if is_dark else "#f0fdf4"
        self.chip_new_fg = "#3a7d44"
        self.btn_primary_bg = "#3a7d44" if is_dark else "#2c302e"
        self.btn_primary_hover = "#4b9e57" if is_dark else "#3d4240"
        self.btn_sec_bg = self.bg_color
        self.btn_sec_fg = self.fg_title
        self.btn_sec_hover = "#242a25" if is_dark else "#e9ece5"

        try:
            self.configure(bg=self.bg_color)
        except Exception:
            pass

        self.rows = []
        self.row_vars = {}
        row_id = 0
        for diff in self.diff_results:
            oid = diff["oid"]
            status = diff.get("status", "ACCEPTED")
            rank = diff.get("rank", "")
            for chg in diff["changes"]:
                row_dict = {
                    "id": row_id,
                    "selected": True,
                    "oid": str(oid),
                    "field": chg["field"],
                    "old": chg["old"],
                    "new": chg["new"],
                    "status": status,
                    "rank": rank
                }
                self.rows.append(row_dict)
                try:
                    self.row_vars[row_id] = tk.BooleanVar(value=True)
                except Exception:
                    self.row_vars[row_id] = None
                row_id += 1

        self._build_ui()
        self._populate_tree()
        try:
            if parent is not None:
                self.transient(parent)
            self.grab_set()
        except Exception:
            pass

    def _build_ui(self):
        main_frame = tk.Frame(self, bg=self.bg_color, padx=sc(16), pady=sc(14))
        main_frame.pack(fill="both", expand=True)

        # Header Frame
        hdr_frame = tk.Frame(main_frame, bg=self.bg_color)
        hdr_frame.pack(fill="x", pady=(0, sc(10)))

        title_row = tk.Frame(hdr_frame, bg=self.bg_color)
        title_row.pack(fill="x")

        tk.Label(
            title_row,
            text="GBIF TAXONOMIC REVIEW",
            font=("Segoe UI", sc(13), "bold"),
            fg=self.fg_title,
            bg=self.bg_color
        ).pack(side="left")

        # Object count badge
        count_chip = tk.Frame(
            title_row,
            bg=self.btn_primary_bg,
            bd=0,
            padx=sc(8), pady=sc(2)
        )
        count_chip.pack(side="left", padx=(sc(10), 0))
        tk.Label(
            count_chip,
            text=f"{len(self.rows)} Updates",
            font=("JetBrains Mono", sc(9), "bold"),
            fg="#ffffff",
            bg=self.btn_primary_bg
        ).pack()

        sub_lbl = tk.Label(
            hdr_frame,
            text=f"Found {len(self.rows)} proposed changes across {len(self.diff_results)} objects. Review Before/After values and select changes to apply:",
            font=("Segoe UI", sc(9)),
            fg=self.fg_muted,
            bg=self.bg_color
        )
        sub_lbl.pack(anchor="w", pady=(sc(4), 0))

        # Action Bar (Select All / Deselect All / Summary)
        act_frame = tk.Frame(main_frame, bg=self.bg_color)
        act_frame.pack(fill="x", pady=(sc(4), sc(8)))

        sel_all_btn = tk.Button(
            act_frame,
            text="Select All",
            command=self._select_all,
            font=("Segoe UI", sc(9)),
            bg=self.btn_sec_bg,
            fg=self.btn_sec_fg,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=sc(10),
            pady=sc(3),
            highlightthickness=1,
            highlightbackground=self.border_color,
            highlightcolor=self.border_color
        )
        sel_all_btn.pack(side="left", padx=(0, sc(6)))
        sel_all_btn.bind("<Enter>", lambda e: sel_all_btn.config(bg=self.btn_sec_hover))
        sel_all_btn.bind("<Leave>", lambda e: sel_all_btn.config(bg=self.btn_sec_bg))

        desel_all_btn = tk.Button(
            act_frame,
            text="Deselect All",
            command=self._deselect_all,
            font=("Segoe UI", sc(9)),
            bg=self.btn_sec_bg,
            fg=self.btn_sec_fg,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=sc(10),
            pady=sc(3),
            highlightthickness=1,
            highlightbackground=self.border_color,
            highlightcolor=self.border_color
        )
        desel_all_btn.pack(side="left", padx=(0, sc(12)))
        desel_all_btn.bind("<Enter>", lambda e: desel_all_btn.config(bg=self.btn_sec_hover))
        desel_all_btn.bind("<Leave>", lambda e: desel_all_btn.config(bg=self.btn_sec_bg))

        self.summary_label = tk.Label(
            act_frame,
            text=f"Selected: {len(self.rows)} / {len(self.rows)}",
            font=("Segoe UI", sc(9.5), "italic"),
            fg=self.fg_muted,
            bg=self.bg_color
        )
        self.summary_label.pack(side="left")

        # Scrollable Cards Canvas Container
        canvas_outer = tk.Frame(main_frame, bg=self.bg_color, bd=1, relief="solid", highlightbackground=self.border_color, highlightthickness=1)
        canvas_outer.pack(fill="both", expand=True, pady=(0, sc(10)))

        self.canvas = tk.Canvas(canvas_outer, bg=self.bg_color, bd=0, highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(canvas_outer, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg=self.bg_color, padx=sc(8), pady=sc(8))

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width) if getattr(self.canvas, "_last_w", None) != e.width and not setattr(self.canvas, "_last_w", e.width) else None
        )
        self.canvas.configure(yscrollcommand=self.v_scroll.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.v_scroll.pack(side="right", fill="y")

        # Bind mouse wheel
        self._bind_mousewheel(self.canvas)
        self._bind_mousewheel(self.scroll_frame)

        # Footer Actions
        btn_frame = tk.Frame(main_frame, bg=self.bg_color)
        btn_frame.pack(fill="x", side="bottom")

        self.apply_btn = tk.Button(
            btn_frame,
            text=f"APPLY SELECTED UPDATES ({len(self.rows)})",
            command=self._apply_selected,
            font=("Segoe UI", sc(9.5), "bold"),
            bg=self.btn_primary_bg,
            fg="#ffffff",
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=sc(16),
            pady=sc(6)
        )
        self.apply_btn.pack(side="right", padx=(sc(8), 0))
        self.apply_btn.bind("<Enter>", lambda e: self.apply_btn.config(bg=self.btn_primary_hover))
        self.apply_btn.bind("<Leave>", lambda e: self.apply_btn.config(bg=self.btn_primary_bg))

        cancel_btn = tk.Button(
            btn_frame,
            text="CANCEL",
            command=self.destroy,
            font=("Segoe UI", sc(9.5), "bold"),
            bg=self.btn_sec_bg,
            fg=self.btn_sec_fg,
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=sc(14),
            pady=sc(5),
            highlightthickness=1,
            highlightbackground=self.border_color,
            highlightcolor=self.border_color
        )
        cancel_btn.pack(side="right")
        cancel_btn.bind("<Enter>", lambda e: cancel_btn.config(bg=self.btn_sec_hover))
        cancel_btn.bind("<Leave>", lambda e: cancel_btn.config(bg=self.btn_sec_bg))

    def _bind_mousewheel(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        widget.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"), add="+")
        widget.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"), add="+")

    def _on_mousewheel(self, event):
        if hasattr(self, "canvas") and self.canvas.winfo_exists() and event.delta:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _populate_cards(self):
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        by_oid = {}
        for r in self.rows:
            by_oid.setdefault(r["oid"], []).append(r)

        for oid, r_list in by_oid.items():
            status = r_list[0].get("status", "ACCEPTED")
            rank = r_list[0].get("rank", "")

            # Specimen Card container
            card = tk.Frame(
                self.scroll_frame,
                bg=self.card_bg,
                bd=1,
                relief="solid",
                highlightbackground=self.border_color,
                highlightthickness=1
            )
            card.pack(fill="x", pady=(0, sc(10)))
            self._bind_mousewheel(card)

            # Card Header
            card_header = tk.Frame(card, bg=self.card_bg, padx=sc(12), pady=sc(8))
            card_header.pack(fill="x")
            self._bind_mousewheel(card_header)

            tk.Label(
                card_header,
                text=f"SPECIMEN #{oid}",
                font=("JetBrains Mono", sc(10), "bold"),
                fg=self.fg_title,
                bg=self.card_bg
            ).pack(side="left")

            # Rank & Status chip
            status_chip = tk.Frame(
                card_header,
                bg=self.chip_new_bg if status == "ACCEPTED" else "#1c2b38",
                bd=1,
                relief="solid",
                highlightbackground=self.chip_new_fg if status == "ACCEPTED" else "#4a7b9d",
                highlightthickness=1,
                padx=sc(6),
                pady=sc(2)
            )
            status_chip.pack(side="right")
            self._bind_mousewheel(status_chip)

            status_text = f"{rank.upper()} • {status}" if rank else status
            status_lbl = tk.Label(
                status_chip,
                text=status_text,
                font=("JetBrains Mono", sc(8.5), "bold"),
                fg=self.chip_new_fg if status == "ACCEPTED" else "#4a7b9d",
                bg=self.chip_new_bg if status == "ACCEPTED" else "#1c2b38"
            )
            status_lbl.pack()
            self._bind_mousewheel(status_lbl)

            # Hairline divider
            tk.Frame(card, bg=self.border_color, height=1).pack(fill="x")

            # Diff items within specimen card
            diffs_container = tk.Frame(card, bg=self.card_bg, padx=sc(12), pady=sc(8))
            diffs_container.pack(fill="x")
            self._bind_mousewheel(diffs_container)

            for item in r_list:
                row_id = item["id"]
                var = self.row_vars.get(row_id)
                if var is None:
                    try:
                        var = tk.BooleanVar(value=item["selected"])
                        self.row_vars[row_id] = var
                    except Exception:
                        var = None

                diff_row = tk.Frame(diffs_container, bg=self.card_bg, pady=sc(4))
                diff_row.pack(fill="x")
                self._bind_mousewheel(diff_row)

                # Checkbox & Field Name
                top_row = tk.Frame(diff_row, bg=self.card_bg)
                top_row.pack(fill="x", anchor="w")
                self._bind_mousewheel(top_row)

                cb_kwargs = {
                    "text": item["field"],
                    "font": ("Segoe UI", sc(10), "bold"),
                    "fg": self.fg_title,
                    "bg": self.card_bg,
                    "activebackground": self.card_bg,
                    "activeforeground": self.fg_title,
                    "selectcolor": self.card_bg,
                    "bd": 0,
                    "highlightthickness": 0,
                    "cursor": "hand2",
                    "command": lambda rid=row_id: self._on_card_toggle(rid)
                }
                if var is not None:
                    cb_kwargs["variable"] = var

                cb = tk.Checkbutton(top_row, **cb_kwargs)
                cb.pack(side="left")
                self._bind_mousewheel(cb)

                # Before/After comparison grid
                grid_frame = tk.Frame(diff_row, bg=self.card_bg, padx=sc(24), pady=sc(4))
                grid_frame.pack(fill="x")
                grid_frame.columnconfigure(0, weight=1)
                grid_frame.columnconfigure(1, weight=1)
                self._bind_mousewheel(grid_frame)

                # Current Value (Before)
                old_chip = tk.Frame(
                    grid_frame,
                    bg=self.chip_old_bg,
                    bd=1,
                    relief="solid",
                    highlightbackground="#c93a40",
                    highlightthickness=1,
                    padx=sc(8),
                    pady=sc(4)
                )
                old_chip.grid(row=0, column=0, sticky="ew", padx=(0, sc(6)))
                self._bind_mousewheel(old_chip)

                old_tag = tk.Label(
                    old_chip,
                    text="CURRENT",
                    font=("JetBrains Mono", sc(8), "bold"),
                    fg=self.chip_old_fg,
                    bg=self.chip_old_bg
                )
                old_tag.pack(anchor="w")
                self._bind_mousewheel(old_tag)

                old_val = tk.Label(
                    old_chip,
                    text=item["old"] if item["old"] else "(Empty)",
                    font=("JetBrains Mono", sc(9.5)),
                    fg=self.fg_title if item["old"] else self.fg_muted,
                    bg=self.chip_old_bg,
                    anchor="w",
                    wraplength=sc(320)
                )
                old_val.pack(anchor="w")
                self._bind_mousewheel(old_val)

                # Proposed Value (After)
                new_chip = tk.Frame(
                    grid_frame,
                    bg=self.chip_new_bg,
                    bd=1,
                    relief="solid",
                    highlightbackground=self.chip_new_fg,
                    highlightthickness=1,
                    padx=sc(8),
                    pady=sc(4)
                )
                new_chip.grid(row=0, column=1, sticky="ew", padx=(sc(6), 0))
                self._bind_mousewheel(new_chip)

                new_tag = tk.Label(
                    new_chip,
                    text="PROPOSED (GBIF)",
                    font=("JetBrains Mono", sc(8), "bold"),
                    fg=self.chip_new_fg,
                    bg=self.chip_new_bg
                )
                new_tag.pack(anchor="w")
                self._bind_mousewheel(new_tag)

                new_val = tk.Label(
                    new_chip,
                    text=item["new"] if item["new"] else "(Empty)",
                    font=("JetBrains Mono", sc(9.5), "bold"),
                    fg=self.chip_new_fg if item["new"] else self.fg_muted,
                    bg=self.chip_new_bg,
                    anchor="w",
                    wraplength=sc(320)
                )
                new_val.pack(anchor="w")
                self._bind_mousewheel(new_val)

    def _populate_tree(self):
        """Compatibility alias for tests."""
        self._populate_cards()

    def _on_card_toggle(self, row_id):
        for r in self.rows:
            if r["id"] == row_id:
                var = self.row_vars.get(row_id)
                if var is not None and hasattr(var, "get"):
                    r["selected"] = bool(var.get())
                break
        self._update_summary()

    def _select_all(self):
        for r in self.rows:
            r["selected"] = True
            var = self.row_vars.get(r["id"])
            if var is not None and hasattr(var, "set"):
                var.set(True)
        self._update_summary()

    def _deselect_all(self):
        for r in self.rows:
            r["selected"] = False
            var = self.row_vars.get(r["id"])
            if var is not None and hasattr(var, "set"):
                var.set(False)
        self._update_summary()

    def _update_summary(self):
        sel_count = sum(1 for r in self.rows if r["selected"])
        if hasattr(self, "summary_label") and self.summary_label.winfo_exists():
            self.summary_label.config(text=f"Selected: {sel_count} / {len(self.rows)}")
        if hasattr(self, "apply_btn") and self.apply_btn.winfo_exists():
            self.apply_btn.config(text=f"APPLY SELECTED UPDATES ({sel_count})")

    def _apply_selected(self):
        selected_rows = [r for r in self.rows if r["selected"]]
        if not selected_rows:
            messagebox.showwarning("No Changes Selected", "Please select at least one taxonomic update to apply.", parent=self)
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

            by_oid = {}
            for r in selected_rows:
                by_oid.setdefault(r["oid"], []).append(r)

            applied_count = 0
            ts = datetime.now().isoformat(timespec="seconds")
            user_name = getpass.getuser()

            problem_to_field = {}
            if getattr(self.app_state, "config", None):
                problems_cfg = self.app_state.config.get("ui_sections", {}).get("problems", [])
                for p in problems_cfg:
                    name = p.get("name")
                    maps_to = p.get("maps_to") or p.get("target")
                    if name and maps_to and maps_to != "Other" and name != "Other_problem":
                        problem_to_field[name] = maps_to

            for oid, r_list in by_oid.items():
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

                for item in r_list:
                    f = item["field"]
                    new_v = item["new"]
                    old_v = item["old"]

                    if f in self.app_state.df_reg.columns:
                        self.app_state.df_reg.at[reg_oid, f] = new_v
                        changed_fields.append(f)
                        changed_diffs.append(f'{f}: "{old_v}" -> "{new_v}"')
                        applied_count += 1

                # Clear mapped problem flags
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
