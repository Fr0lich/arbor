import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from config import AUTOSAVE_INTERVAL_MS, AUTOSAVE_SUFFIX, sc
from utils import debug_error

class AutosaveMixin:
    # open_autosave_settings has been replaced by the unified open_settings_window in main_window.py


    def _write_pickle_async(self, path, callback=None):
        """Save the current in-memory state to a pickle file in a background thread."""
        if getattr(self, '_save_in_progress', False):
            return

        self._save_in_progress = True
        self.set_status_badge("autosaved", "⏳ Saving…")

        # P1-B: Hold the data lock for the minimum time needed to snapshot
        # all four DataFrames.  The lock is an RLock so the main thread can
        # still acquire it recursively (e.g. during commit_current_object).
        try:
            with self.app.df_lock:
                df_reg_copy   = self.app.df_reg.copy()   if self.app.df_reg   is not None else None
                df_obs_copy   = self.app.df_obs.copy()   if self.app.df_obs   is not None else None
                df_photo_copy = self.app.df_photo.copy() if self.app.df_photo is not None else None
                df_log_copy   = self.app.df_log.copy()   if getattr(self.app, 'df_log', None) is not None else None
        except Exception as e:
            self._save_in_progress = False
            self.set_status_badge("autosaved", "Save Error")
            if callback:
                callback(False, str(e))
            return

        def save_worker():
            try:
                import json
                data = {
                    "df_reg": df_reg_copy,
                    "df_obs": df_obs_copy,
                    "df_photo": df_photo_copy,
                    "df_log": df_log_copy
                }
                json_data = {
                    k: v.to_dict(orient="split") if v is not None else None
                    for k, v in data.items()
                }
                # Write to tmp first then replace for atomic safety
                tmp_path = path + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(json_data, f)
                os.replace(tmp_path, path)
                self.root.after(0, lambda: callback(True, None) if callback else None)
            except Exception as e:
                from utils import debug_error
                debug_error("_write_autosave_async worker", str(e))
                err_msg = str(e)
                self.root.after(0, lambda err=err_msg: callback(False, err) if callback else None)
            finally:
                self.root.after(0, lambda: setattr(self, '_save_in_progress', False))

        import threading
        threading.Thread(target=save_worker, daemon=True).start()


    def start_autosave_loop(self):
        if self._autosave_job is not None:
            return

        self._schedule_autosave()


    def _schedule_autosave(self):
        # Always cancel any existing job before scheduling to prevent stale timer leaks
        if self._autosave_job is not None:
            try:
                self.root.after_cancel(self._autosave_job)
            except Exception:
                pass
            self._autosave_job = None
        self._autosave_job = self.root.after(
            AUTOSAVE_INTERVAL_MS,
            self._autosave_tick
        )


    def _autosave_tick(self):
        try:
            if getattr(self, '_save_in_progress', False):
                # Background save still running — skip this tick
                return
            if self.app.dirty and self.app.excel_path:
                current_dirty = self.app.dirty
                self.commit_current_object()
                autosave_path = self._autosave_path()

                def on_autosave_complete(success, err=None):
                    if success:
                        ts = datetime.now().strftime("%H:%M:%S")
                        self.set_status_badge("autosaved", f"Autosaved ({ts})")
                        # U2-F: Brief non-blocking banner so the user has clear
                        # confirmation their work is safe, even in low-light conditions.
                        self.show_banner("💾 Autosaved", "info", duration_ms=2000)
                    else:
                        self.set_status_badge("autosaved", "Autosave failed")
                        self.show_banner("⚠ Autosave failed — check disk space", "error", duration_ms=6000)

                if autosave_path.endswith(".json"):
                    self._write_pickle_async(autosave_path, on_autosave_complete)
                else:
                    self._write_excel_async(autosave_path, on_autosave_complete)

                self.app.dirty = current_dirty
        except Exception as e:
            debug_error("_autosave_tick", str(e))
            self.set_status_badge("error", "Autosave failed")
        finally:
            self._schedule_autosave()


    def _autosave_path(self):
        base, _ = os.path.splitext(self.app.excel_path)
        base = base.replace(".autosave", "")
        return base + AUTOSAVE_SUFFIX


    def _autosave_archive_dir(self):
        """Returns the .autosave_archives directory path next to the Excel file."""
        excel_dir = os.path.dirname(self.app.excel_path)
        return os.path.join(excel_dir, ".autosave_archives")


    def _archive_autosave(self, autosave_path):
        """Move active autosave to archive dir with timestamp suffix."""
        try:
            archive_dir = self._autosave_archive_dir()
            os.makedirs(archive_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            base, ext = os.path.splitext(os.path.basename(autosave_path))
            dest = os.path.join(archive_dir, f"{base}_{ts}{ext}")
            import shutil
            shutil.move(autosave_path, dest)
        except Exception as e:
            from utils import debug_error
            debug_error("_archive_autosave", str(e))


    def _check_and_prompt_autosave(self, original_path):
        """After DB loads, check for a newer autosave and prompt to restore."""
        if not self.app.excel_path:
            return
        autosave_path = self._autosave_path()
        # Backward-compatible fallback check for legacy excel autosave
        if not os.path.exists(autosave_path):
            alt_path = autosave_path.replace(".json", ".xlsx")
            if os.path.exists(alt_path):
                autosave_path = alt_path
            else:
                self._check_archive_clutter()
                return
        try:
            orig_mtime = os.path.getmtime(original_path)
            auto_mtime = os.path.getmtime(autosave_path)
        except Exception:
            return
        if auto_mtime <= orig_mtime:
            # Autosave is not newer — clean it up silently
            try:
                os.remove(autosave_path)
            except Exception:
                pass
            self._check_archive_clutter()
            return

        auto_ts = datetime.fromtimestamp(auto_mtime).strftime("%Y-%m-%d %H:%M:%S")
        restore = messagebox.askyesno(
            "Autosave found",
            f"An autosave from {auto_ts} was found for this database.\n\n"
            "It may contain unsaved work from your last session.\n\n"
            "Restore it now?",
            parent=self.root
        )
        if restore:
            self._restore_autosave(autosave_path, original_path)
        else:
            self._archive_autosave(autosave_path)
        self._check_archive_clutter()


    def _restore_autosave(self, autosave_path, original_path):
        """Load data from the autosave file into the current session."""
        try:
            # Support restoring both the secure json autosave and legacy Excel autosave.
            if autosave_path.endswith(".json"):
                import json
                import pandas as pd
                import io
                with open(autosave_path, "r") as f:
                    data = json.load(f)

                def load_df(key):
                    val = data.get(key)
                    if val is None:
                        return None
                    if isinstance(val, str):
                        if '"schema"' in val:
                            return pd.read_json(io.StringIO(val), orient="table")
                        return pd.read_json(io.StringIO(val), orient="split")
                    elif isinstance(val, dict):
                        if "schema" in val:
                            return pd.read_json(io.StringIO(json.dumps(val)), orient="table")
                        elif "columns" in val and "data" in val:
                            return pd.DataFrame(data=val["data"], index=val.get("index"), columns=val["columns"])
                    return None

                df_reg = load_df("df_reg")
                df_obs = load_df("df_obs")
                df_photo = load_df("df_photo")
                df_log = load_df("df_log")
            else:
                from repository import ExcelRepository
                df_reg, df_obs, df_photo, df_log = ExcelRepository.load_excel(autosave_path, self.app.config)

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
            self.app.active_object_ids = list(self.app.df_reg.index)
            self.refresh_list()
            self.app.dirty = True
            self.update_dirty_ui()
            # Remove the autosave after successful restore
            try:
                os.remove(autosave_path)
            except Exception:
                pass
            self.show_banner("Autosave restored. Remember to save.", "warning")
        except Exception as e:
            from utils import debug_error
            debug_error("_restore_autosave", str(e))
            messagebox.showerror("Restore failed", f"Could not restore autosave:\n{e}", parent=self.root)


    def _check_archive_clutter(self):
        """If more than 10 archived autosaves exist, prompt the user."""
        if not self.app.excel_path:
            return
        archive_dir = self._autosave_archive_dir()
        if not os.path.isdir(archive_dir):
            return
        archives = sorted(
            [f for f in os.listdir(archive_dir) if f.endswith(".xlsx") or f.endswith(".json")],
            key=lambda f: os.path.getmtime(os.path.join(archive_dir, f)),
            reverse=True
        )
        import config as _app_cfg
        advanced_prefs = _app_cfg.load_prefs().get("advanced", {})
        limit = int(advanced_prefs.get("autosave_archive_limit", "10"))
        if len(archives) > limit:
            self.root.after(500, lambda: self._prompt_archive_clutter(archive_dir, archives))


    def _prompt_archive_clutter(self, archive_dir, archives):
        msg = (
            f"You have {len(archives)} archived autosaves stored.\n\n"
            "Would you like to review and clean them up?\n"
            "(You can also access them via File → Restore earlier autosave...)"
        )
        if messagebox.askyesno("Autosave archive full", msg, parent=self.root):
            self.open_autosave_manager()


    def open_autosave_manager(self):
        """Open a window to browse, restore, or delete archived autosaves."""
        if not self.app.excel_path:
            messagebox.showinfo("No database", "Open a database first.", parent=self.root)
            return
        archive_dir = self._autosave_archive_dir()
        if not os.path.isdir(archive_dir):
            messagebox.showinfo("No archives", "No archived autosaves found.", parent=self.root)
            return
        archives = sorted(
            [f for f in os.listdir(archive_dir) if f.endswith(".xlsx") or f.endswith(".json")],
            key=lambda f: os.path.getmtime(os.path.join(archive_dir, f)),
            reverse=True
        )
        if not archives:
            messagebox.showinfo("No archives", "No archived autosaves found.", parent=self.root)
            return

        win = tk.Toplevel(self.root)
        win.title("Autosave Archive Manager")
        win.geometry("520x380")
        win.grab_set()

        ttk.Label(win, text="Archived Autosaves", font=("Segoe UI", sc(11), "bold")).pack(anchor="w", padx=15, pady=(12, 4))
        ttk.Label(win, text="Select a file to restore or delete it.", font=("Segoe UI", sc(9))).pack(anchor="w", padx=15, pady=(0, 8))

        list_frame = ttk.Frame(win)
        list_frame.pack(fill="both", expand=True, padx=15, pady=4)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        lb = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, selectmode="single", font=("Segoe UI", sc(9)))
        lb.pack(fill="both", expand=True)
        scrollbar.config(command=lb.yview)

        for fname in archives:
            lb.insert(tk.END, fname)

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill="x", padx=15, pady=10)

        def restore_selected():
            sel = lb.curselection()
            if not sel:
                return
            fname = archives[sel[0]]
            path = os.path.join(archive_dir, fname)
            if messagebox.askyesno("Restore", f"Restore '{fname}'?\nThis will replace the current in-memory data.", parent=win):
                win.destroy()
                self._restore_autosave(path, self.app.excel_path)

        def delete_selected():
            sel = lb.curselection()
            if not sel:
                return
            fname = archives[sel[0]]
            path = os.path.join(archive_dir, fname)
            if messagebox.askyesno("Delete", f"Permanently delete '{fname}'?", parent=win):
                try:
                    os.remove(path)
                    archives.pop(sel[0])
                    lb.delete(sel[0])
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=win)

        def delete_all():
            if messagebox.askyesno("Delete all", f"Delete all {len(archives)} archived autosaves?", parent=win):
                for fname in list(archives):
                    try:
                        os.remove(os.path.join(archive_dir, fname))
                    except Exception:
                        pass
                win.destroy()

        ttk.Button(btn_frame, text="Restore selected", command=restore_selected).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Delete selected", command=delete_selected).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Delete all", command=delete_all).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side="right", padx=4)
