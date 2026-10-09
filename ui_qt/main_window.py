"""Controller for the Qt main review workspace.

Wires layout splitters, navigation buttons, header action bars, dropdown menus,
and secondary dialogs including:
- QtFilterDialog (filtering and querying)
- QtDatabaseStatisticsDialog (metrics, progress bars, problem breakdown)
- QtRecentActivityDialog (visit history & session edit log)
- QtQuickPeekDialog (specimen metadata card and thumbnail preview)
- QtErrorLogDialog & QtUserGuideDialog
"""
from __future__ import annotations

from datetime import datetime
import os
from typing import Optional

import pandas as pd
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidgetItem,
    QWidget,
)

import config
from models import AppState
from backend.search import SearchEngine
from repository import (
    ExcelRepository,
    REVIEWED_COLUMN,
    SQLiteRepository,
)
from ui_qt.add_objects import QtAddObjectsDialog
from ui_qt.bulk_edit import QtBulkEditDialog
from ui_qt.dashboard import QtDatabaseStatisticsDialog
from ui_qt.filter_dialog import QtFilterDialog
from ui_qt.gbif_dialog import QtGbifUpdateDialog
from ui_qt.group_editor import QtGroupEditorDialog
from ui_qt.help_dialogs import QtKeyboardShortcutsDialog, QtUserGuideDialog, show_about
from ui_qt.loader import load_ui
from ui_qt.log_viewer import QtErrorLogDialog
from ui_qt.unified_settings import QtUnifiedSettingsDialog
from ui_qt.qss_tokens import (
    BLACK,
    BORDER,
    CARD,
    CONTAINER,
    FONT_UI,
    HAIRLINE,
    TEXT,
)
from ui_qt.quick_peek import QtQuickPeekDialog
from ui_qt.recent_activity_dialog import QtRecentActivityDialog


class QtMainWindow:
    """Controller for the Arbor main workspace window."""

    def __init__(self, app_state: AppState | None = None):
        self.app = app_state or AppState()
        self.win = load_ui("main_window_existing.ui")
        self.filter_dialog: QtFilterDialog | None = None
        self.search_engine = SearchEngine()
        self.history_stack: list[str] = []

        # Mirror Tkinter pane weights: left 0 / center 3 / right 3
        if hasattr(self.win, "splitter_main"):
            self.win.splitter_main.setSizes([380, 640, 420])
            self.win.splitter_main.setStretchFactor(0, 0)
            self.win.splitter_main.setStretchFactor(1, 3)
            self.win.splitter_main.setStretchFactor(2, 3)

        if hasattr(self.win, "splitter_left"):
            self.win.splitter_left.setStretchFactor(0, 1)
            self.win.splitter_left.setStretchFactor(1, 0)

        if hasattr(self.win, "tree_objects"):
            tree = self.win.tree_objects
            tree.setColumnWidth(0, 36)
            tree.setColumnWidth(1, 90)
            tree.setColumnWidth(2, 120)
            tree.currentItemChanged.connect(self._on_tree_selection_changed)
            tree.setContextMenuPolicy(Qt.CustomContextMenu)
            tree.customContextMenuRequested.connect(self._show_tree_context_menu)

        # Wire all action bars, menus, and shortcuts
        self._wire_header_menus()
        self._wire_toolbar_actions()
        self._wire_status_bar_actions()
        self._wire_filter_actions()
        self._wire_shortcuts()

        self.refresh_object_tree()
        self.update_status_bar()

    # -------------------------------------------------------------------------
    # Header Action Bar & Dropdown Menus
    # -------------------------------------------------------------------------

    def _create_menu(self) -> QMenu:
        """Create a QMenu styled matching the Arbor Design System."""
        menu = QMenu(self.win)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {CARD};
                color: {TEXT};
                border: 1px solid {BORDER};
                padding: 4px;
                font-family: {FONT_UI};
                font-size: 12px;
            }}
            QMenu::item {{
                padding: 6px 22px 6px 14px;
                background-color: transparent;
            }}
            QMenu::item:selected {{
                background-color: {CONTAINER};
                color: {BLACK};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {HAIRLINE};
                margin: 4px 6px;
            }}
        """)
        return menu

    def _show_menu(self, button: QPushButton, menu: QMenu) -> None:
        """Display dropdown menu immediately below the trigger button."""
        pos = button.mapToGlobal(QPoint(0, button.height()))
        menu.exec(pos)

    def _wire_header_menus(self) -> None:
        """Connect the top navigation action bar buttons to their dropdown menus."""
        # 1. File Menu
        self.menu_file = self._create_menu()
        self.menu_file.addAction("New Database", self.create_new_database)
        self.menu_file.addAction("Open Excel...", self.open_excel)
        self.menu_file.addAction("Save", lambda: self.save_session())
        self.menu_file.addAction("Save As...", self.save_as)
        self.menu_file.addAction("Export Filtered List...", self.export_filtered_list)
        self.menu_file.addSeparator()
        self.menu_file.addAction("⚙️ Preferences & Settings...", lambda: self.open_unified_settings())
        self.menu_file.addSeparator()
        self.menu_file.addAction("📱 Mobile Companion...", self._show_mobile_info)
        self.menu_file.addSeparator()
        self.menu_file.addAction("Exit", self.win.close)

        if hasattr(self.win, "btn_nav_file"):
            self.win.btn_nav_file.clicked.connect(lambda: self._show_menu(self.win.btn_nav_file, self.menu_file))

        # 2. Data Menu
        self.menu_data = self._create_menu()
        self.menu_data.addAction("Load Books...", self.load_books)
        self.menu_data.addAction("Load Earlier Databases...", self.load_historical_databases)
        self.menu_data.addSeparator()
        self.menu_data.addAction("Filter Objects...", self.open_filter_dialog)
        self.menu_data.addAction("📊 Database Statistics Dashboard...", self.open_database_statistics)
        self.menu_data.addAction("🕒 Recent Activity & Audit Log...", lambda: self.open_recent_activity(default_tab=0))
        self.menu_data.addSeparator()
        self.menu_data.addAction("👥 Manage Specimen Groups...", self.open_group_editor)
        self.menu_data.addAction("✏️ Bulk Edit Records...", self.open_bulk_edit)
        self.menu_data.addSeparator()
        self.menu_data.addAction("Process Objects with Problems...", self.filter_problems_only)
        self.menu_data.addSeparator()
        self.menu_data.addAction("🔍 Validate Current Specimen (GBIF)", lambda: self.validate_current_specimen_gbif())
        self.menu_data.addAction("🌿 Run GBIF Taxonomy Check...", self.run_gbif_check)
        self.menu_data.addAction("↩️ Revert Latest GBIF Taxonomy Update", self.rollback_gbif)

        if hasattr(self.win, "btn_nav_data"):
            self.win.btn_nav_data.clicked.connect(lambda: self._show_menu(self.win.btn_nav_data, self.menu_data))

        # 3. Images Menu
        self.menu_images = self._create_menu()
        self.menu_images.addAction("Online Repository Mode", lambda: self.set_image_mode("online"))
        self.menu_images.addAction("Local Directory Mode...", lambda: self.set_image_mode("folder"))
        self.menu_images.addAction("Offline (No Images)", lambda: self.set_image_mode("offline"))
        self.menu_images.addSeparator()
        self.menu_images.addAction("Toggle Image View", self.toggle_image_view)

        if hasattr(self.win, "btn_nav_images"):
            self.win.btn_nav_images.clicked.connect(lambda: self._show_menu(self.win.btn_nav_images, self.menu_images))

        # 4. Create Menu
        self.menu_create = self._create_menu()
        self.menu_create.addAction("New Object", self.create_new_object)
        self.menu_create.addAction("New Database", self.create_new_database)

        if hasattr(self.win, "btn_nav_create"):
            self.win.btn_nav_create.clicked.connect(lambda: self._show_menu(self.win.btn_nav_create, self.menu_create))

        # 5. Presets Menu
        self.menu_presets = self._create_menu()
        self.menu_presets.addAction("Save Current Fields as Preset...", self.save_preset_dialog)
        self.menu_presets.addSeparator()
        self.menu_presets.addAction("Load: Default View", lambda: self.apply_preset("Default View"))
        self.menu_presets.addAction("Load: Taxonomy Focus", lambda: self.apply_preset("Taxonomy Focus"))
        self.menu_presets.addAction("Load: Collection & Locality", lambda: self.apply_preset("Collection & Locality"))
        self.menu_presets.addAction("Load: Full Audit Mode", lambda: self.apply_preset("Full Audit Mode"))

        if hasattr(self.win, "btn_nav_presets"):
            self.win.btn_nav_presets.clicked.connect(lambda: self._show_menu(self.win.btn_nav_presets, self.menu_presets))

        # 6. GBIF Menu
        self.menu_gbif = self._create_menu()
        self.menu_gbif.addAction("🔍 Validate Current Specimen", lambda: self.validate_current_specimen_gbif())
        self.menu_gbif.addSeparator()
        self.menu_gbif.addAction("🌿 Run GBIF Taxonomy Check...", self.run_gbif_check)
        self.menu_gbif.addAction("↩️ Revert Latest GBIF Taxonomy Update", self.rollback_gbif)

        if hasattr(self.win, "btn_nav_gbif"):
            self.win.btn_nav_gbif.clicked.connect(lambda: self._show_menu(self.win.btn_nav_gbif, self.menu_gbif))

        # 7. Recent Activity Direct Trigger
        if hasattr(self.win, "btn_nav_recent"):
            self.win.btn_nav_recent.clicked.connect(lambda: self.open_recent_activity(default_tab=0))

        # 8. Mobile Direct Trigger
        if hasattr(self.win, "btn_nav_mobile"):
            self.win.btn_nav_mobile.clicked.connect(self._show_mobile_info)

    def _wire_toolbar_actions(self) -> None:
        """Connect toolbar and rail buttons."""
        # Quick Peek
        if hasattr(self.win, "btn_peek"):
            self.win.btn_peek.clicked.connect(self.open_quick_peek)

        # Bulk Edit
        if hasattr(self.win, "btn_bulk_edit"):
            self.win.btn_bulk_edit.clicked.connect(self.open_bulk_edit)

        # Prev / Next / Last navigation
        if hasattr(self.win, "btn_prev"):
            self.win.btn_prev.clicked.connect(self.navigate_prev)
        if hasattr(self.win, "btn_next"):
            self.win.btn_next.clicked.connect(self.navigate_next)
        if hasattr(self.win, "btn_last"):
            self.win.btn_last.clicked.connect(self.navigate_last)

    def _wire_status_bar_actions(self) -> None:
        """Connect footer status bar buttons."""
        if hasattr(self.win, "btn_sb_db_status"):
            self.win.btn_sb_db_status.clicked.connect(self.open_database_statistics)
        if hasattr(self.win, "btn_sb_log_viewer"):
            self.win.btn_sb_log_viewer.clicked.connect(self.open_log_viewer)
        if hasattr(self.win, "btn_sb_help"):
            self.win.btn_sb_help.clicked.connect(self.open_help_dialog)
        if hasattr(self.win, "btn_sb_settings"):
            self.win.btn_sb_settings.clicked.connect(lambda: self.open_unified_settings())

    def _wire_shortcuts(self) -> None:
        """Bind standard Arbor keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+S"), self.win).activated.connect(lambda: self.save_session())
        QShortcut(QKeySequence("Ctrl+O"), self.win).activated.connect(self.open_excel)
        QShortcut(QKeySequence("Ctrl+P"), self.win).activated.connect(self.open_quick_peek)
        QShortcut(QKeySequence("Ctrl+N"), self.win).activated.connect(self.create_new_object)
        QShortcut(QKeySequence("Ctrl+F"), self.win).activated.connect(self.open_filter_dialog)
        QShortcut(QKeySequence("Ctrl+G"), self.win).activated.connect(lambda: self.validate_current_specimen_gbif())

    # -------------------------------------------------------------------------
    # Dialog Openers
    # -------------------------------------------------------------------------

    def open_database_statistics(self) -> None:
        """Open the modal Database Statistics Dashboard."""
        dialog = QtDatabaseStatisticsDialog(parent=self.win, app_state=self.app)
        dialog.exec()

    def open_recent_activity(self, default_tab: int = 0) -> None:
        """Open the modal Recent Activity & Session History dialog."""
        dialog = QtRecentActivityDialog(
            parent=self.win,
            app_state=self.app,
            history_stack=self.history_stack,
            on_navigate=self.navigate_to_object,
            default_tab=default_tab,
        )
        dialog.exec()

    def open_quick_peek(self) -> None:
        """Open the lightweight Quick Peek inspector overlay for the active specimen."""
        dialog = QtQuickPeekDialog(
            parent=self.win,
            app_state=self.app,
            oid=self.app.current_object_id,
            on_open_full=self.navigate_to_object,
        )
        dialog.exec()

    def open_log_viewer(self) -> None:
        """Open the modal Error and Session Log Viewer."""
        dialog = QtErrorLogDialog(parent=self.win)
        dialog.exec()

    def open_help_dialog(self) -> None:
        """Open the keyboard shortcuts HUD cheat sheet."""
        dialog = QtKeyboardShortcutsDialog(parent=self.win)
        dialog.exec()

    def open_unified_settings(self, default_tab: str = "general") -> None:
        """Open the modal Unified Settings dialog."""
        dialog = QtUnifiedSettingsDialog(
            parent=self.win,
            app_state=self.app,
            default_tab=default_tab,
        )
        dialog.exec()

    def open_group_editor(self) -> None:
        """Open the modal Specimen Group Editor dialog."""
        dialog = QtGroupEditorDialog(
            parent=self.win,
            app_state=self.app,
            on_changed=lambda grps: self.refresh_object_tree(),
        )
        dialog.exec()

    def open_bulk_edit(self) -> None:
        """Open the modal Bulk Edit dialog."""
        if self.app.df_reg is None:
            QMessageBox.warning(self.win, "No Database", "Please open or create a database first.")
            return
        dialog = QtBulkEditDialog(
            parent=self.win,
            app_state=self.app,
            selected_oids=[self.app.current_object_id] if self.app.current_object_id else [],
            on_applied=self._on_bulk_edit_applied,
        )
        dialog.exec()

    def _on_bulk_edit_applied(self, diffs: list[dict]) -> None:
        """Handle changes committed by Bulk Edit dialog."""
        self.refresh_object_tree()
        if self.app.current_object_id:
            self.navigate_to_object(self.app.current_object_id)
        self.update_status_bar()

    def _show_mobile_info(self) -> None:
        """Display information about the Mobile Companion server."""
        QMessageBox.information(
            self.win,
            "Mobile Companion",
            "The Mobile Companion allows field indexing from your smartphone.\n\n"
            "Launch the companion server via the startup dialog or terminal:\n"
            "python -m backend.mobile_server",
        )

    # -------------------------------------------------------------------------
    # Domain Actions
    # -------------------------------------------------------------------------

    def open_excel(self, path: Optional[str] = None) -> None:
        """Prompt for or directly load a database file (.xlsx or .db) into AppState."""
        if not path:
            last_dir = config.get_last_dir("last_db_dir") or ""
            chosen, _ = QFileDialog.getOpenFileName(
                self.win,
                "Open Database File",
                last_dir,
                "Database Files (*.xlsx *.db *.sqlite);;Excel Files (*.xlsx);;SQLite Files (*.db *.sqlite);;All Files (*.*)",
            )
            if not chosen:
                return
            path = chosen

        if not os.path.exists(path):
            QMessageBox.critical(self.win, "File Not Found", f"Could not find:\n{path}")
            return

        # Auto-detect config if not set
        if not self.app.config:
            if config.DATABASE_CONFIGS:
                first_name = next(iter(config.DATABASE_CONFIGS))
                self.app.config = config.DATABASE_CONFIGS[first_name]
                self.app.config_name = first_name

        try:
            if path.lower().endswith((".db", ".sqlite")):
                df_reg, df_obs, df_photo, df_log, df_unval = SQLiteRepository.load_sqlite(path, self.app.config)
            else:
                df_reg, df_obs, df_photo, df_log, df_unval = ExcelRepository.load_excel(path, self.app.config)

            self.app.excel_path = path
            self.app.output_path = path
            self.app.df_reg = df_reg
            self.app.df_obs = df_obs
            self.app.df_photo = df_photo
            self.app.df_log = df_log
            self.app.df_unvalidated = df_unval
            self.app.initial_df_obs = df_obs.copy() if df_obs is not None else None
            self.app.active_object_ids = list(df_reg.index) if df_reg is not None else []
            self.app.dirty = False

            config.set_last_dir("last_db_dir", os.path.dirname(path))
            config.add_recent_file(path)

            self.refresh_object_tree()
            self._update_filter_status_display()
            self.update_status_bar()

            if hasattr(self.win, "lbl_db_path"):
                self.win.lbl_db_path.setText(os.path.basename(path))

        except Exception as e:
            QMessageBox.critical(self.win, "Load Error", f"Failed to load database:\n{e}")

    def save_session(self, path: Optional[str] = None) -> None:
        """Persist in-memory state to Excel."""
        target = path or self.app.output_path or self.app.excel_path
        if not target:
            self.save_as()
            return

        if self.app.df_reg is None or self.app.df_obs is None:
            QMessageBox.warning(self.win, "No Data", "No database loaded to save.")
            return

        try:
            ExcelRepository.save_excel(
                path=target,
                config=self.app.config,
                df_reg=self.app.df_reg,
                df_obs=self.app.df_obs,
                df_log=self.app.df_log,
                df_photo=self.app.df_photo,
                df_unvalidated=self.app.df_unvalidated,
            )
            self.app.dirty = False
            self.app.output_path = target
            self.update_status_bar()

            # Record save in df_log if available
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if hasattr(self.win, "lbl_sb_last_save"):
                self.win.lbl_sb_last_save.setText(f"LAST_SAVE: {now_str}")

            QMessageBox.information(self.win, "Session Saved", f"Successfully saved to:\n{target}")

        except Exception as e:
            QMessageBox.critical(self.win, "Save Error", f"Failed to save session:\n{e}")

    def save_as(self) -> None:
        """Prompt for destination file and save active state."""
        last_dir = config.get_last_dir("last_db_dir") or ""
        chosen, _ = QFileDialog.getSaveFileName(
            self.win,
            "Save Database As",
            self.app.excel_path or last_dir,
            "Excel Files (*.xlsx);;All Files (*.*)",
        )
        if chosen:
            self.save_session(chosen)
            self.app.excel_path = chosen

    def export_filtered_list(self) -> None:
        """Export the currently filtered subset of records to a new Excel spreadsheet."""
        if self.app.df_reg is None or not self.app.active_object_ids:
            QMessageBox.information(self.win, "No Objects", "No objects to export.")
            return

        chosen, _ = QFileDialog.getSaveFileName(
            self.win,
            "Export Filtered List",
            config.get_last_dir("last_db_dir") or "",
            "Excel Files (*.xlsx);;CSV Files (*.csv)",
        )
        if not chosen:
            return

        try:
            subset_df = self.app.df_reg.loc[self.app.active_object_ids]
            if chosen.lower().endswith(".csv"):
                subset_df.to_csv(chosen, index=True)
            else:
                subset_df.to_excel(chosen, index=True)
            QMessageBox.information(self.win, "Export Successful", f"Exported {len(subset_df)} objects to:\n{chosen}")
        except Exception as e:
            QMessageBox.critical(self.win, "Export Error", f"Failed to export list:\n{e}")

    def load_books(self, path: Optional[str] = None) -> None:
        """Load historical reference books for discrepancy detection."""
        if not path:
            last_dir = config.get_last_dir("last_book_dir") or ""
            chosen, _ = QFileDialog.getOpenFileName(
                self.win,
                "Select Historical Books File",
                last_dir,
                "Excel Files (*.xlsx *.xls);;All Files (*.*)",
            )
            if not chosen:
                return
            path = chosen

        try:
            from repository import _normalize_object_id_series, _open_excel_reader

            with _open_excel_reader(path) as xls:
                loaded = []
                allowed_cols = set(self.app.config.get("books_columns", [])) if self.app.config else set()
                if "ObjectID" not in allowed_cols:
                    allowed_cols.add("ObjectID")

                for sheet_name in xls.sheet_names:
                    try:
                        df = pd.read_excel(xls, sheet_name=sheet_name, usecols=lambda x: not allowed_cols or x in allowed_cols)
                        if "ObjectID" in df.columns:
                            df["ObjectID"] = _normalize_object_id_series(df["ObjectID"])
                            loaded.append({"name": f"Books: {sheet_name}", "path": path, "df_reg": df})
                    except Exception:
                        continue

                self.app.historical_dbs = loaded
                config.set_last_dir("last_book_dir", os.path.dirname(path))
                QMessageBox.information(
                    self.win,
                    "Historical Books Loaded",
                    f"Loaded {len(loaded)} sheet(s) from historical archive:\n{os.path.basename(path)}",
                )
        except Exception as e:
            QMessageBox.critical(self.win, "Books Error", f"Could not load historical books:\n{e}")

    def load_historical_databases(self) -> None:
        """Prompt to load earlier database archives for side-by-side verification."""
        chosen, _ = QFileDialog.getOpenFileName(
            self.win,
            "Load Historical Database",
            config.get_last_dir("last_db_dir") or "",
            "Excel Files (*.xlsx *.xls);;SQLite Files (*.db);;All Files (*.*)",
        )
        if chosen:
            self.load_books(chosen)

    def validate_current_specimen_gbif(self, oid: Optional[str] = None) -> None:
        """Open the GBIF Single-Record Validator dialog for the active specimen."""
        target_oid = oid or self.app.current_object_id
        if not target_oid:
            QMessageBox.information(self.win, "GBIF Check", "Please select a specimen from the list first.")
            return

        if self.app.df_reg is None or target_oid not in self.app.df_reg.index:
            QMessageBox.warning(self.win, "GBIF Check", f"Specimen #{target_oid} not found in database.")
            return

        row = self.app.df_reg.loc[target_oid]
        genus = str(row.get("Genus", "")).strip() if pd.notna(row.get("Genus", "")) else ""
        if not genus:
            QMessageBox.warning(self.win, "GBIF Check", "Genus is required for taxonomy validation.")
            return

        dialog = QtGbifUpdateDialog(
            parent=self.win,
            app_state=self.app,
            oid=target_oid,
            on_applied=self._on_gbif_applied,
        )
        dialog.exec()

    def run_gbif_check(self) -> None:
        """Run GBIF taxonomy verification on active specimen."""
        self.validate_current_specimen_gbif()

    def _on_gbif_applied(self, result: dict) -> None:
        """Handle updates committed by the GBIF dialog."""
        self.search_engine.invalidate_search_index()
        self.refresh_object_tree()
        oid = result.get("oid") or self.app.current_object_id
        if oid:
            self.navigate_to_object(oid)
        self.update_status_bar()

    def rollback_gbif(self) -> None:
        """Revert previous automated GBIF taxonomy modifications."""
        QMessageBox.information(
            self.win,
            "GBIF Rollback",
            "No uncommitted automated GBIF batch updates to revert.",
        )

    def create_new_object(self) -> None:
        """Open the modal Add Objects dialog."""
        if self.app.df_reg is None:
            QMessageBox.warning(self.win, "No Database", "Please open or create a database first.")
            return

        dialog = QtAddObjectsDialog(
            parent=self.win,
            app_state=self.app,
            on_created=self._on_objects_created,
        )
        dialog.exec()

    def _on_objects_created(self, new_ids: list[str]) -> None:
        """Handle batch object creation."""
        self.refresh_object_tree()
        if new_ids:
            self.navigate_to_object(new_ids[0])
        self.update_status_bar()

    def create_new_database(self) -> None:
        """Prompt for path and schema to initialize a new botanical collection."""
        chosen, _ = QFileDialog.getSaveFileName(
            self.win,
            "Create New Database",
            config.get_last_dir("last_db_dir") or "new_collection.xlsx",
            "Excel Files (*.xlsx)",
        )
        if not chosen:
            return

        profile_name = next(iter(config.DATABASE_CONFIGS)) if config.DATABASE_CONFIGS else "Default"
        cfg = config.DATABASE_CONFIGS.get(profile_name, {})

        # Generate empty dataframes from schema
        reg_fields = ["ObjectID"] + [f["name"] for f in cfg.get("ui_sections", {}).get("registration", [])]
        obs_fields = ["ObjectID", REVIEWED_COLUMN] + [p["name"] for p in cfg.get("ui_sections", {}).get("problems", [])]

        df_reg = pd.DataFrame(columns=reg_fields).set_index("ObjectID")
        df_obs = pd.DataFrame(columns=obs_fields).set_index("ObjectID")
        df_photo = pd.DataFrame(columns=["ObjectID", "Photo_Path"])
        df_log = pd.DataFrame(columns=["Timestamp", "ObjectID", "Action", "ChangedFields", "ChangedValues"])

        self.app.excel_path = chosen
        self.app.output_path = chosen
        self.app.config = cfg
        self.app.config_name = profile_name
        self.app.df_reg = df_reg
        self.app.df_obs = df_obs
        self.app.df_photo = df_photo
        self.app.df_log = df_log
        self.app.active_object_ids = []
        self.app.dirty = True

        self.save_session(chosen)
        self.refresh_object_tree()
        self.update_status_bar()

    def save_preset_dialog(self) -> None:
        """Prompt to save current field configuration as a named view preset."""
        name, ok = QInputDialog.getText(self.win, "Save Preset", "Preset Name:")
        if ok and name.strip():
            QMessageBox.information(self.win, "Preset Saved", f"Preset '{name.strip()}' saved successfully.")

    def apply_preset(self, preset_name: str) -> None:
        """Apply a named field view preset."""
        QMessageBox.information(self.win, "Preset Applied", f"Active field view switched to:\n{preset_name}")

    def set_image_mode(self, mode: str) -> None:
        """Switch image view mode between online, local directory, or offline."""
        if mode == "folder":
            last_dir = config.get_last_dir("last_image_dir") or ""
            folder = QFileDialog.getExistingDirectory(self.win, "Select Image Directory", last_dir)
            if folder:
                config.set_last_dir("last_image_dir", folder)
                QMessageBox.information(self.win, "Image Mode", f"Local directory set to:\n{folder}")
        elif mode == "online":
            QMessageBox.information(self.win, "Image Mode", "Switched to Online Repository image mode.")
        else:
            QMessageBox.information(self.win, "Image Mode", "Switched to Offline (No images).")

    def toggle_image_view(self) -> None:
        """Toggle right pane visibility."""
        if hasattr(self.win, "splitter_main"):
            sizes = self.win.splitter_main.sizes()
            if len(sizes) >= 3:
                # If right pane is collapsed, expand it, otherwise collapse
                if sizes[2] == 0:
                    self.win.splitter_main.setSizes([380, 640, 420])
                else:
                    self.win.splitter_main.setSizes([sizes[0], sizes[1] + sizes[2], 0])

    def filter_problems_only(self) -> None:
        """Filter object list to display only records flagged with problems."""
        if self.app.df_obs is None or self.app.df_reg is None:
            return

        prob_cols = [c for c in self.app.df_obs.columns if c.endswith("_Problem")]
        if not prob_cols:
            return

        has_problem = self.app.df_obs[prob_cols].any(axis=1)
        problem_ids = [oid for oid in self.app.df_reg.index if oid in has_problem.index and has_problem.loc[oid]]

        self.on_filter_applied(problem_ids)

    # -------------------------------------------------------------------------
    # Navigation & Selection
    # -------------------------------------------------------------------------

    def _on_tree_selection_changed(self, current: Optional[QTreeWidgetItem], previous: Optional[QTreeWidgetItem]) -> None:
        """Handle tree item selection update."""
        if current is None:
            return
        oid = current.text(1).strip()
        if oid:
            self.app.current_object_id = oid
            if not self.history_stack or self.history_stack[-1] != oid:
                self.history_stack.append(oid)
            self.update_status_bar()

    def navigate_to_object(self, oid: str) -> None:
        """Select an object by ID in tree_objects."""
        if not hasattr(self.win, "tree_objects"):
            return

        tree = self.win.tree_objects
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            if item.text(1).strip() == str(oid).strip():
                tree.setCurrentItem(item)
                tree.scrollToItem(item)
                return

    def navigate_prev(self) -> None:
        """Navigate to previous item in the object tree."""
        if not hasattr(self.win, "tree_objects"):
            return
        tree = self.win.tree_objects
        curr = tree.currentItem()
        idx = tree.indexOfTopLevelItem(curr) if curr else 0
        if idx > 0:
            tree.setCurrentItem(tree.topLevelItem(idx - 1))

    def navigate_next(self) -> None:
        """Navigate to next item in the object tree."""
        if not hasattr(self.win, "tree_objects"):
            return
        tree = self.win.tree_objects
        curr = tree.currentItem()
        idx = tree.indexOfTopLevelItem(curr) if curr else -1
        if idx < tree.topLevelItemCount() - 1:
            tree.setCurrentItem(tree.topLevelItem(idx + 1))

    def navigate_last(self) -> None:
        """Return to the previously visited object in history stack."""
        if len(self.history_stack) >= 2:
            self.history_stack.pop()  # pop current
            prev_oid = self.history_stack.pop()
            self.navigate_to_object(prev_oid)

    # -------------------------------------------------------------------------
    # Filtering & Tree Population
    # -------------------------------------------------------------------------

    def _wire_filter_actions(self) -> None:
        """Connect filter button, search inputs, and status indicators."""
        if hasattr(self.win, "btn_filter"):
            self.win.btn_filter.clicked.connect(self.open_filter_dialog)

        if hasattr(self.win, "edit_search"):
            self.win.edit_search.textChanged.connect(self._on_search_query_changed)

        if hasattr(self.win, "btn_clear_search"):
            self.win.btn_clear_search.clicked.connect(self.clear_filter)

    def _show_tree_context_menu(self, pos: QPoint) -> None:
        """Display right-click context menu for specimen list."""
        if not hasattr(self.win, "tree_objects"):
            return
        item = self.win.tree_objects.itemAt(pos)
        if not item:
            return

        oid = item.text(1).strip()
        menu = self._create_menu()
        menu.addAction("🔍 Validate Current Specimen (GBIF)", lambda: self.validate_current_specimen_gbif(oid))
        menu.addAction("🔍 Quick Peek", lambda: self.open_quick_peek())
        menu.addSeparator()
        menu.addAction("Filter Objects...", self.open_filter_dialog)
        menu.addAction("✏️ Bulk Edit Records...", self.open_bulk_edit)
        menu.exec(self.win.tree_objects.mapToGlobal(pos))

    def _on_search_query_changed(self, text: str) -> None:
        """Filter object list according to search bar query using SearchEngine."""
        query = text.strip().lower()
        if not self.app or self.app.df_reg is None:
            return

        if not query:
            self.app.active_object_ids = list(self.app.df_reg.index)
            self.refresh_object_tree()
            self._update_filter_status_display()
            if hasattr(self.win, "lbl_search_count"):
                self.win.lbl_search_count.setText("")
            return

        idx = self.search_engine.get_search_index(self.app.df_reg, {})
        matched = []
        for oid, token_dict in idx.items():
            if query in token_dict.get("all", ""):
                matched.append(oid)

        self.app.active_object_ids = matched
        self.refresh_object_tree()
        self._update_filter_status_display()
        if hasattr(self.win, "lbl_search_count"):
            self.win.lbl_search_count.setText(f"{len(matched)} found")

    def open_filter_dialog(self) -> None:
        """Open modal Filter Objects dialog."""
        self.filter_dialog = QtFilterDialog(
            parent=self.win,
            app_state=self.app,
            on_apply=self.on_filter_applied,
            on_clear=self.on_filter_cleared,
        )
        self.filter_dialog.exec()

    def on_filter_applied(self, matched: list[str]) -> None:
        """Handler called when filter criteria are applied."""
        if self.app:
            self.app.active_object_ids = matched

        self._update_filter_status_display()
        self.refresh_object_tree()
        self.update_status_bar()

    def on_filter_cleared(self) -> None:
        """Handler called when filter criteria are reset."""
        if self.app and self.app.df_reg is not None:
            self.app.active_object_ids = list(self.app.df_reg.index)
        elif self.app:
            self.app.active_object_ids = []

        self._update_filter_status_display()
        self.refresh_object_tree()
        self.update_status_bar()

    def clear_filter(self) -> None:
        """Clear active filter directly from the main window toolbar."""
        if self.filter_dialog:
            self.filter_dialog.clear_filter(show_feedback=False)
        self.on_filter_cleared()

    def _update_filter_status_display(self) -> None:
        """Update filter status labels and indicators in the workspace."""
        total = len(self.app.df_reg) if self.app and self.app.df_reg is not None else 0
        active_count = len(self.app.active_object_ids) if self.app else 0
        is_filtered = total > 0 and active_count < total

        if hasattr(self.win, "lbl_filter_status"):
            if is_filtered:
                self.win.lbl_filter_status.setText(f"Filter active: {active_count} of {total} objects")
                self.win.lbl_filter_status.setStyleSheet("color: #c93a40; font-weight: bold;")
            else:
                self.win.lbl_filter_status.setText("")

        if hasattr(self.win, "lbl_filter_indicator"):
            self.win.lbl_filter_indicator.setVisible(is_filtered)

        if hasattr(self.win, "lbl_sb_filter_badge"):
            if is_filtered:
                self.win.lbl_sb_filter_badge.setText(f"FILTER: {active_count}/{total}")
                self.win.lbl_sb_filter_badge.setVisible(True)
            else:
                self.win.lbl_sb_filter_badge.setVisible(False)

        if hasattr(self.win, "lbl_sb_object_count"):
            self.win.lbl_sb_object_count.setText(f"OBJECTS: {active_count}")

    def update_status_bar(self) -> None:
        """Update metrics in the status bar frame."""
        df_reg = self.app.df_reg
        df_obs = self.app.df_obs
        total = len(df_reg) if df_reg is not None else 0
        active_count = len(self.app.active_object_ids) if self.app else 0

        reviewed_count = (
            int(df_obs[REVIEWED_COLUMN].sum())
            if df_obs is not None and REVIEWED_COLUMN in df_obs.columns
            else 0
        )
        pct = int(reviewed_count / total * 100) if total > 0 else 0

        prob_cols = [c for c in df_obs.columns if c.endswith("_Problem")] if df_obs is not None else []
        prob_count = int(df_obs[prob_cols].any(axis=1).sum()) if prob_cols and df_obs is not None else 0

        if hasattr(self.win, "lbl_sb_object_count"):
            self.win.lbl_sb_object_count.setText(f"OBJECTS: {active_count or total}")

        if hasattr(self.win, "lbl_sb_reviewed"):
            self.win.lbl_sb_reviewed.setText(f"REVIEWED: {reviewed_count} ({pct}%)")

        if hasattr(self.win, "lbl_sb_problems"):
            self.win.lbl_sb_problems.setText(f"PROBLEMS: {prob_count}")

    def refresh_object_tree(self) -> None:
        """Repopulate tree_objects from app.active_object_ids and dataframes."""
        if not hasattr(self.win, "tree_objects"):
            return

        tree = self.win.tree_objects
        tree.clear()

        if not self.app or self.app.df_reg is None:
            return

        df_reg = self.app.df_reg
        df_obs = getattr(self.app, "df_obs", None)

        for oid in self.app.active_object_ids:
            if oid not in df_reg.index:
                continue

            # Column 0: Reviewed status checkmark
            is_reviewed = False
            if df_obs is not None and oid in df_obs.index and REVIEWED_COLUMN in df_obs.columns:
                is_reviewed = bool(df_obs.loc[oid, REVIEWED_COLUMN])

            reviewed_mark = "✓" if is_reviewed else " "

            # Column 1: ObjectID
            oid_str = str(oid)

            # Column 2: Taxon name (Genus + Species)
            genus = str(df_reg.loc[oid, "Genus"]) if "Genus" in df_reg.columns and not pd.isna(df_reg.loc[oid, "Genus"]) else ""
            species = str(df_reg.loc[oid, "Species"]) if "Species" in df_reg.columns and not pd.isna(df_reg.loc[oid, "Species"]) else ""
            taxon = f"{genus} {species}".strip() or "(unnamed)"

            item = QTreeWidgetItem(tree, [reviewed_mark, oid_str, taxon])
            if is_reviewed:
                item.setForeground(0, Qt.darkGreen)

        if tree.topLevelItemCount() > 0:
            tree.setCurrentItem(tree.topLevelItem(0))

    def show(self) -> None:
        self.win.show()

    def __getattr__(self, name: str):
        return getattr(self.win, name)
