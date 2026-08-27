import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
from datetime import datetime

from models import AppState
import config
from repository import ExcelRepository, SQLiteRepository
from utils import debug_error
from ui.mobile_panel import MobilePanel


class MobileHostApp:
    """Standalone mobile-host entry point.

    Starts as a lightweight full process (bypassing the heavy desktop UI).
    Embeds MobilePanel for all shared UI/server logic; this class only
    handles what is unique to the standalone context:
      - Database loading from disk
      - Autosave loop
      - Save-and-exit lifecycle (prompt + disk write + sys.exit)
    """

    def __init__(self, root=None, app=None, file_path=None):
        if root is not None:
            self.root = root
            self.root.deiconify()
        else:
            self.root = tk.Tk()

        self.root.title("Arbor Mobile Companion")
        self.root.geometry("540x630")
        self.root.minsize(500, 590)
        self.root.configure(bg="#ffffff")

        self.app = app if app is not None else AppState()
        self.port = 5055
        self.autosave_job = None
        self.panel = None

        if self.app.df_reg is None or self.app.df_reg.empty:
            self._init_database(file_path)
        else:
            if not self.app.excel_path and file_path:
                self.app.excel_path = os.path.abspath(file_path)
                self.app.output_path = self.app.excel_path

        self._build_ui()
        self._schedule_autosave()

    # ------------------------------------------------------------------
    # Database loading
    # ------------------------------------------------------------------

    def _init_database(self, file_path):
        if not file_path or not os.path.exists(file_path):
            prefs = config.load_prefs()
            last_file = prefs.get("last_opened_file")
            if last_file and os.path.exists(last_file):
                file_path = last_file
            else:
                self.root.withdraw()
                file_path = filedialog.askopenfilename(
                    title="Select Database for Mobile Session",
                    filetypes=[
                        ("Database Files", "*.xlsx *.xls *.db *.sqlite"),
                        ("All Files", "*.*"),
                    ],
                )
                self.root.deiconify()

        if not file_path or not os.path.exists(file_path):
            messagebox.showerror("No Database", "No database selected. Exiting mobile host.")
            sys.exit(0)

        self.app.excel_path = os.path.abspath(file_path)
        self.app.output_path = self.app.excel_path

        # Detect config from loaded prefs or default to first available
        prefs = config.load_prefs()
        saved_config_name = prefs.get("last_config_name")
        if saved_config_name and saved_config_name in config.DATABASE_CONFIGS:
            self.app.config_name = saved_config_name
        else:
            self.app.config_name = next(iter(config.DATABASE_CONFIGS))
        self.app.config = config.DATABASE_CONFIGS[self.app.config_name]

        try:
            if file_path.endswith((".db", ".sqlite", ".sqlite3")):
                df_reg, df_obs, df_photo, df_log = SQLiteRepository.load_sqlite(
                    self.app.excel_path, self.app.config
                )
            else:
                df_reg, df_obs, df_photo, df_log = ExcelRepository.load_excel(
                    self.app.excel_path, self.app.config
                )

            for df, name in ((df_reg, "ObjectID"), (df_obs, "ObjectID"), (df_photo, "ObjectID")):
                if name in df.columns:
                    df[name] = df[name].astype(str).str.strip()
                    df.set_index(name, inplace=True)

            self.app.df_reg = df_reg
            self.app.df_obs = df_obs
            self.app.df_photo = df_photo
            self.app.df_log = df_log
            self.app._log_records = (
                df_log.to_dict(orient="records")
                if (df_log is not None and not df_log.empty)
                else []
            )
            self.app.dirty = False

            prefs["last_opened_file"] = self.app.excel_path
            config.save_prefs(prefs)
        except Exception as e:
            debug_error("MobileHostApp DB Load Error", str(e))
            messagebox.showerror("Load Error", f"Failed to load database: {e}")
            sys.exit(1)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.panel = MobilePanel(
            parent=self.root,
            app_state=self.app,
            root_tk=self.root,
            port=self.port,
            on_end_session=self._end_session,
            on_edit=self._on_mobile_edit,
        )
        self.panel.start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------------
    # Autosave
    # ------------------------------------------------------------------

    def _schedule_autosave(self):
        def tick():
            if self.app.dirty:
                try:
                    with self.app.df_lock:
                        df_reg_copy = self.app.df_reg.copy() if self.app.df_reg is not None else None
                        df_obs_copy = self.app.df_obs.copy() if self.app.df_obs is not None else None
                        df_photo_copy = self.app.df_photo.copy() if self.app.df_photo is not None else None
                        df_log_copy = (
                            pd.DataFrame(self.app._log_records)
                            if (hasattr(self.app, "_log_records") and self.app._log_records)
                            else (
                                self.app.df_log.copy()
                                if self.app.df_log is not None
                                else pd.DataFrame()
                            )
                        )
                        config_copy = self.app.config
                        excel_path = self.app.excel_path

                    def write_backup():
                        try:
                            if excel_path.endswith((".db", ".sqlite", ".sqlite3")):
                                backup_path = excel_path + ".autosave.db"
                                SQLiteRepository.save_sqlite(
                                    backup_path, df_reg_copy, df_obs_copy, df_photo_copy, df_log_copy
                                )
                            else:
                                backup_path = excel_path + ".autosave"
                                SQLiteRepository.export_to_excel(
                                    sqlite_path=None,
                                    excel_path=backup_path,
                                    config=config_copy,
                                    df_reg=df_reg_copy,
                                    df_obs=df_obs_copy,
                                    df_log=df_log_copy,
                                    df_photo=df_photo_copy,
                                )
                            if self.panel:
                                self.panel.log("Background autosave completed")
                            if self.panel and self.panel.server:
                                ts = datetime.now().isoformat()
                                self.panel.server.broadcast_event(
                                    "autosave_completed", {"timestamp": ts}
                                )
                        except Exception as e:
                            debug_error("MobileHost autosave worker", str(e))

                    threading.Thread(target=write_backup, daemon=True).start()
                except Exception as e:
                    debug_error("MobileHost autosave", str(e))

            self.autosave_job = self.root.after(180000, tick)

        self.autosave_job = self.root.after(180000, tick)

    # ------------------------------------------------------------------
    # Session end
    # ------------------------------------------------------------------

    def _end_session(self):
        """Called by MobilePanel when the user clicks 'End Mobile Session'."""
        self._save_to_disk()

    def _save_to_disk(self):
        try:
            with self.app.df_lock:
                df_reg_copy = self.app.df_reg.copy() if self.app.df_reg is not None else None
                df_obs_copy = self.app.df_obs.copy() if self.app.df_obs is not None else None
                df_photo_copy = self.app.df_photo.copy() if self.app.df_photo is not None else None
                df_log_copy = (
                    pd.DataFrame(self.app._log_records)
                    if (hasattr(self.app, "_log_records") and self.app._log_records)
                    else (
                        self.app.df_log.copy()
                        if self.app.df_log is not None
                        else pd.DataFrame()
                    )
                )
                config_copy = self.app.config
                excel_path = self.app.excel_path

            if excel_path.endswith((".db", ".sqlite", ".sqlite3")):
                SQLiteRepository.save_sqlite(
                    excel_path, df_reg_copy, df_obs_copy, df_photo_copy, df_log_copy
                )
            else:
                SQLiteRepository.export_to_excel(
                    sqlite_path=None,
                    excel_path=excel_path,
                    config=config_copy,
                    df_reg=df_reg_copy,
                    df_obs=df_obs_copy,
                    df_log=df_log_copy,
                    df_photo=df_photo_copy,
                )
            messagebox.showinfo("Saved", "All changes have been successfully saved to database.")
        except Exception as e:
            debug_error("MobileHost Save Error", str(e))
            messagebox.showerror("Save Error", f"Failed to save changes: {e}")
            return

        self.root.destroy()
        sys.exit(0)

    def on_close(self):
        if self.app.dirty:
            res = messagebox.askyesnocancel("Unsaved Changes", "Save changes to database before closing?")
            if res is None:
                return
            if res:
                if self.panel:
                    self.panel.stop()
                self._save_to_disk()
                return

        if self.panel:
            self.panel.stop()
        self.root.destroy()
        sys.exit(0)

    def _on_mobile_edit(self, oid, summary):
        # Expose server instance so if the desktop UI later opens MobileDialog
        # it can reuse the same server (only relevant in combined-process launch)
        pass

    def run(self):
        self.root.mainloop()
