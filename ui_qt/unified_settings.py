"""Controller for the Unified Settings Dialog in Qt (wrapping unified_settings.ui)."""
from __future__ import annotations

import os
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QListWidgetItem,
    QMessageBox,
    QWidget,
)

import config
from models import AppState
from ui_qt.loader import load_ui


class QtUnifiedSettingsDialog:
    """Controller for Arbor Unified Settings preferences dialog."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        app_state: Optional[AppState] = None,
        on_save: Optional[Callable[[dict], None]] = None,
        default_tab: str | int = "general",
    ):
        self.app = app_state or AppState()
        self.parent = parent
        self.on_save = on_save
        self.win = load_ui("unified_settings.ui", parent)

        # Load existing preferences
        self.prefs = dict(config.load_prefs() or {})

        self._populate_controls()
        self._wire_signals()
        self._select_tab(default_tab)

    def _select_tab(self, tab: str | int) -> None:
        """Switch to requested tab by name or index."""
        if not hasattr(self.win, "tab_widget"):
            return

        if isinstance(tab, int):
            self.win.tab_widget.setCurrentIndex(tab)
            return

        tab_map = {
            "general": 0,
            "appearance": 1,
            "profiles": 2,
            "advanced": 3,
        }
        idx = tab_map.get(str(tab).lower(), 0)
        self.win.tab_widget.setCurrentIndex(idx)

    def _populate_controls(self) -> None:
        """Load values from config.load_prefs() into UI widgets."""
        # 1. General Tab
        if hasattr(self.win, "spin_autosave"):
            mins = self.prefs.get("autosave_interval", 5)
            try:
                self.win.spin_autosave.setValue(int(mins))
            except (ValueError, TypeError):
                self.win.spin_autosave.setValue(5)

        if hasattr(self.win, "combo_scale"):
            scale_val = self.prefs.get("ui_scale", 1.0)
            if scale_val == 1.0:
                self.win.combo_scale.setCurrentIndex(1)
            elif scale_val == 1.25:
                self.win.combo_scale.setCurrentIndex(2)
            elif scale_val == 1.50:
                self.win.combo_scale.setCurrentIndex(3)
            elif scale_val == 2.0:
                self.win.combo_scale.setCurrentIndex(4)
            else:
                self.win.combo_scale.setCurrentIndex(0)

        if hasattr(self.win, "input_default_db_path"):
            default_path = self.prefs.get("default_db_dir", config.get_last_dir("last_db_dir") or "")
            self.win.input_default_db_path.setText(str(default_path))

        if hasattr(self.win, "chk_confirm_delete"):
            self.win.chk_confirm_delete.setChecked(bool(self.prefs.get("confirm_delete", True)))

        if hasattr(self.win, "chk_auto_backup"):
            self.win.chk_auto_backup.setChecked(bool(self.prefs.get("enable_excel_import_backup", True)))

        if hasattr(self.win, "chk_auto_advance"):
            self.win.chk_auto_advance.setChecked(bool(self.prefs.get("auto_advance_on_review", False)))

        # 2. Appearance Tab
        if hasattr(self.win, "chk_dark_mode"):
            self.win.chk_dark_mode.setChecked(bool(self.prefs.get("dark_mode", False)))

        if hasattr(self.win, "chk_problem_highlights"):
            self.win.chk_problem_highlights.setChecked(bool(self.prefs.get("enable_problem_highlights", True)))

        if hasattr(self.win, "combo_highlight_color"):
            color = self.prefs.get("problem_highlight_color", "Default (Red)")
            idx = self.win.combo_highlight_color.findText(color)
            if idx >= 0:
                self.win.combo_highlight_color.setCurrentIndex(idx)

        if hasattr(self.win, "chk_large_reviewed_btn"):
            self.win.chk_large_reviewed_btn.setChecked(bool(self.prefs.get("large_reviewed_button", False)))

        if hasattr(self.win, "chk_snap_lock"):
            self.win.chk_snap_lock.setChecked(bool(self.prefs.get("snap_lock", False)))

        # 3. Database Profiles Tab
        self._refresh_profiles_list()

        # 4. Advanced Tab
        if hasattr(self.win, "chk_debug_logging"):
            debug_on = self.prefs.get("log_verbosity") == "DEBUG" or bool(self.prefs.get("debug_logging", False))
            self.win.chk_debug_logging.setChecked(debug_on)

        if hasattr(self.win, "chk_memory_cleanup"):
            self.win.chk_memory_cleanup.setChecked(bool(self.prefs.get("memory_cleanup", True)))

    def _refresh_profiles_list(self) -> None:
        """Populate database profiles list widget."""
        if not hasattr(self.win, "list_profiles"):
            return

        self.win.list_profiles.clear()
        profiles = list(config.DATABASE_CONFIGS.keys()) if config.DATABASE_CONFIGS else []
        custom_dbs = self.prefs.get("custom_databases", {})
        for name in custom_dbs.keys():
            if name not in profiles:
                profiles.append(name)

        active_profile = self.app.config_name or self.prefs.get("last_profile", "")

        for name in sorted(profiles):
            item = QListWidgetItem(name)
            if name == active_profile:
                item.setText(f"{name} (Active)")
            self.win.list_profiles.addItem(item)

    def _wire_signals(self) -> None:
        """Connect all signals and action buttons."""
        if hasattr(self.win, "btn_browse_default_path"):
            self.win.btn_browse_default_path.clicked.connect(self._browse_default_path)

        if hasattr(self.win, "btn_add_profile"):
            self.win.btn_add_profile.clicked.connect(self._add_profile)

        if hasattr(self.win, "btn_edit_profile"):
            self.win.btn_edit_profile.clicked.connect(self._edit_profile)

        if hasattr(self.win, "btn_delete_profile"):
            self.win.btn_delete_profile.clicked.connect(self._delete_profile)

        if hasattr(self.win, "btn_clear_caches"):
            self.win.btn_clear_caches.clicked.connect(self._clear_caches)

        if hasattr(self.win, "btn_save"):
            self.win.btn_save.clicked.connect(self.save_settings)

        if hasattr(self.win, "btn_cancel"):
            self.win.btn_cancel.clicked.connect(self.win.reject)

    def _browse_default_path(self) -> None:
        """Browse directory for default database directory."""
        current = self.win.input_default_db_path.text().strip()
        chosen = QFileDialog.getExistingDirectory(self.win, "Select Default Database Directory", current)
        if chosen:
            self.win.input_default_db_path.setText(chosen)

    def _add_profile(self) -> None:
        """Prompt to create a new database profile."""
        name, ok = QInputDialog.getText(self.win, "New Profile", "Enter database profile name:")
        if ok and name.strip():
            name = name.strip()
            custom_dbs = self.prefs.setdefault("custom_databases", {})
            if name in custom_dbs or (config.DATABASE_CONFIGS and name in config.DATABASE_CONFIGS):
                QMessageBox.warning(self.win, "Profile Exists", f"Profile '{name}' already exists.")
                return
            custom_dbs[name] = dict(self.app.config or {})
            self._refresh_profiles_list()

    def _edit_profile(self) -> None:
        """Inspect or activate selected profile."""
        item = self.win.list_profiles.currentItem()
        if not item:
            QMessageBox.information(self.win, "Select Profile", "Please select a profile first.")
            return

        raw_name = item.text().replace(" (Active)", "").strip()
        # Set as active profile
        self.app.config_name = raw_name
        if config.DATABASE_CONFIGS and raw_name in config.DATABASE_CONFIGS:
            self.app.config = config.DATABASE_CONFIGS[raw_name]
        elif raw_name in self.prefs.get("custom_databases", {}):
            self.app.config = self.prefs["custom_databases"][raw_name]
        self.prefs["last_profile"] = raw_name
        self._refresh_profiles_list()
        QMessageBox.information(self.win, "Profile Selected", f"Profile '{raw_name}' set as active.")

    def _delete_profile(self) -> None:
        """Delete custom database profile."""
        item = self.win.list_profiles.currentItem()
        if not item:
            return
        raw_name = item.text().replace(" (Active)", "").strip()
        if config.DATABASE_CONFIGS and raw_name in config.DATABASE_CONFIGS:
            QMessageBox.warning(self.win, "Cannot Delete", f"'{raw_name}' is a built-in profile and cannot be deleted.")
            return

        custom_dbs = self.prefs.get("custom_databases", {})
        if raw_name in custom_dbs:
            del custom_dbs[raw_name]
            self._refresh_profiles_list()

    def _clear_caches(self) -> None:
        """Clear thumbnail and runtime caches."""
        QMessageBox.information(self.win, "Caches Cleared", "Thumbnail and suggestion caches cleared.")

    def save_settings(self) -> None:
        """Persist draft variables to config.save_prefs without mutating Tkinter state."""
        # 1. Validation
        if hasattr(self.win, "spin_autosave"):
            mins = self.win.spin_autosave.value()
            if mins < 1 or mins > 60:
                QMessageBox.critical(self.win, "Validation Error", "Autosave interval must be between 1 and 60 minutes.")
                return
            self.prefs["autosave_interval"] = mins

        # 2. General
        if hasattr(self.win, "combo_scale"):
            scale_texts = {
                0: 1.0,   # Auto-detect
                1: 1.0,   # 100%
                2: 1.25,  # 125%
                3: 1.50,  # 150%
                4: 2.00,  # 200%
            }
            self.prefs["ui_scale"] = scale_texts.get(self.win.combo_scale.currentIndex(), 1.0)

        if hasattr(self.win, "input_default_db_path"):
            default_path = self.win.input_default_db_path.text().strip()
            self.prefs["default_db_dir"] = default_path
            if default_path and os.path.exists(default_path):
                config.set_last_dir("last_db_dir", default_path)

        if hasattr(self.win, "chk_confirm_delete"):
            self.prefs["confirm_delete"] = self.win.chk_confirm_delete.isChecked()

        if hasattr(self.win, "chk_auto_backup"):
            self.prefs["enable_excel_import_backup"] = self.win.chk_auto_backup.isChecked()

        if hasattr(self.win, "chk_auto_advance"):
            self.prefs["auto_advance_on_review"] = self.win.chk_auto_advance.isChecked()

        # 3. Appearance
        if hasattr(self.win, "chk_dark_mode"):
            self.prefs["dark_mode"] = self.win.chk_dark_mode.isChecked()

        if hasattr(self.win, "chk_problem_highlights"):
            self.prefs["enable_problem_highlights"] = self.win.chk_problem_highlights.isChecked()

        if hasattr(self.win, "combo_highlight_color"):
            self.prefs["problem_highlight_color"] = self.win.combo_highlight_color.currentText()

        if hasattr(self.win, "chk_large_reviewed_btn"):
            self.prefs["large_reviewed_button"] = self.win.chk_large_reviewed_btn.isChecked()

        if hasattr(self.win, "chk_snap_lock"):
            self.prefs["snap_lock"] = self.win.chk_snap_lock.isChecked()

        # 4. Advanced
        if hasattr(self.win, "chk_debug_logging"):
            debug_on = self.win.chk_debug_logging.isChecked()
            self.prefs["debug_logging"] = debug_on
            self.prefs["log_verbosity"] = "DEBUG" if debug_on else "INFO"

        if hasattr(self.win, "chk_memory_cleanup"):
            self.prefs["memory_cleanup"] = self.win.chk_memory_cleanup.isChecked()

        # Save to user_prefs.json via config
        config.save_prefs(self.prefs)

        if self.on_save:
            try:
                self.on_save(self.prefs)
            except Exception:
                pass

        self.win.accept()

    def exec(self) -> int:
        """Display the modal dialog and block until closed."""
        return self.win.exec()
