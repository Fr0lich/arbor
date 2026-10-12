"""ui_qt/new_database_wizard.py - New Database Setup Wizard Controller for Arbor.

Wraps 'qt designer/new_database_wizard.ui' (NewDatabaseWizard subclassing QWizard).
Multi-step guided setup:
- Step 1: Choose Schema Profile (populated from config.DATABASE_CONFIGS)
- Step 2: Collection Name & Destination Path (validates filename and path)
- Initial database initialization (df_reg, df_obs, df_photo, df_log) and Excel persistence.
"""
from __future__ import annotations

import getpass
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QListWidgetItem,
    QMessageBox,
    QWidget,
    QWizard,
)

import config
from models import AppState
from repository import ExcelRepository, REVIEWED_COLUMN, _normalise_log_dataframe
from ui_qt.loader import load_ui


class QtNewDatabaseWizard(QWizard):
    """Controller for the multi-step New Database Creation Wizard."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        app_state: Optional[AppState] = None,
        on_completed: Optional[Callable[[str, str], None]] = None,
    ):
        super().__init__(parent)
        self.app = app_state or AppState()
        self.on_completed = on_completed

        # Load declarative Qt Designer UI (Root is QWizard)
        self.wizard: QWizard = load_ui("new_database_wizard.ui")
        if parent:
            self.wizard.setParent(parent, Qt.Dialog)

        self._populate_profiles()
        self._connect_signals()

    def _populate_profiles(self) -> None:
        """Populate list_templates with available database configs."""
        if not hasattr(self.wizard, "list_templates"):
            return

        list_widget = self.wizard.list_templates
        list_widget.clear()

        profiles = list(config.DATABASE_CONFIGS.keys()) if config.DATABASE_CONFIGS else ["Default"]
        for p in profiles:
            item = QListWidgetItem(p)
            list_widget.addItem(item)

        if list_widget.count() > 0:
            list_widget.setCurrentRow(0)

    def _connect_signals(self) -> None:
        """Connect wizard buttons and browsing slots."""
        if hasattr(self.wizard, "btn_browse_save"):
            self.wizard.btn_browse_save.clicked.connect(self.browse_save_path)

        # Connect finish slot on QWizard accepted
        self.wizard.accepted.connect(self._on_wizard_accepted)

    def browse_save_path(self) -> None:
        """Open file dialog for choosing new database destination path."""
        last_dir = config.get_last_dir("last_db_dir") or ""
        chosen, _ = QFileDialog.getSaveFileName(
            self.wizard,
            "Save New Database",
            last_dir or "new_botanical_collection.xlsx",
            "Excel Files (*.xlsx);;SQLite Database (*.db *.sqlite);;All Files (*.*)",
        )
        if chosen:
            if hasattr(self.wizard, "input_save_path"):
                self.wizard.input_save_path.setText(chosen)
            config.set_last_dir("last_db_dir", os.path.dirname(chosen))

    def _get_selected_profile(self) -> str:
        """Return currently selected profile name."""
        if hasattr(self.wizard, "list_templates"):
            item = self.wizard.list_templates.currentItem()
            if item:
                return item.text().strip()
        return next(iter(config.DATABASE_CONFIGS)) if config.DATABASE_CONFIGS else "Default"

    def _on_wizard_accepted(self) -> None:
        """Validate and construct new database files when wizard completes."""
        save_path = self.wizard.input_save_path.text().strip() if hasattr(self.wizard, "input_save_path") else ""
        if not save_path:
            QMessageBox.critical(self.wizard, "Invalid Path", "Please specify a valid destination file path.")
            return

        collection_name = self.wizard.input_collection_name.text().strip() if hasattr(self.wizard, "input_collection_name") else "New Collection"
        profile_name = self._get_selected_profile()
        cfg = config.DATABASE_CONFIGS.get(profile_name, {})

        try:
            # Build initial DataFrames according to schema
            reg_fields = ["ObjectID"]
            reg_sections = cfg.get("ui_sections", {}).get("registration", [])
            reg_fields.extend([f["name"] for f in reg_sections if f.get("name")])

            loc_fields = ["Stored as", "Building", "Floor", "Room", "Cabinet", "Shelf"]
            loc_sections = cfg.get("ui_sections", {}).get("location", [])
            if loc_sections:
                loc_fields = [f["name"] for f in loc_sections if f.get("name")]

            prob_fields = [REVIEWED_COLUMN]
            prob_sections = cfg.get("ui_sections", {}).get("problems", [])
            prob_fields.extend([p["name"] for p in prob_sections if p.get("name")])

            # Deduplicate fields
            reg_fields = list(dict.fromkeys(reg_fields))
            obs_fields = list(dict.fromkeys(["ObjectID"] + loc_fields + prob_fields))

            # Initial empty row with starting ID
            init_oids = ["1001"]
            df_reg = pd.DataFrame(index=init_oids, columns=[c for c in reg_fields if c != "ObjectID"])
            df_reg.index.name = "ObjectID"

            df_obs = pd.DataFrame(index=init_oids, columns=[c for c in obs_fields if c != "ObjectID"])
            df_obs.index.name = "ObjectID"
            for pf in prob_fields:
                if pf in df_obs.columns:
                    df_obs[pf] = False

            df_photo = pd.DataFrame(columns=["ObjectID", "ImagePath", "ImageNote"]).set_index("ObjectID")

            # Structured initial log record
            now_iso = datetime.now().isoformat(timespec="seconds")
            raw_log = pd.DataFrame([{
                "Timestamp": now_iso,
                "User": getpass.getuser(),
                "Action": "DATABASE_CREATED",
                "ObjectID": "ALL",
                "Reviewed": "",
                "ChangedFields": f"Profile: {profile_name}; Title: {collection_name}",
                "ChangedValues": f"Columns: {len(reg_fields)} registry, {len(obs_fields)} observation",
                "ProblemsChanged": "",
                "ProblemsChangedValues": "",
                "LocationChanged": "",
                "LocationChangedValues": "",
                "SourceFile": "",
                "OutputFile": os.path.basename(save_path),
            }])
            df_log = _normalise_log_dataframe(raw_log)

            # Persist initial workbook
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            ExcelRepository.save_excel(
                path=save_path,
                config=cfg,
                df_reg=df_reg,
                df_obs=df_obs,
                df_log=df_log,
                df_photo=df_photo,
            )

            # Bind to AppState
            self.app.excel_path = save_path
            self.app.output_path = save_path
            self.app.config = cfg
            self.app.config_name = profile_name
            self.app.df_reg = df_reg
            self.app.df_obs = df_obs
            self.app.df_photo = df_photo
            self.app.df_log = df_log
            self.app.active_object_ids = list(df_reg.index)
            self.app.current_object_id = init_oids[0]
            self.app.dirty = False

            config.add_recent_file(save_path)
            config.set_last_dir("last_db_dir", os.path.dirname(save_path))

            QMessageBox.information(
                self.wizard,
                "Database Initialized",
                f"Successfully created botanical collection database:\n{save_path}",
            )

            if self.on_completed:
                self.on_completed(save_path, profile_name)

        except Exception as e:
            QMessageBox.critical(
                self.wizard,
                "Creation Error",
                f"Failed to initialize database:\n{e}",
            )

    def exec(self) -> int:
        return self.wizard.exec()

    def show(self) -> None:
        self.wizard.show()
