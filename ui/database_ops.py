import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from datetime import datetime
import pandas as pd
import config
from utils import debug_error
from repository import ExcelRepository, REVIEWED_COLUMN

class DatabaseOpsMixin:
    def _write_excel(self, path):
        """Save the current in-memory state to Excel directly."""
        for col in self.problem_columns:
            if col not in self.app.df_obs.columns:
                self.app.df_obs[col] = False

        from repository import SQLiteRepository
        SQLiteRepository.export_to_excel(
            sqlite_path=None,
            excel_path=path,
            config=self.app.config,
            df_reg=self.app.df_reg,
            df_obs=self.app.df_obs,
            df_log=self.app.df_log
        )


    def _write_excel_async(self, path, callback=None):
        """Save the current in-memory state to Excel in a background thread."""
        if getattr(self, '_save_in_progress', False):
            # Skip — a background save is already running
            return

        self._save_in_progress = True
        self.set_status_badge("autosaved", "⏳ Saving…")

        try:
            for col in self.problem_columns:
                if col not in self.app.df_obs.columns:
                    self.app.df_obs[col] = False

            # Create copies of dataframes to prevent write-modification conflicts
            df_reg_copy = self.app.df_reg.copy() if self.app.df_reg is not None else None
            df_obs_copy = self.app.df_obs.copy() if self.app.df_obs is not None else None
            df_log_copy = self.app.df_log.copy() if getattr(self.app, 'df_log', None) is not None else None
        except Exception as e:
            self._save_in_progress = False
            self.set_status_badge("autosaved", "Save Error")
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
                self.root.after(0, lambda: _on_done(False, str(e)))

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

            # PERFORMANCE OPTIMIZATION (Bolt): Read via standard library pickle if it's a binary autosave file.
            if path.endswith(".pkl"):
                import pickle
                with open(path, "rb") as f:
                    data = pickle.load(f)
                df_reg = data["df_reg"]
                df_obs = data["df_obs"]
                df_photo = data["df_photo"]
                df_log = data["df_log"]
            else:
                df_reg, df_obs, df_photo, df_log = ExcelRepository.load_excel(path, self.app.config)

            self.root.after(0, lambda: self.image_scan_progress.configure(value=60))

            base, _ = os.path.splitext(path)
            # Ensure the output path uses .xlsx even if we loaded from a .pkl autosave
            base_xlsx = base.replace(".autosave", "")
            output_path = f"{base_xlsx}_updated_{datetime.now():%Y%m%d_%H%M%S}.xlsx"


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
            self.root.after(0, lambda: self.show_traceback_dialog("Excel Load Error", f"An error occurred while loading the Excel/DB file: {e}", tb))


    def _finish_open_excel(self, path, output_path, df_reg, df_obs, df_photo, df_log):
        # PERFORMANCE OPTIMIZATION (Bolt): Reconstruct the original Excel path as active path if loaded from an autosave
        if ".autosave" in path:
            orig_path = path.replace(".autosave.pkl", ".xlsx").replace(".autosave.xlsx", ".xlsx")
            if os.path.exists(orig_path):
                path = orig_path

        # If df_reg has index name already set to ObjectID, we don't have duplicated column
        if "ObjectID" in df_reg.columns:
            dupes = df_reg[df_reg["ObjectID"].duplicated()]["ObjectID"].unique()
        else:
            dupes = []

        if len(dupes) > 0:
            messagebox.showwarning(
                "Duplicate ObjectIDs",
                f"{len(dupes)} duplicate ObjectID(s) found.\n"
                "Only the first occurrence will be kept.\n\n"
                + ", ".join(dupes[:10])
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


        self.build_search_index()

        if self.app.active_object_ids:
            self.root.after(0, self._select_first_object)

        self.initializing = False
        self.app.dirty = False
        self.update_dirty_ui()
        self.update_review_progress()
        self.update_object_count()



        self.system_status.config(text="Excel loaded - loading images...")
        self.image_scan_progress.configure(value=70)

        self.start_autosave_loop()
        self._check_and_prompt_autosave(path)

        if self.image_folder:
            threading.Thread(
                target=self.build_image_index,
                args=(self.image_folder,),
                daemon=True
            ).start()
        else:
            self.image_scan_progress.configure(value=100)
            self._hide_progress("Ready")


        self.root.after(50, self.object_list.focus_set)
        self.root.title(f"arbor {self.app.config_name}")


    def save_session(self, action):

            self.commit_current_object()

            if not self.validate_before_save():
                return

            self.log_action(action)

            try:
                self._write_excel(self.app.output_path)
            except Exception as e:
                from utils import debug_error
                import traceback
                tb = traceback.format_exc()
                debug_error("save_session", str(e))
                self.show_traceback_dialog("Save Error", f"Failed to save to database: {e}", tb)
                return

            self.app.dirty = False
            self.update_dirty_ui()
            self.system_status.config(text=f"Saved: {os.path.basename(self.app.output_path)}")
            self.show_banner(f"Database saved: {os.path.basename(self.app.output_path)}", "success")
            autosave_path = self._autosave_path()
            if os.path.exists(autosave_path):
                try:
                    os.remove(autosave_path)
                except Exception:
                    pass
            self.build_search_index()
            self.invalidate_search_index()  # Genus/Species may have changed


    def validate_before_save(self):

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

        msg = "Before saving:\n\n" + "\n".join(f"- {issue}" for issue in issues)
        msg += "\n\nDo you want to continue?"

        result = messagebox.askyesno("Validation warning", msg)

        if result:
            self._skip_validation_once = True

        return result


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
