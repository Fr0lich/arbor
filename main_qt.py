"""Qt test runner. ``main.py`` still launches Tkinter by default."""
import sys

from PySide6.QtWidgets import QApplication

from models import AppState
from ui_qt.main_window import QtMainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = QtMainWindow(AppState())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
