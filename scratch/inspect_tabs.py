import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QLabel, QStatusBar
from ui_qt.loader import load_ui

app = QApplication.instance() or QApplication([])
win = load_ui("main_window_existing.ui")

print("Labels:")
for lbl in win.findChildren(QLabel):
    name = lbl.objectName()
    if any(k in name.lower() for k in ["status", "count", "reviewed", "problem", "badge", "sb", "stat"]):
        print(f"  {name}: '{lbl.text()}'")

print("StatusBars:")
for sb in win.findChildren(QStatusBar):
    print("  StatusBar:", sb.objectName())
