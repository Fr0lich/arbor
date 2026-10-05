"""PySide6 application runner. ``main.py`` continues to launch Tkinter by default.

Usage:
    python main_qt.py          # Launches Startup Dialog first, then Main Workspace
    python main_qt.py --direct # Bypasses Startup Dialog directly into Main Workspace
"""
import sys

from PySide6.QtWidgets import QApplication

from models import AppState
from ui_qt.main_window import QtMainWindow
from ui_qt.startup_dialog import QtStartupDialog


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    state = AppState()

    # Unless explicitly bypassed with --direct, show Startup Dialog
    if "--direct" not in sys.argv:
        startup = QtStartupDialog(app_state=state)
        startup.exec()
        if not startup.completed:
            return 0

    window = QtMainWindow(state)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
