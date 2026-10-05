"""PySide6 controller for the Startup / Project Setup Dialog (arbor.ui).

Handles database selection, configuration profile auto-detection, image source
mode switching, recent projects history, and launch validation.
"""
from datetime import datetime
import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QListWidgetItem,
    QMessageBox,
)

import config
from ui_qt.loader import load_ui


class QtStartupDialog:
    """Controller wrapping ``qt designer/arbor.ui``."""

    ACTIVE_SEG_STYLE = (
        "background-color: #000000; color: #ffffff; border: none; "
        "font-family: 'Courier New', 'JetBrains Mono', monospace; font-size: 12px; "
        "font-weight: bold; padding: 7px 10px;"
    )
    INACTIVE_SEG_STYLE = (
        "background-color: #ffffff; color: #444748; border: none; "
        "font-family: 'Courier New', 'JetBrains Mono', monospace; font-size: 12px; "
        "font-weight: bold; padding: 7px 10px;"
    )

    def __init__(self, parent=None, app_state=None):
        self.parent = parent
        self.app = app_state
        self.completed = False

        # Values read by main runner
        self.selected_excel_path: Optional[str] = None
        self.image_mode_val: str = "folder"
        self.image_folder_val: str = ""
        self.books_path_val: Optional[str] = None

        # Load pure declarative Qt Designer .ui file
        self.win: QDialog = load_ui("arbor.ui", parent)

        # Ignore mobile companion for now (hidden per project directive)
        if hasattr(self.win, "btn_mobile"):
            self.win.btn_mobile.hide()

        self._init_profiles()
        self._init_recent_projects()
        self._init_saved_paths()
        self._connect_signals()

        # Set default image mode: local directory
        self.set_image_mode("folder")
        self._refresh_launch_state()

    # ------------------------------------------------------------------
    # Initialization Helpers
    # ------------------------------------------------------------------

    def _init_profiles(self) -> None:
        """Populate profile combo with available database configs."""
        self.win.combo_profile.clear()
        configs = list(config.DATABASE_CONFIGS.keys())
        if configs:
            self.win.combo_profile.addItems(configs)

    def _init_recent_projects(self) -> None:
        """Populate recent projects list widget."""
        self.win.list_recent_projects.clear()
        recent = config.get_recent_files()
        if not recent:
            item = QListWidgetItem("No recent projects")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.win.list_recent_projects.addItem(item)
            return

        for entry in recent[:8]:
            path = entry.get("path", "")
            if path:
                item = QListWidgetItem(path)
                item.setToolTip(path)
                self.win.list_recent_projects.addItem(item)

    def _init_saved_paths(self) -> None:
        """Restore last used database and image directory paths."""
        last_db = config.get_last_dir("last_db_dir")
        if last_db and os.path.isfile(last_db):
            self.win.input_db_path.setText(last_db)
            self._auto_detect_profile(last_db)

        last_img = config.get_last_dir("last_image_dir")
        if last_img and os.path.isdir(last_img):
            self.win.input_image_path.setText(last_img)
            self.image_folder_val = last_img

    def _connect_signals(self) -> None:
        """Wire UI events to controller slots."""
        self.win.btn_browse_db.clicked.connect(self.browse_database)
        self.win.btn_browse_images.clicked.connect(self.browse_image_folder)
        self.win.btn_browse_books.clicked.connect(self.browse_books_file)

        self.win.btn_mode_online.clicked.connect(lambda: self.set_image_mode("online"))
        self.win.btn_mode_local.clicked.connect(lambda: self.set_image_mode("folder"))
        self.win.btn_mode_offline.clicked.connect(lambda: self.set_image_mode("offline"))

        self.win.list_recent_projects.itemClicked.connect(self._on_recent_clicked)
        self.win.btn_help.clicked.connect(self.show_help)
        self.win.btn_launch.clicked.connect(self.finish)

    # ------------------------------------------------------------------
    # Actions & Slots
    # ------------------------------------------------------------------

    def set_image_mode(self, mode: str) -> None:
        """Toggle segmented button styling and folder picker visibility."""
        self.image_mode_val = mode
        self.win.btn_mode_online.setStyleSheet(
            self.ACTIVE_SEG_STYLE if mode == "online" else self.INACTIVE_SEG_STYLE
        )
        self.win.btn_mode_local.setStyleSheet(
            self.ACTIVE_SEG_STYLE if mode == "folder" else self.INACTIVE_SEG_STYLE
        )
        self.win.btn_mode_offline.setStyleSheet(
            self.ACTIVE_SEG_STYLE if mode == "offline" else self.INACTIVE_SEG_STYLE
        )
        self.win.folder_picker_container.setVisible(mode == "folder")

    def _auto_detect_profile(self, path: str) -> None:
        """Auto-select matching database profile based on file basename."""
        if not path:
            return
        basename = os.path.basename(path).lower()
        for name in config.DATABASE_CONFIGS.keys():
            if name.lower() in basename or basename in name.lower():
                self.win.combo_profile.setCurrentText(name)
                return

    def browse_database(self) -> None:
        """Open file dialog to pick database file (*.xlsx, *.db, *.sqlite)."""
        last_dir = config.get_last_dir("last_db_dir") or ""
        path, _ = QFileDialog.getOpenFileName(
            self.win,
            "Select Database File",
            last_dir,
            "Database files (*.xlsx *.db *.sqlite);;All files (*.*)",
        )
        if not path:
            return

        config.set_last_dir("last_db_dir", path)
        self.win.input_db_path.setText(path)
        self._auto_detect_profile(path)
        self._check_autosave(path)
        self._refresh_launch_state()

    def _check_autosave(self, path: str) -> None:
        """Prompt to recover if an autosave file is found."""
        base, _ = os.path.splitext(path)
        autosave_path = base + ".autosave.json"
        if not os.path.exists(autosave_path):
            autosave_path = base + ".autosave.xlsx"

        if os.path.exists(autosave_path):
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(autosave_path))
                time_str = mtime.strftime("%d.%m.%Y %H:%M")
                reply = QMessageBox.question(
                    self.win,
                    "Autosave found",
                    f"An autosave was found from {time_str}.\n\n"
                    "Do you want to recover from autosave?\n\n"
                    "(Click No to open the original file)",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.win.input_db_path.setText(autosave_path)
            except Exception:
                pass

    def browse_image_folder(self) -> None:
        """Open folder dialog to select image directory."""
        last_dir = config.get_last_dir("last_image_dir") or ""
        folder = QFileDialog.getExistingDirectory(
            self.win, "Select Image Directory", last_dir
        )
        if folder:
            self.win.input_image_path.setText(folder)
            self.image_folder_val = folder
            config.set_last_dir("last_image_dir", folder)

    def browse_books_file(self) -> None:
        """Open file dialog for optional historical data file."""
        path, _ = QFileDialog.getOpenFileName(
            self.win,
            "Select Historical Books File",
            "",
            "Excel files (*.xlsx *.xls);;All files (*.*)",
        )
        if path:
            self.win.input_books_path.setText(path)

    def _on_recent_clicked(self, item: QListWidgetItem) -> None:
        """Load selected path from recent projects list."""
        path = item.text().strip()
        if not path or path == "No recent projects":
            return
        if not os.path.exists(path):
            QMessageBox.warning(
                self.win, "File Not Found", f"Could not find file:\n{path}"
            )
            return

        self.win.input_db_path.setText(path)
        self._auto_detect_profile(path)
        self._refresh_launch_state()

    def _refresh_launch_state(self) -> None:
        """Enable LAUNCH button and update status text when a valid DB is chosen."""
        path = self.win.input_db_path.text().strip()
        valid = bool(path and os.path.exists(path))
        self.win.btn_launch.setEnabled(valid)

        if valid:
            self.win.lbl_status.setText("Ready to launch!")
            self.win.lbl_status.setStyleSheet("color: #3a7d44; font-weight: bold;")
        else:
            self.win.lbl_status.setText("Please select a database file.")
            self.win.lbl_status.setStyleSheet("color: #c93a40;")

    def show_help(self) -> None:
        """Display startup setup guide."""
        QMessageBox.information(
            self.win,
            "Setup Help",
            "SETUP STEPS\n\n"
            "1. REQUIRED: Select a database file (.xlsx or .db).\n"
            "2. Profile: Select or verify the matching schema profile.\n"
            "3. Image Source: Choose Online, Local directory, or Offline.\n"
            "4. Historical Books (Optional): Select a historical reference file.\n"
            "5. Click LAUNCH SYSTEM to start.",
        )

    def finish(self) -> None:
        """Validate paths, apply to AppState/config, and accept dialog."""
        path = self.win.input_db_path.text().strip()
        if not path or not os.path.exists(path):
            QMessageBox.critical(
                self.win, "Error", "Please select a valid database file first."
            )
            return

        profile_name = self.win.combo_profile.currentText().strip()
        matched_config = config.DATABASE_CONFIGS.get(profile_name)
        if not matched_config and config.DATABASE_CONFIGS:
            profile_name = next(iter(config.DATABASE_CONFIGS))
            matched_config = config.DATABASE_CONFIGS[profile_name]

        if not matched_config:
            QMessageBox.critical(
                self.win, "Error", "No valid database configuration profile found."
            )
            return

        # Populate AppState if provided
        if self.app:
            self.app.config = matched_config
            self.app.config_name = profile_name

        self.selected_excel_path = path

        # Image mode
        if self.image_mode_val == "folder":
            img_path = self.win.input_image_path.text().strip()
            if not img_path:
                QMessageBox.critical(
                    self.win,
                    "Error",
                    "Please select a local image directory or switch to Online/Offline mode.",
                )
                return
            config.set_last_dir("last_image_dir", img_path)
            self.image_folder_val = img_path

        # Books path
        books_val = self.win.input_books_path.text().strip()
        self.books_path_val = books_val if books_val else None

        # Add to recent files
        config.add_recent_file(path)

        self.completed = True
        self.win.accept()

    def exec(self) -> int:
        """Show dialog modally."""
        return self.win.exec()
