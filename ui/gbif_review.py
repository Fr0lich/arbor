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

        self.title("Review GBIF Taxonomic Updates")
        self.geometry(f"{sc(850)}x{sc(560)}")
        self.minsize(sc(600), sc(400))

        self.rows = []
        row_id = 0
        for diff in self.diff_results:
            oid = diff["oid"]
            status = diff.get("status", "ACCEPTED")
            rank = diff.get("rank", "")
            for chg in diff["changes"]:
                self.rows.append({
                    "id": row_id,
                    "selected": True,
                    "oid": str(oid),
                    "field": chg["field"],
                    "old": chg["old"],
                    "new": chg["new"],
                    "status": status,
                    "rank": rank
                })
                row_id += 1

        self._build_ui()
        self._populate_tree()
        self.transient(parent)
        self.grab_set()

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding=sc(10))
        main_frame.pack(fill="both", expand=True)

        hdr_frame = ttk.Frame(main_frame)
        hdr_frame.pack(fill="x", pady=(0, sc(8)))

        title_lbl = ttk.Label(
            hdr_frame,
            text="GBIF Taxonomic Updates",
            font=("Segoe UI", sc(12), "bold")
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ttk.Label(
            hdr_frame,
            text=f"Found {len(self.rows)} proposed changes across {len(self.diff_results)} objects. Select changes to apply:",
            font=("Segoe UI", sc(9))
        )
        sub_lbl.pack(anchor="w", pady=(sc(2), 0))

        act_frame = ttk.Frame(main_frame)
        act_frame.pack(fill="x", pady=(0, sc(6)))

        ttk.Button(act_frame, text="Select All", command=self._select_all).pack(side="left", padx=(0, sc(4)))
        ttk.Button(act_frame, text="Deselect All", command=self._deselect_all).pack(side="left", padx=(0, sc(10)))

        self.summary_label = ttk.Label(
            act_frame,
            text=f"Selected: {len(self.rows)} / {len(self.rows)}",
            font=("Segoe UI", sc(9), "italic")
        )
        self.summary_label.pack(side="left", padx=sc(4))

        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill="both", expand=True)

        columns = ("selected", "oid", "field", "old", "new", "status", "rank")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        
        self.tree.heading("selected", text="Apply", anchor="center")
        self.tree.heading("oid", text="Object ID", anchor="w")
        self.tree.heading("field", text="Field", anchor="w")
        self.tree.heading("old", text="Current Value", anchor="w")
        self.tree.heading("new", text="Proposed GBIF Value", anchor="w")
        self.tree.heading("status", text="Status", anchor="center")
        self.tree.heading("rank", text="Rank", anchor="center")

        self.tree.column("selected", width=sc(50), anchor="center")
        self.tree.column("oid", width=sc(80), anchor="w")
        self.tree.column("field", width=sc(120), anchor="w")
        self.tree.column("old", width=sc(160), anchor="w")
        self.tree.column("new", width=sc(180), anchor="w")
        self.tree.column("status", width=sc(90), anchor="center")
        self.tree.column("rank", width=sc(70), anchor="center")

        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<space>", self._on_space_pressed)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(sc(10), 0))

        self.apply_btn = ttk.Button(
            btn_frame,
            text=f"Apply Updates ({len(self.rows)})",
            command=self._apply_selected
        )
        self.apply_btn.pack(side="right", padx=(sc(6), 0))

        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="right")

    def _populate_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for row in self.rows:
            sel_mark = "✓" if row["selected"] else " "
            self.tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                values=(
                    sel_mark,
                    row["oid"],
                    row["field"],
                    row["old"],
                    row["new"],
                    row["status"],
                    row["rank"]
                )
            )

    def _on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region in ("cell", "tree"):
            item_id = self.tree.identify_row(event.y)
            if item_id:
                self._toggle_row(int(item_id))

    def _on_space_pressed(self, event):
        selected = self.tree.selection()
        if selected:
            self._toggle_row(int(selected[0]))

    def _toggle_row(self, row_id):
        for r in self.rows:
            if r["id"] == row_id:
                r["selected"] = not r["selected"]
                sel_mark = "✓" if r["selected"] else " "
                vals = list(self.tree.item(str(row_id), "values"))
                vals[0] = sel_mark
                self.tree.item(str(row_id), values=vals)
                break
        self._update_summary()

    def _select_all(self):
        for r in self.rows:
            r["selected"] = True
        self._populate_tree()
        self._update_summary()

    def _deselect_all(self):
        for r in self.rows:
            r["selected"] = False
        self._populate_tree()
        self._update_summary()

    def _update_summary(self):
        sel_count = sum(1 for r in self.rows if r["selected"])
        self.summary_label.config(text=f"Selected: {sel_count} / {len(self.rows)}")
        self.apply_btn.config(text=f"Apply Updates ({sel_count})")

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

                for item in r_list:
                    f = item["field"]
                    new_v = item["new"]
                    old_v = item["old"]

                    if f in self.app_state.df_reg.columns:
                        self.app_state.df_reg.at[reg_oid, f] = new_v
                        changed_fields.append(f)
                        changed_diffs.append(f'{f}: "{old_v}" -> "{new_v}"')
                        applied_count += 1

                if changed_fields:
                    log_entry = {
                        "Timestamp": ts,
                        "User": user_name,
                        "Action": "GBIF_UPDATE",
                        "ObjectID": str(oid),
                        "Reviewed": "",
                        "ChangedFields": ", ".join(changed_fields),
                        "ChangedValues": " | ".join(changed_diffs),
                        "ProblemsChanged": "",
                        "ProblemsChangedValues": "",
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
