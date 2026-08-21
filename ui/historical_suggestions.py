from tkinter import filedialog, messagebox
import threading
import pandas as pd
from collections import OrderedDict

class HistoricalSuggestionsMixin:
    def _get_db_dict_cache(self, db, oid=None):
        if "dict_cache" not in db:
            db["dict_cache"] = {}

        cache = db["dict_cache"]

        if oid is None:
            return cache

        if oid not in cache:
            oid_cache = {}
            reg_by_id = db.get("reg_by_id")

            if reg_by_id is not None and oid in reg_by_id.index:
                rows = reg_by_id.loc[oid]

                if isinstance(rows, pd.DataFrame):
                    # Handle duplicate rows with same ObjectID by gathering all unique column values across rows
                    for row in rows.itertuples(index=False, name=None):
                        for col, val in zip(rows.columns, row):
                            if pd.notna(val):
                                val_str = str(val).strip()
                                if val_str and val_str != "nan":
                                    if col not in oid_cache:
                                        oid_cache[col] = []
                                    if val_str not in oid_cache[col]:
                                        oid_cache[col].append(val_str)
                elif isinstance(rows, pd.Series):
                    for col, val in rows.items():
                         if pd.notna(val):
                            val_str = str(val).strip()
                            if val_str and val_str != "nan":
                                if col not in oid_cache:
                                    oid_cache[col] = []
                                if val_str not in oid_cache[col]:
                                    oid_cache[col].append(val_str)
                else:
                    # Single value or fallback
                    pass
            cache[oid] = oid_cache

        return cache

    def invalidate_history_cache(self, oid=None):
        if not hasattr(self, "_history_cache") or self._history_cache is None:
            return
        if oid is None:
            self._history_cache.clear()
        else:
            self._history_cache.pop((oid, True), None)
            self._history_cache.pop((oid, False), None)
            s_oid = str(oid)
            self._history_cache.pop((s_oid, True), None)
            self._history_cache.pop((s_oid, False), None)
            if s_oid.isdigit():
                self._history_cache.pop((int(s_oid), True), None)
                self._history_cache.pop((int(s_oid), False), None)

    def collect_historical_suggestions(self, oid, show_all_override=None):


        if show_all_override is None:
            show_all = self.show_all_history_var.get()
        else:
            show_all = show_all_override


        cache_key = (oid, show_all)

        if hasattr(self, "_history_cache"):
            cached = self._history_cache.get(cache_key)
            if cached is not None:
                self._history_cache.move_to_end(cache_key)
                return cached
        else:
            self._history_cache = OrderedDict()

        suggestions = {}

        if not self.app.historical_dbs:
            self._history_cache[cache_key] = suggestions
            return suggestions

        db_oid_entries = []
        for db in self.app.historical_dbs:
            dict_cache = self._get_db_dict_cache(db, oid)
            if oid in dict_cache and dict_cache[oid]:
                db_oid_entries.append((db["name"], dict_cache[oid]))

        field_to_prob = {
            v: k for k, v in self.problem_to_field.items()
        }


        fields = set()


        fields.update(self.problem_to_field.values())


        if show_all:
            if hasattr(self, "reg_columns") and self.reg_columns:
                fields.update(self.reg_columns)
            elif hasattr(self, "reg_by_id") and self.reg_by_id is not None:
                fields.update(self.reg_by_id.columns)

        # Get registration row via fast dictionary lookup
        reg = {}
        reg_dict = self._get_reg_dict() if hasattr(self, "_get_reg_dict") else None
        if reg_dict is not None:
            reg = reg_dict.get(oid)
            if reg is None and str(oid).isdigit():
                reg = reg_dict.get(int(oid), {})
            if reg is None:
                reg = {}
        elif hasattr(self, "reg_by_id") and self.reg_by_id is not None and oid in self.reg_by_id.index:
            r = self.reg_by_id.loc[oid]
            if isinstance(r, pd.DataFrame):
                reg = r.iloc[0].to_dict()
            elif isinstance(r, pd.Series):
                reg = r.to_dict()

        for field in fields:
            prob_col = field_to_prob.get(field)

            is_unknown = self.is_unknown(str(reg.get(field, "")).strip()) if reg else False
            is_active_prob = prob_col and self.is_problem_active(oid, prob_col)

            if not show_all:
                if not (is_active_prob or is_unknown):
                    continue

            value_map = {}

            for db_name, oid_data in db_oid_entries:
                field_vals = oid_data.get(field, [])
                for val in field_vals:
                    if self.is_word_ignored(val):
                        continue
                    value_map.setdefault(val, []).append(db_name)

            if value_map:
                suggestions[field] = value_map
            elif show_all or is_active_prob or is_unknown:
                suggestions[field] = {
                    "(No data found)": []
                }

        self._history_cache[cache_key] = suggestions
        if len(self._history_cache) > 50:
            self._history_cache.popitem(last=False)
        return suggestions


    def _toggle_history_local(self, win, oid):
        current = getattr(win, "local_show_all", False)
        new_state = not current
        self.open_historical_suggestions(show_all_override=new_state, refresh=True)


    def _make_row_widgets(self, row_frame, bg, widgets):
        """Lagre widgets i rad for enkel highlight senere"""
        row_frame._widgets = widgets
        row_frame._base_bg = bg


    def _set_row_bg(self, row_frame, color):
        """Oppdater hele raden"""
        try:
            for w in row_frame._widgets:
                w.configure(bg=color)
        except Exception:
            pass


    def _highlight_row(self, row_frame):
        self._set_row_bg(row_frame, "#d0ebff")  # valgt


    def _hover_row_enter(self, row_frame):
        if not getattr(row_frame, "_selected", False):
            self._set_row_bg(row_frame, "#e8f2ff")


    def _hover_row_leave(self, row_frame):
        if not getattr(row_frame, "_selected", False):
            self._set_row_bg(row_frame, row_frame._base_bg)


    def _on_combo_select(self, selected_frame, all_rows):
        """temp"""
        for rf in all_rows:
            rf._selected = False
            self._set_row_bg(rf, rf._base_bg)

        selected_frame._selected = True
        self._highlight_row(selected_frame)


    def open_historical_suggestions(self, show_all_override=None, refresh=False):
        show_all = show_all_override if show_all_override is not None else self.show_all_history_var.get()
        if not self.app.historical_dbs:
            if not refresh:
                from tkinter import messagebox
                messagebox.showinfo("No data loaded", "No historical data is loaded.\n\nPlease load books or earlier databases first.")
                self.open_load_data_menu()
            return
        oid = self.app.current_object_id
        if not oid: return
        suggestions = self.collect_historical_suggestions(oid, show_all_override=show_all)
        if not suggestions and not show_all:
            self.history_indicator_label.config(text="")
        active_count = sum(1 for prob_col in self.problem_to_field if self.problem_vars.get(prob_col) and self.problem_vars[prob_col].get())
        if active_count:
            self.history_indicator_label.config(text=f"Suggestions available ({active_count} active problem(s))", foreground="blue")
        else:
            self.history_indicator_label.config(text=" Suggestions available", foreground="gray")
        from ui.historical_resolver import HistoricalConflictResolverWindow
        HistoricalConflictResolverWindow(self, oid, suggestions)


    def load_books_file(self):
        last_dir = __import__("config").get_last_dir("last_book_dir")
        dialog_kwargs = dict(
            title="Select Books Excel file",
            filetypes=[("Excel files", "*.xlsx")],
        )
        # Guard: only pass initialdir if it resolves to an existing directory
        import os as _os
        if last_dir and _os.path.isdir(last_dir):
            dialog_kwargs["initialdir"] = last_dir

        path = filedialog.askopenfilename(**dialog_kwargs)
        if not path:
            return
        __import__("config").set_last_dir("last_book_dir", path)

        self._show_progress("Loading Books (Reading sheets)...", 100)

        threading.Thread(
            target=self._load_books_file_worker,
            args=(path,),
            daemon=True
        ).start()


    def _load_books_file_worker(self, path):
        try:
            from repository import _open_excel_reader, _normalize_object_id_series
            with _open_excel_reader(path) as xls:
                loaded = []
                total = len(xls.sheet_names)

                allowed_cols = set(self.app.config.get("books_columns", []))
                if "ObjectID" not in allowed_cols:
                    allowed_cols.add("ObjectID")

                for i, sheet_name in enumerate(xls.sheet_names):
                    self.root.after(0, lambda current_idx=i, total_count=total: self.image_scan_progress.configure(value=current_idx, maximum=total_count))

                    try:
                        df = pd.read_excel(
                            xls,
                            sheet_name=sheet_name,
                            usecols=lambda x: x in allowed_cols
                        )

                        if "ObjectID" not in df.columns:
                            continue

                        df["ObjectID"] = _normalize_object_id_series(df["ObjectID"])

                        loaded.append({
                            "name": f"Books: {sheet_name}",
                            "path": path,
                            "df_reg": df,
                            "reg_by_id": None,
                        })

                    except Exception:
                        continue


            self.root.after(
                0,
                lambda: self._finish_load_books(loaded)
            )

        except Exception as e:
            err_msg = str(e)

            self.root.after(
                0,
                lambda: (
                    self._hide_progress("Books load failed"),
                    messagebox.showerror("Error", f"Could not load Books file:\n{err_msg}")
                )
            )


    def _finish_load_books(self, loaded):
        self._history_cache = OrderedDict()
        self._cached_dbs_id = None

        if not loaded:
            if hasattr(self, "image_scan_progress"):
                try:
                    self._hide_progress("Books load failed")
                    self.image_scan_progress.configure(mode="determinate")
                except Exception:
                    pass
            messagebox.showwarning(
                "No valid sheets",
                "No usable sheets were found in the Books file."
            )
            if hasattr(self, "status"):
                self.system_status.config(text="Books load failed")
            return

        self._history_presence_set = set()
        for db in loaded:
            reg_df = self._get_reg_by_id(db) if hasattr(self, "_get_reg_by_id") else None
            if reg_df is None and db.get("reg_by_id") is None and db.get("df_reg") is not None and isinstance(db.get("df_reg"), pd.DataFrame):
                try:
                    if "ObjectID" in db["df_reg"].columns:
                        db["reg_by_id"] = db["df_reg"].set_index("ObjectID")
                    else:
                        db["reg_by_id"] = db["df_reg"]
                except Exception:
                    pass
            reg_by_id = db.get("reg_by_id")
            if reg_by_id is not None and hasattr(reg_by_id, "index"):
                self._history_presence_set.update(reg_by_id.index)

        self.app.historical_dbs = loaded

        self._has_suggestions_set = None
        self._problem_cache.clear()
        if hasattr(self, "_history_cache"):
            self._history_cache.clear()

        self.refresh_list()

        if hasattr(self, "image_scan_progress"):
            try:
                self.system_status.config(text=f"Loaded Books file ({len(loaded)} sheets) — scanning suggestions...")
                self._show_progress("Scanning suggestions... 0/N", len(self.app.active_object_ids))
            except Exception:
                pass

        threading.Thread(
            target=self._prescan_suggestions_worker,
            daemon=True
        ).start()

    def _prescan_suggestions_worker(self):
        suggestions_set = set()
        presence_set = set()
        total = len(self.app.active_object_ids)

        # Populate presence_set from historical_dbs
        for db in getattr(self.app, "historical_dbs", []):
            reg_by_id = db.get("reg_by_id")
            if reg_by_id is not None:
                for hist_id in reg_by_id.index:
                    presence_set.add(hist_id)
                    s_id = str(hist_id)
                    presence_set.add(s_id)
                    if s_id.isdigit():
                        presence_set.add(int(s_id))

        for i, oid in enumerate(self.app.active_object_ids):
            # Update progress bar
            self.root.after(0, lambda current=i, max_val=total: (
                getattr(self, "image_scan_progress", None) and self.image_scan_progress.configure(value=current, maximum=max_val),
                getattr(self, "progress_label", None) and self.progress_label.config(text=f"Scanning suggestions... {current}/{max_val}")
            ))

            suggs = self.collect_historical_suggestions(oid, show_all_override=False)
            has_valid = False
            if suggs:
                for field, values in suggs.items():
                    if list(values.keys()) != ["(No data found)"]:
                        has_valid = True
                        break
            if has_valid:
                suggestions_set.add(oid)
                s_oid = str(oid)
                suggestions_set.add(s_oid)
                if s_oid.isdigit():
                    suggestions_set.add(int(s_oid))

        self.root.after(0, lambda: self._finish_prescan(suggestions_set, presence_set))

    def _finish_prescan(self, suggestions_set, presence_set=None):
        self._has_suggestions_set = suggestions_set
        if presence_set is not None:
            self._history_presence_set = presence_set
        self._list_dirty = True
        self.refresh_list()

        oid = self.app.current_object_id
        if oid:
            self.load_object(oid)

        if hasattr(self, "image_scan_progress"):
            try:
                self._hide_progress("Books loaded and scanned")
                self.image_scan_progress.configure(mode="determinate")
            except Exception:
                pass

        self.update_history_button_state()
        if hasattr(self, "_history_cache"):
            self._history_cache.clear()

        self.system_status.config(text="Historical data ready")
        oid = self.app.current_object_id
        if oid:
            self.update_history_indicator(oid)

    def update_history_indicator(self, oid):

        if not self.app.historical_dbs:
            self.history_indicator_label.config(text="")
            return


        suggestions = self.collect_historical_suggestions(oid)

        if suggestions:
            self.history_indicator_label.config(
                text=" Suggestions available (click for details)",
                foreground="blue"
            )
            return


        has_any_history = any(
            (self._get_reg_by_id(db) is not None and oid in self._get_reg_by_id(db).index)
            for db in self.app.historical_dbs
        )

        if has_any_history:
            self.history_indicator_label.config(
                text=" Historical data loaded. No suggestions for current problems",
                foreground="gray"
            )
        else:
            self.history_indicator_label.config(text="")


    def update_history_button_state(self):

        if not hasattr(self, "next_history_btn"):
            return

        has_data = bool(self.app.historical_dbs)

        if has_data:
            self.next_history_btn.config(
                state="normal",
                text="Next Problem with Historical Data"
            )
        else:
            self.next_history_btn.config(
                state="disabled",
                text="No Historical Data Loaded"
            )


            if hasattr(self, "status"):
                self.system_status.config(
                    text="Load Books or previous databases to enable historical navigation"
                )

