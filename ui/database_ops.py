import os
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
from datetime import datetime
import pandas as pd
from utils import debug_error
from repository import ExcelRepository, REVIEWED_COLUMN

class DatabaseOpsMixin:
    def _write_excel(self, path):
        """Save the current in-memory state to Excel directly."""
        missing_problem_cols = [col for col in self.problem_columns if col not in self.app.df_obs.columns]
        if missing_problem_cols:
            self.app.df_obs[missing_problem_cols] = pd.DataFrame({col: False for col in missing_problem_cols}, index=self.app.df_obs.index)

        from repository import SQLiteRepository
        SQLiteRepository.export_to_excel(
            sqlite_path=None,
            excel_path=path,
            config=self.app.config,
            df_reg=self.app.df_reg,
            df_obs=self.app.df_obs,
            df_log=self.app.df_log
        )


    def _write_excel_async(self, path, callback=None, show_saving_badge=True):
        """Save the current in-memory state to Excel in a background thread.

        Args:
            path: Target file path.
            callback: Optional callable(success: bool, err: str | None) invoked
                      on the main thread when the worker finishes.
            show_saving_badge: If True, immediately show the "Saving…" badge
                               before the thread starts (zero-latency feedback).
        """
        if getattr(self, '_save_in_progress', False):
            # Skip — a background save is already running
            return

        self._save_in_progress = True

        # U2-F: Zero-latency visual feedback — update badge *before* spawning
        # the thread so the user sees an instant response to Ctrl+S.
        if show_saving_badge:
            self.set_status_badge("saving", "💾 Saving…")

        try:
            missing_problem_cols = [col for col in self.problem_columns if col not in self.app.df_obs.columns]
            if missing_problem_cols:
                self.app.df_obs[missing_problem_cols] = pd.DataFrame({col: False for col in missing_problem_cols}, index=self.app.df_obs.index)

            # P1-B: Hold df_lock for the minimum time needed to snapshot all frames.
            # The RLock allows the main thread to still acquire it recursively.
            with self.app.df_lock:
                df_reg_copy = self.app.df_reg.copy() if self.app.df_reg is not None else None
                df_obs_copy = self.app.df_obs.copy() if self.app.df_obs is not None else None
                df_log_copy = self.app.df_log.copy() if getattr(self.app, 'df_log', None) is not None else None
        except Exception as e:
            self._save_in_progress = False
            self.set_status_badge("error", "Save Error")
            if callback:
                callback(False, str(e))
            return

        _outer_callback = callback

        def _on_done(success, err=None):
            self._save_in_progress = False
            if _outer_callback:
                _outer_callback(success, err)

        def save_worker():
            try:
                from repository import SQLiteRepository
                SQLiteRepository.export_to_excel(
                    sqlite_path=None,
                    excel_path=path,
                    config=self.app.config,
                    df_reg=df_reg_copy,
                    df_obs=df_obs_copy,
                    df_log=df_log_copy
                )
                self.root.after(0, lambda: _on_done(True, None))
            except Exception as e:
                from utils import debug_error
                debug_error("_write_excel_async worker", str(e))
                err_msg = str(e)
                self.root.after(0, lambda err=err_msg: _on_done(False, err))

        import threading
        threading.Thread(target=save_worker, daemon=True).start()


    def create_new_database(self):
        from ui.new_database_wizard import NewDatabaseWizard
        def on_complete():
                pass
        NewDatabaseWizard(self.root, self.app, on_complete)


    def open_excel(self):
        path = filedialog.askopenfilename(
            filetypes=[("Excel files", "*.xlsx")],
            initialdir=__import__("config").get_last_dir("last_db_dir")
        )
        if not path:
            return
        __import__("config").set_last_dir("last_db_dir", path)

        self.object_loaded = False
        self.app.current_object_id = None
        self.initializing = True


        self._show_progress(
            text="Loading Excel file",
            maximum=100
        )

        t = threading.Thread(
            target=self._open_excel_worker,
            args=(path,),
            daemon=True
        )
        t.start()


    def open_excel_from_path(self, path):
        threading.Thread(
            target=self._open_excel_worker,
            args=(path,),
            daemon=True
        ).start()


    def _open_excel_worker(self, path):
        try:

            self.root.after(0, lambda: self.image_scan_progress.configure(value=10))

            if path.endswith(".json"):
                import json
                import pandas as pd
                import io
                with open(path, "r") as f:
                    data = json.load(f)

                def load_df(key):
                    val = data.get(key)
                    if val is not None:
                        return pd.read_json(io.StringIO(val), orient="table")
                    return None

                df_reg = load_df("df_reg")
                df_obs = load_df("df_obs")
                df_photo = load_df("df_photo")
                df_log = load_df("df_log")
            else:
                df_reg, df_obs, df_photo, df_log = ExcelRepository.load_excel(path, self.app.config)

            self.root.after(0, lambda: self.image_scan_progress.configure(value=60))

            base, _ = os.path.splitext(path)
            # Ensure the output path uses .xlsx even if we loaded from a .json autosave
            base_xlsx = base.replace(".autosave", "")
            output_path = f"{base_xlsx}_updated_{datetime.now():%Y%m%d_%H%M%S}.xlsx"

            # PERFORMANCE OPTIMIZATION: Warm historical databases cache in the background thread
            # if they were loaded by the Startup Dialog, avoiding a multi-second main-thread freeze on startup.

            # PERFORMANCE OPTIMIZATION: Pre-compute all expensive in-memory caches
            # (row dicts, problem cache, search index, photo counts) while still on
            # the background thread. When _finish_open_excel runs on the main thread,
            # it finds everything ready — refresh_list() skips the O(N×M) problem loop
            # and the list populates in milliseconds instead of seconds.
            self.root.after(0, lambda: self.system_status.config(text="Building indexes..."))
            self.root.after(0, lambda: self.image_scan_progress.configure(value=70))
            self._precompute_startup_caches(df_reg, df_obs, df_photo)
            self.root.after(0, lambda: self.image_scan_progress.configure(value=82))

            def _safe_finish(p=path, op=output_path,
                             r=df_reg, o=df_obs, ph=df_photo, l=df_log):
                try:
                    self._finish_open_excel(p, op, r, o, ph, l)
                except Exception as exc:
                    debug_error("_finish_open_excel", str(exc))
                    messagebox.showerror(
                        "Error loading file",
                        f"The file was read but could not be initialised:\n{exc}"
                    )
            self.root.after(0, _safe_finish)

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            err_msg = str(e)
            self.root.after(0, lambda msg=err_msg, t=tb: self.show_traceback_dialog("Excel Load Error", f"An error occurred while loading the Excel/DB file: {msg}", t))


    def _finish_open_excel(self, path, output_path, df_reg, df_obs, df_photo, df_log):
        self._history_presence_set = set()
        self._has_suggestions_set = set()

        # PERFORMANCE OPTIMIZATION (Bolt): Reconstruct the original Excel path as active path if loaded from an autosave
        if ".autosave" in path:
            orig_path = path.replace(".autosave.json", ".xlsx").replace(".autosave.xlsx", ".xlsx")
            if os.path.exists(orig_path):
                path = orig_path

        # If df_reg has index name already set to ObjectID, we don't have duplicated column
        if "ObjectID" in df_reg.columns:
            dupes = df_reg[df_reg["ObjectID"].duplicated()]["ObjectID"].unique()
        else:
            dupes = []

        if len(dupes) > 0:
            self.show_banner(
                f"⚠ {len(dupes)} duplicate ObjectID(s) found. Only the first occurrence will be kept: "
                + ", ".join(dupes[:10]),
                "warning",
                duration_ms=10000
            )

            df_reg = df_reg.drop_duplicates(subset="ObjectID")



        self.app.df_obs = df_obs

        self.app.excel_path = path
        self.app.output_path = output_path
        self.app.df_reg = df_reg
        self.app.df_obs = df_obs
        self.app.df_photo = df_photo
        self.app.df_log = df_log

        if "ObjectID" in self.app.df_reg.columns:
            self.app.df_reg.set_index("ObjectID", inplace=True)
        if "ObjectID" in self.app.df_obs.columns:
            self.app.df_obs.set_index("ObjectID", inplace=True)
        if "ObjectID" in self.app.df_photo.columns:
            self.app.df_photo.set_index("ObjectID", inplace=True)

        self.app.initial_df_obs = self.app.df_obs.copy()

        self.reg_by_id = self.app.df_reg
        self.obs_by_id = self.app.df_obs
        self.photo_by_id = self.app.df_photo

        self.app.active_object_ids = list(self.app.df_reg.index)
        # PERFORMANCE OPTIMIZATION (Bolt): Call self.refresh_list() instead of manual loop to populate
        # the list with pre-calculated fields and apply correct color/state styles in a single fast pass.
        self.refresh_list()


        self.invalidate_search_index()
        self.build_search_index()

        self.initializing = False
        self.app.dirty = False
        self.update_dirty_ui()
        self.update_review_progress()
        self.update_object_count()

        self.system_status.config(text="Excel loaded - loading images...")
        self.image_scan_progress.configure(value=85)

        self.start_autosave_loop()
        self._check_and_prompt_autosave(path)

        if self.image_folder:
            threading.Thread(
                target=self.build_image_index,
                args=(self.image_folder,),
                daemon=True
            ).start()

        # Detect whether we are in startup (LoadingWindow is active) or a
        # mid-session file reload triggered from the menu.
        in_startup = (getattr(self, '_loading_window', None) is not None)

        if self.app.active_object_ids:
            first_oid = self.app.active_object_ids[0]
            if in_startup:
                # Startup path: load the first object NOW (synchronous w.r.t. the
                # event loop) so the window is fully populated before it appears.
                # _startup_load_first_and_reveal will call _on_startup_ready() after
                # load_object() finishes (or defer to build_image_index if scanning).
                self.root.after(0, lambda oid=first_oid: self._startup_load_first_and_reveal(oid))
            else:
                # Normal mid-session reload: use the standard event-based flow.
                self.root.after(0, self._select_first_object)
                if not self.image_folder:
                    self.image_scan_progress.configure(value=100)
                    self._hide_progress("Ready")
        else:
            # No objects in database
            if in_startup:
                self.root.after(0, self._on_startup_ready)
            elif not self.image_folder:
                self.image_scan_progress.configure(value=100)
                self._hide_progress("Ready")


        self.root.after(50, self.object_list.focus_set)
        self.root.title(f"arbor {self.app.config_name}")


    def _on_startup_ready(self):
        """
        Called once ALL startup work is complete (first object loaded + image scan done).
        Dismisses the LoadingWindow and reveals the main window in a fully ready state.
        Previously _hide_progress("Ready") was called too early — before load_object()
        had run — causing the user to see the main window populate itself.
        """
        self.image_scan_progress.configure(value=100)
        self._hide_progress("Ready")

    def _startup_load_first_and_reveal(self, first_oid):
        """
        During startup: directly call load_object() for the first record so the
        main window is fully populated BEFORE the LoadingWindow is dismissed.
        Only reveals the window (via _on_startup_ready) when no background image
        scan is running; otherwise build_image_index._notify_ui handles the reveal.
        """
        # Select the first row in the list widget (visual sync)
        self.object_list.selection_clear(0, tk.END)
        self.object_list.selection_set(0)
        self.object_list.see(0)

        # Load the object directly — bypasses the 150ms debounce so we know
        # exactly when it completes before deciding to reveal the window.
        try:
            self.load_object(first_oid)
        except Exception as e:
            debug_error("_startup_load_first_and_reveal", str(e))

        # If no image folder is being scanned, reveal the window now.
        # If there IS an image folder, build_image_index._notify_ui will call
        # _on_startup_ready() when the scan finishes.
        if not self.image_folder:
            self._on_startup_ready()


    def _precompute_startup_caches(self, df_reg, df_obs, df_photo):
        """
        Build all expensive in-memory caches while on the background loader thread.
        By the time _finish_open_excel runs on the main thread, everything is ready:
        - refresh_list() skips the O(N×M) problem-detection loop
        - Sorts use O(1) dict lookups instead of pandas .loc[] per item
        - Search uses a pre-built full-text index covering all registration columns
        - Card widgets get photo counts from a pre-built dict

        SAFETY: This method only writes to self._cached_* attributes which are
        only READ (never written) by the main thread until _finish_open_excel sets
        _row_cache_dirty = False. The assignment of the final dicts is atomic in CPython.
        """
        from repository import REVIEWED_COLUMN

        if df_reg is not None and "ObjectID" in df_reg.columns and df_reg.index.name != "ObjectID":
            df_reg = df_reg.set_index("ObjectID", drop=False)
        if df_obs is not None and "ObjectID" in df_obs.columns and df_obs.index.name != "ObjectID":
            df_obs = df_obs.set_index("ObjectID", drop=False)

        # 1. Full row dicts — expensive DataFrame.to_dict() done once here
        reg_dict = df_reg.to_dict(orient="index") if df_reg is not None else {}
        obs_dict = df_obs.to_dict(orient="index") if df_obs is not None else {}

        # 2. Lightweight per-column dicts used by refresh_list coloring and sorting
        reviewed_dict = {}
        genus_dict = {}
        species_dict = {}
        if df_obs is not None and REVIEWED_COLUMN in df_obs.columns:
            reviewed_dict = df_obs[REVIEWED_COLUMN].to_dict()
        if df_reg is not None and "Genus" in df_reg.columns:
            genus_dict = df_reg["Genus"].to_dict()
        if df_reg is not None and "Species" in df_reg.columns:
            species_dict = df_reg["Species"].to_dict()

        # 3. Problem cache — Vectorized generation to prevent main thread blocking
        #    Duplicates the logic from refresh_list() so that refresh_list() can skip it.
        problem_cache = {}
        problem_cols = getattr(self, "problem_columns", [])
        problem_mapping = getattr(self, "problem_to_field", {})
        include_image_problems = (self.image_mode == "folder")

        if df_reg is not None and not df_reg.empty:
            has_prob_series = pd.Series(False, index=df_reg.index)

            for p in problem_cols:
                if p == "Images_Missing":
                    continue
                if not include_image_problems and "Image" in p:
                    continue

                if p == "Other_problem":
                    if df_obs is not None and "Other_problem" in df_obs.columns:
                        vals = df_obs["Other_problem"].fillna(False).astype(bool)
                        has_prob_series |= vals.reindex(has_prob_series.index, fill_value=False)
                elif p == "Reviewed":
                    if df_obs is not None and REVIEWED_COLUMN in df_obs.columns:
                        vals = df_obs[REVIEWED_COLUMN].fillna(False).astype(bool)
                        has_prob_series |= vals.reindex(has_prob_series.index, fill_value=False)
                elif p == "Has_Images":
                    if df_obs is not None and "Images_Missing" in df_obs.columns:
                        vals = ~df_obs["Images_Missing"].fillna(False).astype(bool)
                        has_prob_series |= vals.reindex(has_prob_series.index, fill_value=True)
                    else:
                        has_prob_series |= True
                else:
                    obs_val = pd.Series(False, index=df_reg.index)
                    if df_obs is not None and p in df_obs.columns:
                        vals = df_obs[p].fillna(False).astype(bool)
                        obs_val = vals.reindex(has_prob_series.index, fill_value=False)

                    auto_val = pd.Series(False, index=df_reg.index)
                    if p in problem_mapping:
                        field = problem_mapping.get(p)
                        if field and field in df_reg.columns:
                            raw_vals = df_reg[field]
                            is_missing = raw_vals.isna() | (raw_vals.astype(str).str.strip() == "")
                            # PERFORMANCE OPTIMIZATION (Bolt): Replaced slow row-by-row .apply(self.is_unknown)
                            # with vectorized Pandas .isin() running entirely in C, speeding up load times.
                            is_unknown = raw_vals.astype(str).str.strip().str.lower().isin(["ukjent", "unknown", "?", "-"])
                            auto_val = is_missing & ~is_unknown

                    has_prob_series |= (obs_val | auto_val)

            problem_cache = has_prob_series.to_dict()

        # 4. Photo counts used by card widgets (avoids repeated value_counts() calls)
        photo_counts = {}
        if df_photo is not None and not df_photo.empty:
            photo_counts = df_photo.index.value_counts().to_dict()

        # 5. Full-text search index covering ALL registration columns (not just
        #    Genus + Species). Stored as a dictionary per ObjectID
        #    for fast substring matching and priority ranking.
        search_index = {}
        if df_reg is not None:
            df_str = df_reg.fillna("").astype(str)
            for col in df_str.columns:
                df_str[col] = df_str[col].str.strip().str.lower()

            all_cols = list(df_reg.columns)
            genus_idx = all_cols.index('Genus') if 'Genus' in all_cols else -1
            species_idx = all_cols.index('Species') if 'Species' in all_cols else -1
            family_idx = all_cols.index('Family') if 'Family' in all_cols else -1

            for row in df_str.itertuples(index=True, name=None):
                oid = row[0]
                oid_str = str(oid).lower()

                genus = row[genus_idx + 1] if genus_idx != -1 else ""
                species = row[species_idx + 1] if species_idx != -1 else ""
                family = row[family_idx + 1] if family_idx != -1 else ""

                if genus and species:
                    genus_species_str = f"{genus} {species}"
                elif genus:
                    genus_species_str = genus
                elif species:
                    genus_species_str = species
                else:
                    genus_species_str = ""

                parts = [oid_str]
                for val in row[1:]:
                    if val:
                        parts.append(val)

                search_index[oid] = {
                    "id": oid_str,
                    "genus_species": genus_species_str,
                    "family": family,
                    "all": " ".join(parts)
                }

        # Atomically assign all caches so the main thread sees a consistent state
        self._cached_reg_dict = reg_dict
        self._cached_obs_dict = obs_dict
        self._cached_reviewed_dict = reviewed_dict
        self._cached_genus_dict = genus_dict
        self._cached_species_dict = species_dict
        self._row_cache_dirty = False
        self._problem_cache = problem_cache
        self._cached_photo_counts = photo_counts
        self._search_index_cache = search_index


    def save_session(self, action):
        """Persist the current session to disk asynchronously.

        P1-A: Replaced the blocking _write_excel() call with the existing
        async path (_write_excel_async) so Ctrl+S never freezes the UI.
        U2-F: Badge and banner feedback is wired into the completion callback
        so the user always sees an immediate response and a clear outcome.
        """
        self.commit_current_object()

        if not self.validate_before_save(action):
            return

        self.log_action(action)

        output_path = self.app.output_path
        basename = os.path.basename(output_path)

        def _on_save_complete(success, err=None):
            if success:
                self.app.dirty = False
                self.update_dirty_ui()  # sets badge to "✓ Saved HH:MM"
                self.system_status.config(text=f"Saved: {basename}")
                self.show_banner(f"Database saved: {basename}", "success")
                # Clean up autosave file now that a real save succeeded
                autosave_path = self._autosave_path()
                if os.path.exists(autosave_path):
                    try:
                        os.remove(autosave_path)
                    except Exception:
                        pass
                self.build_search_index()
                self.invalidate_search_index()  # Genus/Species may have changed
            else:
                from utils import debug_error
                import traceback
                debug_error("save_session async", str(err))
                self.show_traceback_dialog(
                    "Save Error",
                    f"Failed to save to database: {err}",
                    ""
                )

        # show_saving_badge=True fires the "💾 Saving…" badge immediately
        # (before the background thread starts) for zero-latency feedback.
        self._write_excel_async(output_path, callback=_on_save_complete, show_saving_badge=True)


    def _save_anyway(self, action):
        self._skip_validation_once = True
        self.save_session(action)

    def validate_before_save(self, action="SAVE"):

        if self._skip_validation_once:
            self._skip_validation_once = False
            return True
        oid = self.app.current_object_id
        if not oid:
            return True

        issues = []

        reg = self.app.df_reg.loc[oid]
        obs = self.app.df_obs.loc[oid]

        required_fields = [
            f for f in self.problem_to_field.values()
            if f in self.app.df_reg.columns and f != "Other"
        ]
        for field in required_fields:
            if not str(reg.get(field, "")).strip():
                issues.append(f"{field} is empty")

        # Problems fortsatt aktive
        active_problems = [
            p for p in self.problem_columns
            if self.is_problem_active(oid, p)
        ]
        if active_problems:
            issues.append(f"{len(active_problems)} active problem(s)")

        # Ikke reviewed
        if not obs.get(REVIEWED_COLUMN, False):
            issues.append("Not marked as reviewed")

        # Mangler bilder (kun i folder mode)
        if self.image_mode == "folder" and obs.get("Images_Missing", False):
            issues.append("Images missing")

        if not issues:
            return True

        msg = "Validation warning: " + ", ".join(issues) + ". Click here to save anyway."
        self.show_banner(msg, "warning", duration_ms=8000, action_callback=lambda: self._save_anyway(action))

        return False


    def save_as(self):
        try:
            path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx"), ("SQLite Database", "*.db")], initialdir=__import__("config").get_last_dir("last_db_dir"))
            if not path:
                return
            __import__("config").set_last_dir("last_db_dir", path)

            # If they choose to save as Excel, perform an export instead of a database move
            if path.endswith(".xlsx"):
                if self.app.df_reg is not None:
                    self.save_session("SAVE")  # Save current state first

                sqlite_path = self.app.excel_path

                self._show_progress("Exporting to Excel...", 100)
                with self.app.df_lock:
                    df_reg_copy = self.app.df_reg.copy() if self.app.df_reg is not None else None
                    df_obs_copy = self.app.df_obs.copy() if self.app.df_obs is not None else None
                    df_log_copy = self.app.df_log.copy() if getattr(self.app, 'df_log', None) is not None else None

                def _worker():
                    try:
                        from repository import SQLiteRepository
                        SQLiteRepository.export_to_excel(
                            sqlite_path, path,
                            self.app.config,
                            df_reg=df_reg_copy, df_obs=df_obs_copy, df_log=df_log_copy
                        )
                        self.root.after(0, lambda: (
                            self._hide_progress("Export complete"),
                            self.show_banner(f"Exported to: {path}", "success")
                        ))
                    except Exception as e:
                        from utils import debug_error
                        import traceback
                        tb = traceback.format_exc()
                        debug_error("save_as_export_to_excel", str(e))
                        self.root.after(0, lambda err=str(e), t=tb: (
                            self._hide_progress("Export failed"),
                            self.show_traceback_dialog("Export Error", f"Failed to export: {err}", t)
                        ))
                import threading
                threading.Thread(target=_worker, daemon=True).start()
            else:
                self.app.output_path = path
                self.save_session("SAVE_AS")
        except Exception as e:
            from utils import debug_error
            debug_error("save_as_main_thread", str(e))
            messagebox.showerror("Save As Error", f"An error occurred while preparing to save:\n{e}")


    def save_and_close(self):
        self.save_session("SAVE_AND_CLOSE")
        self.root.destroy()


    def import_to_sqlite(self):
        excel_path = filedialog.askopenfilename(title="Select Excel File to Import", filetypes=[("Excel files", "*.xlsx")], initialdir=__import__("config").get_last_dir("last_db_dir"))
        if not excel_path: return
        __import__("config").set_last_dir("last_db_dir", excel_path)

        sqlite_path = filedialog.asksaveasfilename(title="Save as new SQLite DB", defaultextension=".db", filetypes=[("SQLite DB", "*.db")], initialdir=__import__("config").get_last_dir("last_db_dir"))
        if not sqlite_path: return
        __import__("config").set_last_dir("last_db_dir", sqlite_path)

        try:
            self._show_progress("Importing to SQLite...", 100)
            from repository import SQLiteRepository
            df_reg, df_obs, df_photo, df_log = SQLiteRepository.import_from_excel(excel_path, sqlite_path, self.app.config)

            self.app.excel_path = sqlite_path
            self.app.df_reg = df_reg
            self.app.df_obs = df_obs
            self.app.df_photo = df_photo
            self.app.df_log = df_log
            self.refresh_list()
            self._hide_progress("Import successful")
            self.show_banner("Imported and backed up successfully!", "success")
        except Exception as e:
            self._hide_progress("Import failed")
            debug_error("Import to SQLite Failed", str(e))
            import traceback
            tb = traceback.format_exc()
            self.show_traceback_dialog("Import Error", f"Failed to import: {e}", tb)


    def export_to_excel(self):
        source_path = self.app.excel_path
        if not source_path:
            messagebox.showwarning("Warning", "No active database is currently loaded to export.")
            return

        is_sqlite = source_path.endswith(".db")

        excel_path = filedialog.asksaveasfilename(
            title="Export to Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialdir=__import__("config").get_last_dir("last_db_dir")
        )
        if not excel_path:
            return
        __import__("config").set_last_dir("last_db_dir", excel_path)

        if is_sqlite:
            # Force-save current in-memory state first (fast, sync)
            from repository import SQLiteRepository
            SQLiteRepository.save_sqlite(
                source_path,
                self.app.df_reg, self.app.df_obs,
                self.app.df_photo, self.app.df_log
            )

        self._show_progress("Preparing export...", 4)

        def _on_progress(step, total, label):
            self.root.after(0, lambda s=step, t=total, l=label: (
                self.image_scan_progress.configure(value=s, maximum=t),
                self.data_status.config(text=l, foreground="gray")
            ))

        def _worker():
            try:
                from repository import SQLiteRepository
                SQLiteRepository.export_to_excel(
                    source_path if is_sqlite else None, excel_path,
                    self.app.config,
                    progress_callback=_on_progress,
                    df_reg=self.app.df_reg,
                    df_obs=self.app.df_obs,
                    df_log=self.app.df_log
                )
                self.root.after(0, lambda: (
                    self._hide_progress("Export complete"),
                    self.show_banner(f"Exported to: {excel_path}", "success")
                ))
            except Exception as e:
                debug_error("export_to_excel", str(e))
                import traceback
                tb = traceback.format_exc()
                self.root.after(0, lambda err=str(e), t=tb: (
                    self._hide_progress("Export failed"),
                    self.show_traceback_dialog("Export Error", f"Failed to export: {err}", t)
                ))

        threading.Thread(target=_worker, daemon=True).start()
