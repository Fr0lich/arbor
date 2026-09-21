"""
ui/tutorials/sandbox_manager.py

Manages entering and exiting isolated in-memory sandbox environments for tutorials.
Ensures zero mutations to user files by snapshotting existing session state and
restoring it upon tutorial exit or completion.
"""

import copy
import pandas as pd
import config
from utils import debug_error


class SandboxManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SandboxManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.initialized = True
            self.is_sandboxed = False
            self.snapshot = None

    def enter_sandbox(self, ui, mock_type="review"):
        """Snapshots the active state and loads isolated mock data."""
        if self.is_sandboxed:
            return

        try:
            # 1. Snapshot existing session state
            app = ui.app
            self.snapshot = {
                "config": copy.deepcopy(app.config) if app.config else None,
                "config_name": app.config_name,
                "excel_path": app.excel_path,
                "output_path": app.output_path,
                "df_reg": app.df_reg.copy() if app.df_reg is not None else None,
                "df_obs": app.df_obs.copy() if app.df_obs is not None else None,
                "df_photo": app.df_photo.copy() if app.df_photo is not None else None,
                "df_log": app.df_log.copy() if app.df_log is not None else None,
                "df_unvalidated": app.df_unvalidated.copy() if app.df_unvalidated is not None else None,
                "historical_dbs": copy.deepcopy(app.historical_dbs),
                "dirty": app.dirty,
                "current_object_id": app.current_object_id,
            }

            # 2. Build mock DataFrames according to standard DB config
            cfg = app.config or config.DATABASE_CONFIGS.get("Standard", list(config.DATABASE_CONFIGS.values())[0])
            app.config = cfg

            mock_reg, mock_obs, mock_photo, mock_log, mock_unval, mock_hist = self._create_mock_datasets(mock_type)

            self.is_sandboxed = True

            # 3. Apply mock dataset in UI
            ui._precompute_startup_caches(mock_reg, mock_obs, mock_photo)
            ui._finish_open_excel(
                "[Tutorial Sandbox]",
                "[Tutorial Sandbox]",
                mock_reg,
                mock_obs,
                mock_photo,
                mock_log,
                mock_unval
            )

            # Inject mock historical discrepancy data if needed
            if mock_hist:
                app.historical_dbs = mock_hist
                if hasattr(ui, "_history_cache"):
                    ui._history_cache.clear()

            # Select first mock specimen
            if mock_reg is not None and not mock_reg.empty:
                first_id = str(mock_reg.index[0])
                ui.current_id = first_id
                ui.app.current_object_id = first_id
                if hasattr(ui, "object_list"):
                    try:
                        ui.object_list.select_by_id(first_id)
                    except Exception:
                        pass
                if hasattr(ui, "load_object"):
                    try:
                        ui.load_object(first_id)
                    except Exception:
                        pass
                if hasattr(ui, "update_history_indicator"):
                    try:
                        ui.update_history_indicator(first_id)
                    except Exception:
                        pass

        except Exception as e:
            debug_error("SandboxManager.enter_sandbox", str(e))

    def exit_sandbox(self, ui):
        """Restores the original workspace state from snapshot."""
        if not self.is_sandboxed:
            return

        try:
            self.is_sandboxed = False
            if not self.snapshot:
                return

            snap = self.snapshot
            self.snapshot = None

            app = ui.app
            app.config = snap["config"]
            app.config_name = snap["config_name"]
            app.historical_dbs = snap["historical_dbs"]
            app.dirty = snap["dirty"]

            if snap["df_reg"] is not None and snap["df_obs"] is not None:
                ui._precompute_startup_caches(snap["df_reg"], snap["df_obs"], snap["df_photo"])
                ui._finish_open_excel(
                    snap["excel_path"] or "",
                    snap["output_path"] or "",
                    snap["df_reg"],
                    snap["df_obs"],
                    snap["df_photo"],
                    snap["df_log"],
                    snap["df_unvalidated"]
                )
                if snap["current_object_id"]:
                    oid = snap["current_object_id"]
                    ui.current_id = oid
                    ui.app.current_object_id = oid
                    if hasattr(ui, "object_list"):
                        try:
                            ui.object_list.select_by_id(oid)
                        except Exception:
                            pass
                    if hasattr(ui, "load_object"):
                        try:
                            ui.load_object(oid)
                        except Exception:
                            pass

        except Exception as e:
            debug_error("SandboxManager.exit_sandbox", str(e))

    def _create_mock_datasets(self, mock_type):
        """Creates sample in-memory DataFrames for tutorials."""
        reg_data = [
            {
                "ObjectID": "1001",
                "Genus": "Betula",
                "Species": "nana",
                "Taxon": "Betula nana",
                "Family": "Betulaceae",
                "Author": "L.",
                "Collector": "E. Dahl",
                "CollectorNumber": "142",
                "Day": "15",
                "Month": "07",
                "Year": "1965",
                "Locality": "Dovrefjell, Kongsvoll",
                "Country": "Norway",
                "Reviewed": False,
                "Reviewed_By": "",
                "Reviewed_At": "",
                "Problem_Flags": ""
            },
            {
                "ObjectID": "1002",
                "Genus": "Pinus",
                "Species": "sylvestris",
                "Taxon": "Pinus sylvestris",
                "Family": "Pinaceae",
                "Author": "L.",
                "Collector": "J. M. Norman",
                "CollectorNumber": "89",
                "Day": "04",
                "Month": "08",
                "Year": "1882",
                "Locality": "Alvdal, Hedmark",
                "Country": "Norway",
                "Reviewed": False,
                "Reviewed_By": "",
                "Reviewed_At": "",
                "Problem_Flags": "Taxon_Mismatch"
            },
            {
                "ObjectID": "1003",
                "Genus": "Salix",
                "Species": "herbacea",
                "Taxon": "Salix herbacea",
                "Family": "Salicaceae",
                "Author": "L.",
                "Collector": "R. F. Fristedt",
                "CollectorNumber": "304",
                "Day": "22",
                "Month": "06",
                "Year": "1853",
                "Locality": "Jotunheimen",
                "Country": "Norway",
                "Reviewed": True,
                "Reviewed_By": "Curator",
                "Reviewed_At": "2026-01-10 14:30:00",
                "Problem_Flags": ""
            }
        ]

        obs_data = [
            {
                "ObjectID": "1001",
                "Genus_Problem": False,
                "Species_Problem": False,
                "Taxon_Mismatch": False,
                "Coordinate_Problem": False,
                "Unidentified": False
            },
            {
                "ObjectID": "1002",
                "Genus_Problem": False,
                "Species_Problem": False,
                "Taxon_Mismatch": True,
                "Coordinate_Problem": False,
                "Unidentified": False
            },
            {
                "ObjectID": "1003",
                "Genus_Problem": False,
                "Species_Problem": False,
                "Taxon_Mismatch": False,
                "Coordinate_Problem": False,
                "Unidentified": False
            }
        ]

        df_reg = pd.DataFrame(reg_data).set_index("ObjectID", drop=False)
        df_obs = pd.DataFrame(obs_data).set_index("ObjectID", drop=False)
        df_photo = pd.DataFrame(columns=["ObjectID", "PhotoURL", "PhotoType"])
        df_log = pd.DataFrame(columns=["Timestamp", "ObjectID", "Action", "User"])
        df_unval = pd.DataFrame()

        mock_hist = []
        if mock_type == "discrepancy":
            # Add historical discrepancies for 1001
            hist_books = pd.DataFrame([
                {
                    "ObjectID": "1001",
                    "Taxon": "Betula pendula",
                    "Author": "Roth",
                    "Family": "Betulaceae",
                    "Locality": "Dovre, Kongsvold",
                    "Year": "1965"
                }
            ]).set_index("ObjectID", drop=False)

            mock_hist.append({
                "name": "Historical Ledger Book 1",
                "df": hist_books
            })

        return df_reg, df_obs, df_photo, df_log, df_unval, mock_hist
