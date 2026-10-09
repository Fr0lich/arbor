"""PySide6 application runner and workspace coordinator.

``main.py`` continues to launch Tkinter by default for production stability.

Usage:
    python main_qt.py          # Launches Startup Dialog first, then Main Workspace
    python main_qt.py --direct # Bypasses Startup Dialog directly into Main Workspace
"""
from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtWidgets import QApplication

from models import AppState
from ui_qt.main_window import QtMainWindow
from ui_qt.startup_dialog import QtStartupDialog


def open_excel_action(window: QtMainWindow, path: Optional[str] = None) -> None:
    """Domain action: Load an Excel or SQLite database into the main workspace."""
    window.open_excel(path)


def save_session_action(window: QtMainWindow, path: Optional[str] = None) -> None:
    """Domain action: Persist active in-memory state to disk."""
    window.save_session(path)


def load_books_action(window: QtMainWindow, path: Optional[str] = None) -> None:
    """Domain action: Load historical reference books."""
    window.load_books(path)


def run_gbif_check_action(window: QtMainWindow) -> None:
    """Domain action: Execute GBIF taxonomy validation for active specimen."""
    window.run_gbif_check()


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    state = AppState()

    selected_db: Optional[str] = None
    selected_books: Optional[str] = None

    # Unless explicitly bypassed with --direct, show Startup Dialog
    if "--direct" not in sys.argv:
        startup = QtStartupDialog(app_state=state)
        startup.exec()
        if not startup.completed:
            return 0
        selected_db = startup.selected_excel_path
        selected_books = startup.books_path_val

    window = QtMainWindow(state)

    # Load database configured in Startup Dialog
    if selected_db:
        open_excel_action(window, selected_db)
        if selected_books:
            load_books_action(window, selected_books)

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
