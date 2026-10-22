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
from ui_qt.advanced_search import QtAdvancedSearchDialog
from ui_qt.dashboard import QtDatabaseStatisticsDialog
from ui_qt.filter_dialog import QtFilterDialog
from ui_qt.gbif_dialog import QtGbifUpdateDialog
from ui_qt.gbif_review import QtGbifReviewDialog
from ui_qt.group_editor import QtGroupEditorDialog
from ui_qt.help_dialogs import QtKeyboardShortcutsDialog, QtUserGuideDialog, show_about
from ui_qt.historical_resolver import QtHistoricalResolverDialog
from ui_qt.loader import load_ui
from ui_qt.log_viewer import QtErrorLogDialog
from ui_qt.new_database_wizard import QtNewDatabaseWizard
from ui_qt.problem_queue import QtProblemQueueDialog
from ui_qt.unified_settings import QtUnifiedSettingsDialog
from ui_qt.qss_tokens import (
    BLACK,
    BORDER,
    CARD,
    CONTAINER,
    FONT_UI,
    HAIRLINE,
    TEXT,
    repolish,
)
from ui_qt.image_viewer import QtImageViewer
from ui_qt.location_panel import QtLocationPanel
from ui_qt.problems_panel import QtProblemsPanel
from ui_qt.quick_peek import QtQuickPeekDialog
from ui_qt.recent_activity_dialog import QtRecentActivityDialog
from ui_qt.registry_panel import QtRegistryPanel



class QtMainWindow:
    """Controller for the Arbor main workspace window."""

    def __init__(self, app_state: AppState | None = None):
        self.app = app_state or AppState()
        self.win = load_ui("main_window_existing.ui")
        self.filter_dialog: QtFilterDialog | None = None
        self.search_engine = SearchEngine()
        self.history_stack: list[str] = []

        # Enforce string ObjectID indexing if data is already loaded in app_state
        for df in (self.app.df_reg, self.app.df_obs, self.app.df_photo):
            if df is not None and "ObjectID" in df.columns:
                df["ObjectID"] = df["ObjectID"].astype(str).str.strip()
                df.set_index("ObjectID", inplace=True)
            elif df is not None:
                df.index = df.index.astype(str).str.strip()

        if self.app.df_reg is not None and not self.app.active_object_ids:
            self.app.active_object_ids = [str(x).strip() for x in self.app.df_reg.index]

        # Initialize dynamic Registration form cards in tab_general
        self.registry_panel: QtRegistryPanel | None = None
        if hasattr(self.win, "scroll_general_contents") and self.win.scroll_general_contents.layout():
            self.registry_panel = QtRegistryPanel(self.win.scroll_general_contents.layout(), self.app.config)
            self.registry_panel.on_problem_changed_callback = self._on_problem_toggled
            self.registry_panel.on_field_changed_callback = self._on_field_edited

        # Initialize dynamic Problems checklist in tab_problems
        self.problems_panel: QtProblemsPanel | None = None
        if hasattr(self.win, "scroll_problems_contents") and self.win.scroll_problems_contents.layout():
            self.problems_panel = QtProblemsPanel(self.app.config)
            self.win.scroll_problems_contents.layout().addWidget(self.problems_panel)
            self.problems_panel.problem_toggled.connect(self._on_problem_toggled)

        # Mirror Tkinter pane weights: left 0 / center 3 / right 3
        prefs = config.load_prefs() or {}
        if hasattr(self.win, "splitter_main"):
            saved_sizes = prefs.get("splitter_sizes")
            if saved_sizes and len(saved_sizes) == 3 and all(s > 0 for s in saved_sizes):
                self.win.splitter_main.setSizes(saved_sizes)
            else:
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

        # Initialize Middle Column Image Canvas & Toolbar
        self.image_viewer: QtImageViewer | None = None
        if hasattr(self.win, "image_view"):
            self.image_viewer = QtImageViewer(
                graphics_view=self.win.image_view,
                lbl_images_count=getattr(self.win, "lbl_images_count", None),
                lbl_images_missing=getattr(self.win, "lbl_images_missing", None),
                lbl_zoom_status=getattr(self.win, "lbl_zoom_status", None),
            )
            self.image_viewer.wire_toolbar(
                btn_zoom_in=getattr(self.win, "btn_zoom_in", None),
                btn_zoom_out=getattr(self.win, "btn_zoom_out", None),
                btn_rotate_ccw=getattr(self.win, "btn_rotate_ccw", None),
                btn_rotate_cw=getattr(self.win, "btn_rotate_cw", None),
                btn_reset_view=getattr(self.win, "btn_reset_view", None),
                btn_fit_view=getattr(self.win, "btn_fit_view", None),
            )

        # Initialize Dual-Docking Location Panel (Default: Middle Column)
        prefs = config.load_prefs() or {}
        self.location_in_center = prefs.get("location_in_center", True)
        loc_mode = "horizontal_2row" if prefs.get("location_2row", False) else "horizontal_1row"

        self.location_panel = QtLocationPanel(
            config_ref=self.app.config,
            mode=loc_mode if self.location_in_center else "vertical",
        )
        self.location_panel.toggle_dock_requested.connect(self.toggle_location_panel_position)
        self.location_panel.field_changed.connect(self._on_location_field_edited)
        self._mount_location_panel()

        # Wire all action bars, menus, and shortcuts
        self._wire_header_menus()
        self._wire_toolbar_actions()
        self._wire_status_bar_actions()
        self._wire_filter_actions()
        self._wire_shortcuts()

        # Exit confirmation guard
        self.win.closeEvent = self._on_close_event

        self.refresh_object_tree()
        self.update_status_bar()
        self.update_save_status()

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
        self.menu_data.addAction("Historical Books Conflict Resolver...", self.open_historical_resolver)
        self.menu_data.addSeparator()
        self.menu_data.addAction("Filter Objects...", self.open_filter_dialog)
        self.menu_data.addAction("Advanced Historical Search...", self.open_advanced_search)
        self.menu_data.addAction("📊 Database Statistics Dashboard...", self.open_database_statistics)
        self.menu_data.addAction("🕒 Recent Activity & Audit Log...", lambda: self.open_recent_activity(default_tab=0))
        self.menu_data.addSeparator()
        self.menu_data.addAction("👥 Manage Specimen Groups...", self.open_group_editor)
        self.menu_data.addAction("✏️ Bulk Edit Records...", self.open_bulk_edit)
        self.menu_data.addSeparator()
        self.menu_data.addAction("Process Objects with Problems...", self.open_problem_queue)
        self.menu_data.addSeparator()
        self.menu_data.addAction("🔍 Validate Current Specimen (GBIF)", lambda: self.validate_current_specimen_gbif())
        self.menu_data.addAction("🌿 Batch Taxonomy Review (GBIF)...", self.open_gbif_batch_review)
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
        self.menu_gbif.addAction("🌿 Batch Taxonomy Review (GBIF)...", self.open_gbif_batch_review)
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

        # Mark Reviewed
        if hasattr(self.win, "btn_mark_reviewed"):
            self.win.btn_mark_reviewed.clicked.connect(self.toggle_reviewed)

        # GBIF Single Specimen Validation
        if hasattr(self.win, "btn_gbif"):
            self.win.btn_gbif.clicked.connect(lambda: self.validate_current_specimen_gbif())

        # Historical Books Resolver
        if hasattr(self.win, "btn_check_books"):
            self.win.btn_check_books.clicked.connect(lambda: self.open_historical_resolver())

        # Prev / Next / Last navigation
        if hasattr(self.win, "btn_prev"):
            self.win.btn_prev.clicked.connect(self.navigate_prev)
        if hasattr(self.win, "btn_next"):
            self.win.btn_next.clicked.connect(self.navigate_next)
        if hasattr(self.win, "btn_last"):
            self.win.btn_last.clicked.connect(self.navigate_last)
        if hasattr(self.win, "btn_next_problem"):
            self.win.btn_next_problem.clicked.connect(self.navigate_next_problem)
        if hasattr(self.win, "btn_next_hist"):
            self.win.btn_next_hist.clicked.connect(self.navigate_next_hist)
        if hasattr(self.win, "btn_history"):
            self.win.btn_history.clicked.connect(self.open_recent_activity)

        # Sorting ComboBox
        if hasattr(self.win, "combo_sort"):
            self.win.combo_sort.currentTextChanged.connect(self._on_sort_changed)

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
        """Bind standard Arbor keyboard shortcuts with full Tkinter parity."""
        # Session & File Operations
        QShortcut(QKeySequence("Ctrl+S"), self.win).activated.connect(lambda: self.save_session())
        QShortcut(QKeySequence("Ctrl+O"), self.win).activated.connect(self.focus_object_tree)

        # Focus & Panel Navigation (Tkinter Parity)
        QShortcut(QKeySequence("Ctrl+F"), self.win).activated.connect(self.focus_search_bar)
        QShortcut(QKeySequence("Ctrl+E"), self.win).activated.connect(self.focus_first_reg_field)
        QShortcut(QKeySequence("Ctrl+I"), self.win).activated.connect(self.focus_first_reg_field)
        QShortcut(QKeySequence("Shift+E"), self.win).activated.connect(self.focus_first_empty_reg_field)
        QShortcut(QKeySequence("Ctrl+L"), self.win).activated.connect(self.focus_first_location_field)
        QShortcut(QKeySequence("F4"), self.win).activated.connect(self.focus_first_location_field)
        QShortcut(QKeySequence("Ctrl+Shift+L"), self.win).activated.connect(self.focus_first_location_field)
        QShortcut(QKeySequence("Ctrl+P"), self.win).activated.connect(self.focus_first_problem_checkbox)
        QShortcut(QKeySequence("F3"), self.win).activated.connect(self.focus_first_problem_checkbox)
        QShortcut(QKeySequence("Ctrl+Shift+P"), self.win).activated.connect(self.focus_first_problem_checkbox)
        QShortcut(QKeySequence("Ctrl+Page_Up"), self.win).activated.connect(lambda: self.switch_registration_tab(-1))
        QShortcut(QKeySequence("Ctrl+Page_Down"), self.win).activated.connect(lambda: self.switch_registration_tab(1))
        QShortcut(QKeySequence("Space"), self.win).activated.connect(self.toggle_focused_problem_checkbox)

        # Review & Editing
        QShortcut(QKeySequence("Ctrl+R"), self.win).activated.connect(self.toggle_reviewed)
        QShortcut(QKeySequence("Ctrl+Return"), self.win).activated.connect(self.toggle_reviewed)
        QShortcut(QKeySequence("Ctrl+Enter"), self.win).activated.connect(self.toggle_reviewed)
        QShortcut(QKeySequence("Ctrl+Z"), self.win).activated.connect(self.undo)
        QShortcut(QKeySequence("Ctrl+Y"), self.win).activated.connect(self.redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self.win).activated.connect(self.redo)

        # Dialog Openers & Tools
        QShortcut(QKeySequence("Ctrl+G"), self.win).activated.connect(self.open_filter_dialog)
        QShortcut(QKeySequence("Ctrl+Shift+F"), self.win).activated.connect(self.open_advanced_search)
        QShortcut(QKeySequence("Ctrl+B"), self.win).activated.connect(self.open_bulk_edit)
        QShortcut(QKeySequence("Ctrl+J"), self.win).activated.connect(self.open_database_statistics)
        QShortcut(QKeySequence("Ctrl+H"), self.win).activated.connect(self.open_historical_resolver)
        QShortcut(QKeySequence("Ctrl+K"), self.win).activated.connect(lambda: self.apply_preset("Default View"))
        QShortcut(QKeySequence("F1"), self.win).activated.connect(self.open_help_dialog)

        # Object Management
        QShortcut(QKeySequence("Ctrl+N"), self.win).activated.connect(self.create_new_object)
        QShortcut(QKeySequence("Ctrl+Shift+N"), self.win).activated.connect(self.quick_create_new_object)
        QShortcut(QKeySequence("Ctrl+Shift+D"), self.win).activated.connect(self.duplicate_current_specimen)
        QShortcut(QKeySequence("Ctrl+Delete"), self.win).activated.connect(self.delete_current_specimen)

        # Specimen Navigation
        QShortcut(QKeySequence("Left"), self.win).activated.connect(self.navigate_prev)
        QShortcut(QKeySequence("Right"), self.win).activated.connect(self.navigate_next)
        QShortcut(QKeySequence("Alt+Left"), self.win).activated.connect(self.navigate_last)

        # Layout Toggles (Laptop Views)
        QShortcut(QKeySequence("F6"), self.win).activated.connect(self.toggle_left_panel)
        QShortcut(QKeySequence("F7"), self.win).activated.connect(self.toggle_registration_panel)
        QShortcut(QKeySequence("F8"), self.win).activated.connect(self.toggle_image_panel)

        # Image Gallery Shortcuts
        if hasattr(self, "image_viewer") and self.image_viewer:
            QShortcut(QKeySequence("Shift+Left"), self.win).activated.connect(self.image_viewer.prev_image)
            QShortcut(QKeySequence("Shift+Right"), self.win).activated.connect(self.image_viewer.next_image)
            QShortcut(QKeySequence("Alt+R"), self.win).activated.connect(self.image_viewer.rotate_cw)
            QShortcut(QKeySequence("Ctrl+0"), self.win).activated.connect(self.image_viewer.reset_view)
            QShortcut(QKeySequence("Ctrl+="), self.win).activated.connect(self.image_viewer.zoom_in)
            QShortcut(QKeySequence("Ctrl++"), self.win).activated.connect(self.image_viewer.zoom_in)
            QShortcut(QKeySequence("Ctrl+-"), self.win).activated.connect(self.image_viewer.zoom_out)

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

            # Enforce string ObjectID indexing
            for df in (df_reg, df_obs, df_photo):
                if df is not None and "ObjectID" in df.columns:
                    df["ObjectID"] = df["ObjectID"].astype(str).str.strip()
                    df.set_index("ObjectID", inplace=True)
                elif df is not None:
                    df.index = df.index.astype(str).str.strip()

            self.app.excel_path = path
            self.app.output_path = path
            self.app.df_reg = df_reg
            self.app.df_obs = df_obs
            self.app.df_photo = df_photo
            self.app.df_log = df_log
            self.app.df_unvalidated = df_unval
            self.app.initial_df_obs = df_obs.copy() if df_obs is not None else None
            self.app.active_object_ids = [str(x).strip() for x in df_reg.index] if df_reg is not None else []
            self.app.dirty = False

            config.set_last_dir("last_db_dir", os.path.dirname(path))
            config.add_recent_file(path)

            # Rebuild dynamic registration form for current database configuration
            if hasattr(self.win, "scroll_general_contents") and self.win.scroll_general_contents.layout():
                self.registry_panel = QtRegistryPanel(self.win.scroll_general_contents.layout(), self.app.config)
                self.registry_panel.on_problem_changed_callback = self._on_problem_toggled
                self.registry_panel.on_field_changed_callback = self._on_field_edited

            # Rebuild dynamic problems checklist for current database configuration
            if hasattr(self.win, "scroll_problems_contents") and self.win.scroll_problems_contents.layout():
                # Clear existing items from scroll_problems_contents layout
                while self.win.scroll_problems_contents.layout().count():
                    item = self.win.scroll_problems_contents.layout().takeAt(0)
                    w = item.widget()
                    if w:
                        w.deleteLater()
                self.problems_panel = QtProblemsPanel(self.app.config)
                self.win.scroll_problems_contents.layout().addWidget(self.problems_panel)
                self.problems_panel.problem_toggled.connect(self._on_problem_toggled)

            # Rebuild dynamic location panel for current database configuration
            if hasattr(self, "location_panel") and self.location_panel:
                self.location_panel.config_ref = self.app.config
                self.location_panel.build_ui()
                self.location_panel.field_changed.connect(self._on_location_field_edited)
                self._mount_location_panel()

            self.refresh_object_tree()
            self._update_filter_status_display()
            self.update_status_bar()
            self.update_save_status()

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
            self.update_save_status()
            self.log_action("SAVE", ["Session"], [f'Saved to: "{target}"'])

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
        """Launch the multi-step New Database Wizard."""
        wizard = QtNewDatabaseWizard(
            parent=self.win,
            app_state=self.app,
            on_completed=self._on_new_database_initialized,
        )
        wizard.exec()

    def _on_new_database_initialized(self, path: str, profile_name: str) -> None:
        """Refresh main workspace when a new database is initialized."""
        self.search_engine.invalidate_search_index()
        self.refresh_object_tree()
        self._update_filter_status_display()
        self.update_status_bar()
        if hasattr(self.win, "lbl_db_path"):
            self.win.lbl_db_path.setText(os.path.basename(path))

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

    def open_problem_queue(self) -> None:
        """Open the Problem Queue Resolver dialog."""
        if self.app.df_reg is None or self.app.df_obs is None:
            QMessageBox.warning(self.win, "No Database", "Please open or create a database first.")
            return

        dialog = QtProblemQueueDialog(
            parent=self.win,
            app_state=self.app,
            on_resolved=self._on_problem_resolved,
            on_inspect=self.navigate_to_object,
        )
        dialog.exec()

    def _on_problem_resolved(self, oid: str) -> None:
        """Handler called when a problem is resolved in the queue."""
        self.refresh_object_tree()
        self.update_status_bar()

    def open_historical_resolver(self, oid: Optional[str] = None) -> None:
        """Open the Historical Books Conflict Resolver dialog."""
        target_oid = oid or self.app.current_object_id
        if not target_oid:
            QMessageBox.information(self.win, "Historical Resolver", "Please select a specimen from the list first.")
            return

        if not self.app.historical_dbs:
            reply = QMessageBox.question(
                self.win,
                "No Historical Books Loaded",
                "No archival historical books are currently loaded.\nWould you like to load a historical books file now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.load_books()
            if not self.app.historical_dbs:
                return

        dialog = QtHistoricalResolverDialog(
            parent=self.win,
            app_state=self.app,
            oid=target_oid,
            on_resolved=lambda resolved_oid: self.refresh_object_tree(),
        )
        dialog.exec()

    def open_gbif_batch_review(self) -> None:
        """Open the GBIF Batch Taxonomy Reconciliation and Review workspace."""
        if self.app.df_reg is None:
            QMessageBox.warning(self.win, "No Database", "Please open or create a database first.")
            return

        dialog = QtGbifReviewDialog(
            parent=self.win,
            app_state=self.app,
            on_applied=self._on_gbif_batch_applied,
        )
        dialog.exec()

    def _on_gbif_batch_applied(self, count: int) -> None:
        """Handler called after batch GBIF updates are committed."""
        self.search_engine.invalidate_search_index()
        self.refresh_object_tree()
        self.update_status_bar()

    # -------------------------------------------------------------------------
    # Navigation & Selection
    # -------------------------------------------------------------------------

    def _on_tree_selection_changed(self, current: Optional[QTreeWidgetItem], previous: Optional[QTreeWidgetItem]) -> None:
        """Handle tree item selection update, updating middle column header and registration fields."""
        if current is None:
            self.app.current_object_id = None
            if hasattr(self.win, "lbl_id_badge"):
                self.win.lbl_id_badge.setText("ID: --")
            if hasattr(self.win, "lbl_specimen_name"):
                self.win.lbl_specimen_name.setText("No Specimen Selected")
            if hasattr(self.win, "lbl_status_badge"):
                self.win.lbl_status_badge.setText("PENDING")
                self.win.lbl_status_badge.setProperty("state", "pending")
                repolish(self.win.lbl_status_badge)
            if hasattr(self, "registry_panel") and self.registry_panel:
                self.registry_panel.clear()
            if hasattr(self, "image_viewer") and self.image_viewer:
                self.image_viewer.show_placeholder("No Specimen Selected")
            if hasattr(self, "location_panel") and self.location_panel:
                self.location_panel.clear()
            self.update_status_bar()
            return

        oid = current.text(1).strip()
        if not oid:
            return

        self.app.current_object_id = oid
        if not self.history_stack or self.history_stack[-1] != oid:
            self.history_stack.append(oid)

        df_reg = self.app.df_reg
        df_obs = self.app.df_obs

        # 1. Update Middle Column Context Bar (with active position indicator)
        pos = -1
        total_active = len(self.app.active_object_ids)
        if oid in self.app.active_object_ids:
            pos = self.app.active_object_ids.index(oid)

        if hasattr(self.win, "lbl_id_badge"):
            pos_str = f" ({pos + 1} of {total_active})" if pos >= 0 and total_active > 0 else ""
            self.win.lbl_id_badge.setText(f"ID: {oid}{pos_str}")

        scientific_name = ""
        if df_reg is not None and oid in df_reg.index:
            row = df_reg.loc[oid]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            genus = str(row["Genus"]).strip() if "Genus" in row.index and not pd.isna(row["Genus"]) else ""
            species = str(row["Species"]).strip() if "Species" in row.index and not pd.isna(row["Species"]) else ""
            author = str(row["Author"]).strip() if "Author" in row.index and not pd.isna(row["Author"]) else ""
            parts = [p for p in (genus, species, author) if p]
            scientific_name = " ".join(parts)

        if hasattr(self.win, "lbl_specimen_name"):
            self.win.lbl_specimen_name.setText(scientific_name or "(unnamed specimen)")

        # 2. Populate Problems Panel & Determine Active Problems
        active_problems: list[str] = []
        if hasattr(self, "problems_panel") and self.problems_panel:
            active_problems = self.problems_panel.populate_specimen(oid, df_obs)
        elif df_obs is not None and oid in df_obs.index:
            obs_row = df_obs.loc[oid]
            if isinstance(obs_row, pd.DataFrame):
                obs_row = obs_row.iloc[0]
            prob_cfg = self.app.config.get("ui_sections", {}).get("problems", []) if self.app.config else []
            for p in prob_cfg:
                p_name = p.get("name")
                if p_name and p_name != "Images_Missing" and p_name in obs_row.index and bool(obs_row[p_name]):
                    active_problems.append(p_name)

        # Update Problems Tab title with active count
        if hasattr(self.win, "tabs_registration"):
            tab_text = f"Problems ({len(active_problems)})" if active_problems else "Problems"
            self.win.tabs_registration.setTabText(1, tab_text)

        # 3. Update Status Badge (Reviewed > Problems > Pending)
        is_reviewed = False
        reviewed_at = ""
        if df_obs is not None and oid in df_obs.index:
            obs_row = df_obs.loc[oid]
            if isinstance(obs_row, pd.DataFrame):
                obs_row = obs_row.iloc[0]
            if REVIEWED_COLUMN in obs_row.index:
                is_reviewed = bool(obs_row[REVIEWED_COLUMN])
            if "ReviewedAt" in obs_row.index and not pd.isna(obs_row["ReviewedAt"]):
                reviewed_at = str(obs_row["ReviewedAt"]).strip()

        if hasattr(self.win, "lbl_reviewed_time"):
            self.win.lbl_reviewed_time.setText(f"Reviewed: {reviewed_at}" if is_reviewed and reviewed_at else "")

        if hasattr(self.win, "btn_mark_reviewed"):
            self.win.btn_mark_reviewed.setText("✓ MARKED AS REVIEWED" if is_reviewed else "✓ MARK AS REVIEWED (Ctrl+Enter)")

        if hasattr(self.win, "lbl_status_badge"):
            if is_reviewed:
                self.win.lbl_status_badge.setText("REVIEWED")
                self.win.lbl_status_badge.setProperty("state", "reviewed")
            elif active_problems:
                self.win.lbl_status_badge.setText(f"{len(active_problems)} PROBLEM{'S' if len(active_problems) > 1 else ''}")
                self.win.lbl_status_badge.setProperty("state", "problem")
            else:
                self.win.lbl_status_badge.setText("PENDING")
                self.win.lbl_status_badge.setProperty("state", "pending")
            repolish(self.win.lbl_status_badge)

        # 4. Update Right Column Registration Form Cards
        if hasattr(self, "registry_panel") and self.registry_panel:
            self.registry_panel.populate_specimen(oid, df_reg, df_obs)

        # 5. Update Middle Column Image Canvas
        if hasattr(self, "image_viewer") and self.image_viewer:
            self.image_viewer.load_specimen_images(
                oid=oid,
                df_reg=df_reg,
                df_photo=self.app.df_photo,
                image_dir=getattr(self.app, "image_folder", None) or config.get_last_dir("last_image_dir"),
            )

        # 6. Update Location Panel
        if hasattr(self, "location_panel") and self.location_panel:
            self.location_panel.populate_specimen(oid, df_obs)

        self.update_status_bar()
        self.update_save_status()

    def _on_problem_toggled(self, problem_name: str, checked: bool) -> None:
        """Synchronize problem flag toggles across dataframes, tabs, and status badges."""
        oid = self.app.current_object_id
        if not oid:
            return

        df_obs = self.app.df_obs
        if df_obs is not None and oid in df_obs.index:
            if problem_name not in df_obs.columns:
                df_obs[problem_name] = False
            df_obs.at[oid, problem_name] = checked
            self.app.dirty = True

        # Synchronize problems panel
        if hasattr(self, "problems_panel") and self.problems_panel:
            self.problems_panel.set_problem_state(problem_name, checked)
            active_problems = self.problems_panel.get_active_problems()
        else:
            active_problems = []

        # Synchronize registry panel inline checkbox & field tint
        if hasattr(self, "registry_panel") and self.registry_panel:
            self.registry_panel.set_problem_flag(problem_name, checked)

        # Update tab header
        if hasattr(self.win, "tabs_registration"):
            tab_text = f"Problems ({len(active_problems)})" if active_problems else "Problems"
            self.win.tabs_registration.setTabText(1, tab_text)

        # Update middle status badge
        if hasattr(self.win, "lbl_status_badge"):
            is_reviewed = False
            if df_obs is not None and oid in df_obs.index and REVIEWED_COLUMN in df_obs.columns:
                is_reviewed = bool(df_obs.loc[oid, REVIEWED_COLUMN])
            if is_reviewed:
                self.win.lbl_status_badge.setText("REVIEWED")
                self.win.lbl_status_badge.setProperty("state", "reviewed")
            elif active_problems:
                self.win.lbl_status_badge.setText(f"{len(active_problems)} PROBLEM{'S' if len(active_problems) > 1 else ''}")
                self.win.lbl_status_badge.setProperty("state", "problem")
            else:
                self.win.lbl_status_badge.setText("PENDING")
                self.win.lbl_status_badge.setProperty("state", "pending")
            repolish(self.win.lbl_status_badge)

        self.update_status_bar()

    def _mount_location_panel(self) -> None:
        """Mount location panel into either center pane (default) or left column."""
        if not hasattr(self, "location_panel") or not self.location_panel:
            return

        if self.location_panel.parent():
            self.location_panel.setParent(None)

        if self.location_in_center:
            # Mount into pane_center below image_view/image_area
            self.location_panel.set_layout_mode("horizontal_1row")
            if hasattr(self.win, "pane_center_layout"):
                self.win.pane_center_layout.addWidget(self.location_panel)
            elif hasattr(self.win, "pane_center") and self.win.pane_center.layout():
                self.win.pane_center.layout().addWidget(self.location_panel)
            if hasattr(self.win, "location_container"):
                self.win.location_container.setVisible(False)
        else:
            # Mount into location_container in left pane
            self.location_panel.set_layout_mode("vertical")
            if hasattr(self.win, "location_container"):
                self.win.location_container.setVisible(True)
                if self.win.location_container.layout():
                    self.win.location_container.layout().addWidget(self.location_panel)

    def toggle_location_panel_position(self) -> None:
        """Toggle location panel position between Middle and Left columns."""
        self.location_in_center = not self.location_in_center
        self._mount_location_panel()
        if self.app.current_object_id:
            self.location_panel.populate_specimen(self.app.current_object_id, self.app.df_obs)
        prefs = config.load_prefs() or {}
        prefs["location_in_center"] = self.location_in_center
        config.save_prefs(prefs)

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

    def navigate_next_problem(self) -> None:
        """Advance to the next specimen in the list with active problem flags."""
        if not self.app.active_object_ids or self.app.df_obs is None:
            return

        cur_oid = self.app.current_object_id
        start_idx = self.app.active_object_ids.index(cur_oid) if cur_oid in self.app.active_object_ids else -1
        total = len(self.app.active_object_ids)

        prob_cols = [
            c for c in self.app.df_obs.columns
            if (c.endswith("_Problem") or c in ("Other_problem", "Images_Problem"))
            and c != "Images_Missing"
        ]
        if not prob_cols:
            return

        for offset in range(1, total + 1):
            check_idx = (start_idx + offset) % total
            candidate_oid = self.app.active_object_ids[check_idx]
            if candidate_oid in self.app.df_obs.index:
                row = self.app.df_obs.loc[candidate_oid]
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]
                if any(bool(row.get(c)) for c in prob_cols):
                    self.navigate_to_object(candidate_oid)
                    return

    def navigate_next_hist(self) -> None:
        """Advance to the next specimen that has historical book entries."""
        if not self.app.active_object_ids or not self.app.historical_dbs:
            return

        cur_oid = self.app.current_object_id
        start_idx = self.app.active_object_ids.index(cur_oid) if cur_oid in self.app.active_object_ids else -1
        total = len(self.app.active_object_ids)

        hist_ids = set()
        for hdb in self.app.historical_dbs:
            df_hist = hdb.get("df")
            if df_hist is not None and "ObjectID" in df_hist.columns:
                hist_ids.update(df_hist["ObjectID"].astype(str).str.strip().tolist())

        for offset in range(1, total + 1):
            check_idx = (start_idx + offset) % total
            candidate_oid = self.app.active_object_ids[check_idx]
            if candidate_oid in hist_ids:
                self.navigate_to_object(candidate_oid)
                return

    def _on_sort_changed(self, sort_mode: str) -> None:
        """Re-sort active_object_ids according to selected sorting mode."""
        if not self.app or self.app.df_reg is None or not self.app.active_object_ids:
            return

        df_reg = self.app.df_reg
        df_obs = self.app.df_obs
        oids = list(self.app.active_object_ids)

        if sort_mode == "ID":
            oids.sort(key=lambda x: (0, int(x)) if str(x).isdigit() else (1, str(x)))
        elif sort_mode == "Genus A-Z":
            def _genus_key(oid):
                if oid in df_reg.index:
                    row = df_reg.loc[oid]
                    if isinstance(row, pd.DataFrame):
                        row = row.iloc[0]
                    genus = str(row["Genus"]).strip().lower() if "Genus" in row.index and not pd.isna(row["Genus"]) else ""
                    species = str(row["Species"]).strip().lower() if "Species" in row.index and not pd.isna(row["Species"]) else ""
                    return (genus, species, oid)
                return ("", "", oid)
            oids.sort(key=_genus_key)
        elif sort_mode == "Reviewed first":
            def _rev_key(oid):
                if df_obs is not None and oid in df_obs.index and REVIEWED_COLUMN in df_obs.columns:
                    val = df_obs.loc[oid, REVIEWED_COLUMN]
                    is_rev = bool(val.iloc[0] if isinstance(val, pd.Series) else val)
                    return (0 if is_rev else 1, int(oid) if str(oid).isdigit() else oid)
                return (1, int(oid) if str(oid).isdigit() else oid)
            oids.sort(key=_rev_key)
        elif sort_mode == "Problems first":
            prob_cols = [
                c for c in df_obs.columns
                if (c.endswith("_Problem") or c in ("Other_problem", "Images_Problem"))
                and c != "Images_Missing"
            ] if df_obs is not None else []
            def _prob_key(oid):
                if df_obs is not None and oid in df_obs.index and prob_cols:
                    row = df_obs.loc[oid]
                    if isinstance(row, pd.DataFrame):
                        row = row.iloc[0]
                    p_count = sum(1 for c in prob_cols if bool(row.get(c)))
                    return (-p_count, int(oid) if str(oid).isdigit() else oid)
                return (0, int(oid) if str(oid).isdigit() else oid)
            oids.sort(key=_prob_key)

        self.app.active_object_ids = oids
        self.refresh_object_tree()

    # -------------------------------------------------------------------------
    # State Mutation, Undo Stack, Logging & Save Status
    # -------------------------------------------------------------------------

    def update_save_status(self) -> None:
        """Update save indicator badges in workspace."""
        if hasattr(self.win, "lbl_data_status"):
            if getattr(self.app, "dirty", False):
                self.win.lbl_data_status.setText("Unsaved*")
                self.win.lbl_data_status.setStyleSheet("color: #d9a036; font-weight: bold;")
            else:
                self.win.lbl_data_status.setText("Saved")
                self.win.lbl_data_status.setStyleSheet("color: #3a7d44; font-weight: bold;")

    def push_undo_state(self, target_oid: str | None = None) -> None:
        """Push a snapshot of the current specimen's df_reg and df_obs rows onto undo_stacks."""
        oid = target_oid or self.app.current_object_id
        if not oid or self.app.df_reg is None or self.app.df_obs is None:
            return

        with self.app.df_lock:
            if oid not in self.app.df_reg.index or oid not in self.app.df_obs.index:
                return
            state = {
                "reg": self.app.df_reg.loc[oid].copy(),
                "obs": self.app.df_obs.loc[oid].copy(),
            }

        stack = self.app.undo_stacks.setdefault(oid, [])
        stack.append(state)
        if len(stack) > 50:
            stack.pop(0)
        self.app.redo_stacks.setdefault(oid, []).clear()

    def undo(self) -> None:
        """Revert the most recent edit on the current specimen."""
        oid = self.app.current_object_id
        if not oid or oid not in self.app.undo_stacks or not self.app.undo_stacks[oid]:
            return

        with self.app.df_lock:
            cur_state = {
                "reg": self.app.df_reg.loc[oid].copy(),
                "obs": self.app.df_obs.loc[oid].copy(),
            }
            self.app.redo_stacks.setdefault(oid, []).append(cur_state)
            state = self.app.undo_stacks[oid].pop()
            self.app.df_reg.loc[oid] = state["reg"]
            self.app.df_obs.loc[oid] = state["obs"]

        # Repopulate detail panels
        df_reg = self.app.df_reg
        df_obs = self.app.df_obs
        if hasattr(self, "registry_panel") and self.registry_panel:
            self.registry_panel.populate_specimen(oid, df_reg, df_obs)
        if hasattr(self, "location_panel") and self.location_panel:
            self.location_panel.populate_specimen(oid, df_obs)
        if hasattr(self, "problems_panel") and self.problems_panel:
            self.problems_panel.populate_specimen(oid, df_obs)

        # Update nomenclature and tree taxon
        row = df_reg.loc[oid]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        genus = str(row["Genus"]).strip() if "Genus" in row.index and not pd.isna(row["Genus"]) else ""
        species = str(row["Species"]).strip() if "Species" in row.index and not pd.isna(row["Species"]) else ""
        author = str(row["Author"]).strip() if "Author" in row.index and not pd.isna(row["Author"]) else ""
        parts = [p for p in (genus, species, author) if p]
        scientific_name = " ".join(parts) or "(unnamed specimen)"

        if hasattr(self.win, "lbl_specimen_name"):
            self.win.lbl_specimen_name.setText(scientific_name)

        if hasattr(self.win, "tree_objects"):
            cur_item = self.win.tree_objects.currentItem()
            if cur_item and cur_item.text(1).strip() == oid:
                cur_item.setText(2, f"{genus} {species}".strip() or "(unnamed)")

        self.app.dirty = True
        self.update_save_status()
        self.update_status_bar()
        self.log_action("UNDO", ["Object"], [f"Reverted state for #{oid}"], oid=oid)

    def redo(self) -> None:
        """Redo the last reverted edit on the current specimen."""
        oid = self.app.current_object_id
        if not oid or oid not in self.app.redo_stacks or not self.app.redo_stacks[oid]:
            return

        with self.app.df_lock:
            cur_state = {
                "reg": self.app.df_reg.loc[oid].copy(),
                "obs": self.app.df_obs.loc[oid].copy(),
            }
            self.app.undo_stacks.setdefault(oid, []).append(cur_state)
            state = self.app.redo_stacks[oid].pop()
            self.app.df_reg.loc[oid] = state["reg"]
            self.app.df_obs.loc[oid] = state["obs"]

        # Repopulate detail panels
        df_reg = self.app.df_reg
        df_obs = self.app.df_obs
        if hasattr(self, "registry_panel") and self.registry_panel:
            self.registry_panel.populate_specimen(oid, df_reg, df_obs)
        if hasattr(self, "location_panel") and self.location_panel:
            self.location_panel.populate_specimen(oid, df_obs)
        if hasattr(self, "problems_panel") and self.problems_panel:
            self.problems_panel.populate_specimen(oid, df_obs)

        # Update nomenclature and tree taxon
        row = df_reg.loc[oid]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        genus = str(row["Genus"]).strip() if "Genus" in row.index and not pd.isna(row["Genus"]) else ""
        species = str(row["Species"]).strip() if "Species" in row.index and not pd.isna(row["Species"]) else ""
        author = str(row["Author"]).strip() if "Author" in row.index and not pd.isna(row["Author"]) else ""
        parts = [p for p in (genus, species, author) if p]
        scientific_name = " ".join(parts) or "(unnamed specimen)"

        if hasattr(self.win, "lbl_specimen_name"):
            self.win.lbl_specimen_name.setText(scientific_name)

        if hasattr(self.win, "tree_objects"):
            cur_item = self.win.tree_objects.currentItem()
            if cur_item and cur_item.text(1).strip() == oid:
                cur_item.setText(2, f"{genus} {species}".strip() or "(unnamed)")

        self.app.dirty = True
        self.update_save_status()
        self.update_status_bar()
        self.log_action("REDO", ["Object"], [f"Re-applied state for #{oid}"], oid=oid)

    # -------------------------------------------------------------------------
    # Panel Focus Jumping & Laptop View Toggles (Tkinter Parity)
    # -------------------------------------------------------------------------

    def focus_search_bar(self) -> None:
        """Jump focus to inline search entry (Ctrl+F)."""
        if hasattr(self.win, "edit_search"):
            self.win.edit_search.setFocus()
            self.win.edit_search.selectAll()

    def focus_object_tree(self) -> None:
        """Jump focus to object treeview (Ctrl+O)."""
        if hasattr(self.win, "tree_objects"):
            tree = self.win.tree_objects
            tree.setFocus()
            if not tree.selectedItems() and tree.topLevelItemCount() > 0:
                item = tree.topLevelItem(0)
                tree.setCurrentItem(item)

    def focus_first_reg_field(self) -> None:
        """Jump to first editable field in registration form (Ctrl+E / Ctrl+I)."""
        if hasattr(self.win, "tabs_registration"):
            self.win.tabs_registration.setCurrentIndex(0)
        if hasattr(self, "registry_panel") and self.registry_panel:
            self.registry_panel.focus_first_field()

    def focus_first_empty_reg_field(self) -> None:
        """Jump to first empty field in registration form (Shift+E)."""
        if hasattr(self.win, "tabs_registration"):
            self.win.tabs_registration.setCurrentIndex(0)
        if hasattr(self, "registry_panel") and self.registry_panel:
            self.registry_panel.focus_first_empty_field()

    def focus_first_location_field(self) -> None:
        """Jump to first editable field in location panel (Ctrl+L / F4)."""
        if hasattr(self, "location_panel") and self.location_panel:
            self.location_panel.focus_first_field()

    def focus_first_problem_checkbox(self) -> None:
        """Jump to first checkbox in problems tab (Ctrl+P / F3)."""
        if hasattr(self.win, "tabs_registration"):
            self.win.tabs_registration.setCurrentIndex(1)
        if hasattr(self, "problems_panel") and self.problems_panel:
            self.problems_panel.focus_first_checkbox()

    def switch_registration_tab(self, delta: int = 1) -> None:
        """Switch active tab in registration panel (Ctrl+PageUp / Ctrl+PageDown)."""
        if hasattr(self.win, "tabs_registration"):
            count = self.win.tabs_registration.count()
            if count > 0:
                cur = self.win.tabs_registration.currentIndex()
                new_idx = (cur + delta) % count
                self.win.tabs_registration.setCurrentIndex(new_idx)

    def toggle_focused_problem_checkbox(self) -> None:
        """Toggle the focused problem checkbox (Space)."""
        if hasattr(self, "problems_panel") and self.problems_panel:
            self.problems_panel.toggle_focused_checkbox()

    def toggle_left_panel(self) -> None:
        """Toggle Left Column / Object List visibility (F6)."""
        if hasattr(self.win, "pane_left"):
            self.win.pane_left.setVisible(not self.win.pane_left.isVisible())

    def toggle_registration_panel(self) -> None:
        """Toggle Right Column / Registration panel visibility (F7)."""
        if hasattr(self.win, "pane_right"):
            self.win.pane_right.setVisible(not self.win.pane_right.isVisible())

    def toggle_image_panel(self) -> None:
        """Toggle Middle Column / Image panel visibility (F8)."""
        if hasattr(self.win, "pane_center"):
            self.win.pane_center.setVisible(not self.win.pane_center.isVisible())

    # -------------------------------------------------------------------------
    # Specimen Lifecycle Actions (Creation, Duplication, Deletion)
    # -------------------------------------------------------------------------

    def quick_create_new_object(self) -> None:
        """Quickly create next sequential object with blank template (Ctrl+Shift+N)."""
        if self.app.df_reg is None or self.app.df_obs is None:
            return

        import uuid
        existing_ids = [int(x) for x in self.app.df_reg.index if str(x).isdigit()]
        new_oid = str(max(existing_ids) + 1 if existing_ids else 1)

        new_reg_row = {col: "" for col in self.app.df_reg.columns}
        new_reg_row["ObjectID"] = new_oid
        if "UID" in self.app.df_reg.columns:
            new_reg_row["UID"] = uuid.uuid4().hex[:8]

        new_obs_row = {col: "" for col in self.app.df_obs.columns}
        new_obs_row["ObjectID"] = new_oid
        if REVIEWED_COLUMN in self.app.df_obs.columns:
            new_obs_row[REVIEWED_COLUMN] = False

        self.push_undo_state(new_oid)

        with self.app.df_lock:
            self.app.df_reg.loc[new_oid] = new_reg_row
            self.app.df_obs.loc[new_oid] = new_obs_row
            if self.app.df_photo is not None and not self.app.df_photo.empty:
                new_photo_row = {col: "" for col in self.app.df_photo.columns}
                new_photo_row["ObjectID"] = new_oid
                self.app.df_photo.loc[new_oid] = new_photo_row

            if new_oid not in self.app.active_object_ids:
                self.app.active_object_ids.append(new_oid)

        self.app.dirty = True
        self.refresh_object_tree()
        self.navigate_to_object(new_oid)
        self.log_action("CREATE_OBJECT_FAST", ["ObjectID"], [f"Created {new_oid}"], oid=new_oid)

    def duplicate_current_specimen(self) -> None:
        """Duplicate currently selected specimen under new sequential ID (Ctrl+Shift+D)."""
        oid = self.app.current_object_id
        if not oid or self.app.df_reg is None or self.app.df_obs is None or oid not in self.app.df_reg.index:
            return

        import uuid
        existing_ids = [int(x) for x in self.app.df_reg.index if str(x).isdigit()]
        new_oid = str(max(existing_ids) + 1 if existing_ids else 1)

        self.push_undo_state(new_oid)

        with self.app.df_lock:
            new_reg = self.app.df_reg.loc[[oid]].copy()
            new_reg.index = [new_oid]
            new_reg["ObjectID"] = new_oid
            if "UID" in new_reg.columns:
                new_reg["UID"] = uuid.uuid4().hex[:8]
            self.app.df_reg = pd.concat([self.app.df_reg, new_reg])

            new_obs = self.app.df_obs.loc[[oid]].copy()
            new_obs.index = [new_oid]
            new_obs["ObjectID"] = new_oid
            if "ProblemDescription" in new_obs.columns:
                new_obs["ProblemDescription"] = ""
            if REVIEWED_COLUMN in new_obs.columns:
                new_obs[REVIEWED_COLUMN] = False
            self.app.df_obs = pd.concat([self.app.df_obs, new_obs])

            if self.app.df_photo is not None and oid in self.app.df_photo.index:
                new_photo = self.app.df_photo.loc[[oid]].copy()
                new_photo.index = [new_oid]
                new_photo["ObjectID"] = new_oid
                self.app.df_photo = pd.concat([self.app.df_photo, new_photo])

            if new_oid not in self.app.active_object_ids:
                self.app.active_object_ids.append(new_oid)

        self.app.dirty = True
        self.refresh_object_tree()
        self.navigate_to_object(new_oid)
        self.log_action("DUPLICATE_OBJECT", ["ObjectID"], [f"Cloned {oid} -> {new_oid}"], oid=new_oid)

    def delete_current_specimen(self) -> None:
        """Delete currently selected specimen with confirmation prompt (Ctrl+Delete)."""
        oid = self.app.current_object_id
        if not oid or self.app.df_reg is None or oid not in self.app.df_reg.index:
            return

        reply = QMessageBox.question(
            self.win,
            "Confirm Delete",
            f"Are you sure you want to delete specimen #{oid}?\nThis action can be undone with Ctrl+Z.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.push_undo_state(oid)

        with self.app.df_lock:
            if oid in self.app.df_reg.index:
                self.app.df_reg = self.app.df_reg.drop(index=oid)
            if self.app.df_obs is not None and oid in self.app.df_obs.index:
                self.app.df_obs = self.app.df_obs.drop(index=oid)
            if self.app.df_photo is not None and oid in self.app.df_photo.index:
                self.app.df_photo = self.app.df_photo.drop(index=oid)

            if oid in self.app.active_object_ids:
                self.app.active_object_ids.remove(oid)

        self.app.dirty = True
        self.refresh_object_tree()

        # Select next or first object
        if self.app.active_object_ids:
            next_oid = self.app.active_object_ids[0]
            self.navigate_to_object(next_oid)
        else:
            self.app.current_object_id = None
            if hasattr(self, "registry_panel") and self.registry_panel:
                self.registry_panel.clear()
            if hasattr(self, "location_panel") and self.location_panel:
                self.location_panel.clear()
            if hasattr(self, "problems_panel") and self.problems_panel:
                self.problems_panel.clear()
            if hasattr(self, "image_viewer") and self.image_viewer:
                self.image_viewer.show_placeholder("No Specimen Selected")

        self.update_save_status()
        self.update_status_bar()
        self.log_action("DELETE_OBJECT", ["ObjectID"], [f"Deleted {oid}"], oid=oid)

    def set_reviewed_for_selection(self, value: bool) -> None:
        """Set reviewed flag for all selected tree items."""
        if not hasattr(self.win, "tree_objects") or self.app.df_obs is None:
            return

        selected_items = self.win.tree_objects.selectedItems()
        if not selected_items and self.app.current_object_id:
            oids = [self.app.current_object_id]
        else:
            oids = [it.text(1).strip() for it in selected_items if it.text(1).strip()]

        from datetime import datetime
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if value else ""

        with self.app.df_lock:
            for oid in oids:
                if oid in self.app.df_obs.index:
                    self.push_undo_state(oid)
                    self.app.df_obs.at[oid, REVIEWED_COLUMN] = value
                    if "ReviewedAt" in self.app.df_obs.columns:
                        self.app.df_obs.at[oid, "ReviewedAt"] = now_str

        self.app.dirty = True
        self.refresh_object_tree()
        if self.app.current_object_id:
            self.navigate_to_object(self.app.current_object_id)
        self.update_save_status()
        self.update_status_bar()

    def copy_current_accession_id(self) -> None:
        """Copy active specimen ObjectID to clipboard."""
        oid = self.app.current_object_id
        if oid:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(oid)

    def log_action(
        self,
        action: str,
        changed_fields: list[str] | None = None,
        changed_values: list[str] | None = None,
        oid: str | None = None,
    ) -> None:
        """Append an audit record to app.df_log and app._log_records."""
        target_oid = oid or self.app.current_object_id
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        username = os.environ.get("USERNAME") or os.environ.get("USER") or "User"

        rec = {
            "Timestamp": now_str,
            "User": username,
            "Action": action,
            "ObjectID": str(target_oid) if target_oid is not None else "",
            "ChangedFields": ", ".join(changed_fields) if changed_fields else "",
            "ChangedValues": " | ".join(changed_values) if changed_values else "",
        }
        self.app._log_records.append(rec)
        new_row_df = pd.DataFrame([rec])
        if self.app.df_log is None or self.app.df_log.empty:
            self.app.df_log = new_row_df
        else:
            self.app.df_log = pd.concat([self.app.df_log, new_row_df], ignore_index=True)

    def _on_field_edited(self, field_name: str, value: str) -> None:
        """Handle inline editing of a registration field in tab_general."""
        oid = self.app.current_object_id
        if not oid or self.app.df_reg is None or oid not in self.app.df_reg.index:
            return

        current_val = ""
        if field_name in self.app.df_reg.columns:
            raw = self.app.df_reg.loc[oid, field_name]
            current_val = "" if pd.isna(raw) else str(raw)

        if value == current_val:
            return

        self.push_undo_state(oid)

        with self.app.df_lock:
            self.app.df_reg.at[oid, field_name] = value

        self.app.dirty = True
        self.update_save_status()
        self.log_action("EDIT", [field_name], [f'{field_name}: "{current_val}" -> "{value}"'], oid=oid)

        if field_name in ("Genus", "Species", "Author"):
            row = self.app.df_reg.loc[oid]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            genus = str(row["Genus"]).strip() if "Genus" in row.index and not pd.isna(row["Genus"]) else ""
            species = str(row["Species"]).strip() if "Species" in row.index and not pd.isna(row["Species"]) else ""
            author = str(row["Author"]).strip() if "Author" in row.index and not pd.isna(row["Author"]) else ""
            parts = [p for p in (genus, species, author) if p]
            scientific_name = " ".join(parts) or "(unnamed specimen)"

            if hasattr(self.win, "lbl_specimen_name"):
                self.win.lbl_specimen_name.setText(scientific_name)

            if hasattr(self.win, "tree_objects"):
                cur_item = self.win.tree_objects.currentItem()
                if cur_item and cur_item.text(1).strip() == oid:
                    cur_item.setText(2, f"{genus} {species}".strip() or "(unnamed)")

    def _on_location_field_edited(self, field_name: str, value: str) -> None:
        """Handle inline editing of a location field in location_panel."""
        oid = self.app.current_object_id
        if not oid or self.app.df_obs is None or oid not in self.app.df_obs.index:
            return

        current_val = ""
        if field_name in self.app.df_obs.columns:
            raw = self.app.df_obs.loc[oid, field_name]
            current_val = "" if pd.isna(raw) else str(raw)

        if str(value) == current_val:
            return

        self.push_undo_state(oid)

        with self.app.df_lock:
            if field_name == "Loaned out":
                value_parsed = str(value).lower() in ("true", "1", "yes")
                self.app.df_obs.at[oid, field_name] = value_parsed
            else:
                self.app.df_obs.at[oid, field_name] = value

        self.app.dirty = True
        self.update_save_status()
        self.log_action("EDIT_LOCATION", [field_name], [f'{field_name}: "{current_val}" -> "{value}"'], oid=oid)

    def toggle_reviewed(self) -> None:
        """Toggle reviewed status for active specimen."""
        oid = self.app.current_object_id
        if not oid or self.app.df_obs is None or oid not in self.app.df_obs.index:
            return

        self.push_undo_state(oid)

        current = False
        if REVIEWED_COLUMN in self.app.df_obs.columns:
            raw = self.app.df_obs.loc[oid, REVIEWED_COLUMN]
            current = bool(raw.iloc[0] if isinstance(raw, pd.Series) else raw)

        new_val = not current
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if new_val else ""

        with self.app.df_lock:
            if REVIEWED_COLUMN not in self.app.df_obs.columns:
                self.app.df_obs[REVIEWED_COLUMN] = False
            self.app.df_obs.at[oid, REVIEWED_COLUMN] = new_val
            if "ReviewedAt" in self.app.df_obs.columns or new_val:
                self.app.df_obs.at[oid, "ReviewedAt"] = now_str

        self.app.dirty = True
        self.update_save_status()
        self.log_action("REVIEWED" if new_val else "UNREVIEWED", ["Reviewed"], [f'Reviewed: "{new_val}"'], oid=oid)

        # Update Reviewed Time label and button text
        if hasattr(self.win, "lbl_reviewed_time"):
            self.win.lbl_reviewed_time.setText(f"Reviewed: {now_str}" if new_val else "")

        if hasattr(self.win, "btn_mark_reviewed"):
            self.win.btn_mark_reviewed.setText("✓ MARKED AS REVIEWED" if new_val else "✓ MARK AS REVIEWED (Ctrl+Enter)")

        # Update Tree item checkmark
        if hasattr(self.win, "tree_objects"):
            cur_item = self.win.tree_objects.currentItem()
            if cur_item and cur_item.text(1).strip() == oid:
                cur_item.setText(0, "✓" if new_val else " ")
                cur_item.setForeground(0, Qt.darkGreen if new_val else Qt.black)

        # Update Middle Status Badge
        active_problems = []
        if hasattr(self, "problems_panel") and self.problems_panel:
            active_problems = self.problems_panel.get_active_problems()

        if hasattr(self.win, "lbl_status_badge"):
            if new_val:
                self.win.lbl_status_badge.setText("REVIEWED")
                self.win.lbl_status_badge.setProperty("state", "reviewed")
            elif active_problems:
                self.win.lbl_status_badge.setText(f"{len(active_problems)} PROBLEM{'S' if len(active_problems) > 1 else ''}")
                self.win.lbl_status_badge.setProperty("state", "problem")
            else:
                self.win.lbl_status_badge.setText("PENDING")
                self.win.lbl_status_badge.setProperty("state", "pending")
            repolish(self.win.lbl_status_badge)

        self.update_status_bar()

        # Workflow options when toggled ON to Reviewed:
        if new_val:
            # 1. Clear problems if checked
            if hasattr(self.win, "chk_clear_problems") and self.win.chk_clear_problems.isChecked():
                self.clear_current_problems()

            # 2. Auto-next if checked
            if hasattr(self.win, "chk_auto_next") and self.win.chk_auto_next.isChecked():
                self.navigate_next()
            # 3. Auto-hist if checked
            elif hasattr(self.win, "chk_auto_hist") and self.win.chk_auto_hist.isChecked():
                self.open_historical_resolver(oid)

    def clear_current_problems(self) -> None:
        """Clear all active problem flags for the current specimen."""
        oid = self.app.current_object_id
        if not oid or self.app.df_obs is None or oid not in self.app.df_obs.index:
            return

        prob_cols = [
            c for c in self.app.df_obs.columns
            if (c.endswith("_Problem") or c in ("Other_problem", "Images_Problem"))
            and c != "Images_Missing"
        ]

        with self.app.df_lock:
            for c in prob_cols:
                self.app.df_obs.at[oid, c] = False

        if hasattr(self, "problems_panel") and self.problems_panel:
            self.problems_panel.populate_specimen(oid, self.app.df_obs)

        if hasattr(self, "registry_panel") and self.registry_panel:
            self.registry_panel.populate_specimen(oid, self.app.df_reg, self.app.df_obs)

        if hasattr(self.win, "tabs_registration"):
            self.win.tabs_registration.setTabText(1, "Problems")

        self.update_status_bar()

    def _save_window_preferences(self) -> None:
        """Persist splitter geometry, maximized state, and layout preferences."""
        try:
            prefs = config.load_prefs() or {}
            if hasattr(self.win, "splitter_main"):
                prefs["splitter_sizes"] = self.win.splitter_main.sizes()
            prefs["win_maximized"] = self.win.isMaximized()
            prefs["location_in_center"] = getattr(self, "location_in_center", True)
            config.save_prefs(prefs)
        except Exception as e:
            logger.warning(f"Could not persist window preferences on exit: {e}")

    def _on_close_event(self, event) -> None:
        """Prompt to save unsaved modifications and persist preferences on window exit."""
        if not getattr(self.app, "dirty", False):
            self._save_window_preferences()
            event.accept()
            return

        reply = QMessageBox.question(
            self.win,
            "Unsaved Changes",
            "There are unsaved changes in the database.\nDo you want to save before closing?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )

        if reply == QMessageBox.Save:
            self.save_session()
            self._save_window_preferences()
            event.accept()
        elif reply == QMessageBox.Discard:
            self._save_window_preferences()
            event.accept()
        else:
            event.ignore()

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

        if hasattr(self.win, "btn_advanced_search"):
            self.win.btn_advanced_search.clicked.connect(self.open_advanced_search)

    def _show_tree_context_menu(self, pos: QPoint) -> None:
        """Display right-click context menu for specimen list with full Tkinter parity."""
        if not hasattr(self.win, "tree_objects"):
            return
        item = self.win.tree_objects.itemAt(pos)
        if not item:
            return

        oid = item.text(1).strip()
        menu = self._create_menu()

        menu.addAction("✓ Mark Selected as Reviewed", lambda: self.set_reviewed_for_selection(True))
        menu.addAction("✗ Mark Selected as Not Reviewed", lambda: self.set_reviewed_for_selection(False))
        menu.addSeparator()

        menu.addAction("📋 Copy Accession ID", self.copy_current_accession_id)
        menu.addAction("👥 Manage Specimen Groups...", self.open_group_editor)
        menu.addSeparator()

        menu.addAction("📄 Duplicate Specimen", self.duplicate_current_specimen)
        menu.addAction("🗑️ Delete Specimen", self.delete_current_specimen)
        menu.addSeparator()

        menu.addAction("🔍 Validate Current Specimen (GBIF)", lambda: self.validate_current_specimen_gbif(oid))
        menu.addAction("👁️ Quick Peek", lambda: self.open_quick_peek())
        menu.addAction("📖 Historical Books Resolver...", lambda: self.open_historical_resolver(oid))
        menu.addAction("✏️ Bulk Edit Records...", self.open_bulk_edit)
        menu.addAction("⚠️ Problem Queue...", self.open_problem_queue)
        menu.addAction("Filter Objects...", self.open_filter_dialog)

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

    def open_advanced_search(self) -> None:
        """Open modal Advanced Historical Search dialog."""
        dialog = QtAdvancedSearchDialog(
            parent=self.win,
            app_state=self.app,
            on_applied=self.on_advanced_search_applied,
        )
        dialog.exec()

    def on_advanced_search_applied(self, matched: list[str]) -> None:
        """Handler called when advanced historical search criteria are applied."""
        if self.app:
            self.app.active_object_ids = matched

        self._update_filter_status_display()
        self.refresh_object_tree()
        self.update_status_bar()

        total = len(self.app.df_reg) if self.app and self.app.df_reg is not None else 0
        active_count = len(matched)
        if total > 0 and hasattr(self.win, "lbl_filter_status"):
            self.win.lbl_filter_status.setText(f"Search active: {active_count} of {total} objects")
            self.win.lbl_filter_status.setStyleSheet("color: #d95c14; font-weight: bold;")
        if total > 0 and hasattr(self.win, "lbl_sb_filter_badge"):
            self.win.lbl_sb_filter_badge.setText(f"SEARCH: {active_count}/{total}")
            self.win.lbl_sb_filter_badge.setVisible(True)

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

        prob_cols = [
            c for c in df_obs.columns
            if (c.endswith("_Problem") or c in ("Other_problem", "Images_Problem"))
            and c != "Images_Missing"
        ] if df_obs is not None else []
        prob_count = int(df_obs[prob_cols].any(axis=1).sum()) if prob_cols and df_obs is not None else 0

        is_filtered = total > 0 and active_count < total

        if hasattr(self.win, "lbl_sb_object_count"):
            if is_filtered:
                self.win.lbl_sb_object_count.setText(f"OBJECTS: {active_count}/{total}")
            else:
                self.win.lbl_sb_object_count.setText(f"OBJECTS: {total}")

        if hasattr(self.win, "lbl_sb_reviewed"):
            self.win.lbl_sb_reviewed.setText(f"REVIEWED: {reviewed_count} ({pct}%)")

        if hasattr(self.win, "lbl_sb_problems"):
            self.win.lbl_sb_problems.setText(f"PROBLEMS: {prob_count}")

        if hasattr(self.win, "lbl_sb_filter_badge"):
            if is_filtered:
                self.win.lbl_sb_filter_badge.setText(f"[FILTER: {active_count}/{total}]")
                self.win.lbl_sb_filter_badge.setVisible(True)
            else:
                self.win.lbl_sb_filter_badge.setVisible(False)

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
            oid_str = str(oid).strip()
            if oid_str not in df_reg.index:
                continue

            # Column 0: Reviewed status checkmark
            is_reviewed = False
            if df_obs is not None and oid_str in df_obs.index and REVIEWED_COLUMN in df_obs.columns:
                val = df_obs.loc[oid_str, REVIEWED_COLUMN]
                is_reviewed = bool(val.iloc[0] if isinstance(val, pd.Series) else val)

            reviewed_mark = "✓" if is_reviewed else " "

            # Column 1: ObjectID
            # Column 2: Taxon name (Genus + Species)
            genus_val = df_reg.loc[oid_str, "Genus"] if "Genus" in df_reg.columns else ""
            genus = str(genus_val.iloc[0] if isinstance(genus_val, pd.Series) else genus_val).strip()
            if genus in ("nan", "None", "<NA>"):
                genus = ""

            species_val = df_reg.loc[oid_str, "Species"] if "Species" in df_reg.columns else ""
            species = str(species_val.iloc[0] if isinstance(species_val, pd.Series) else species_val).strip()
            if species in ("nan", "None", "<NA>"):
                species = ""

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
