import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QPushButton, QCheckBox, QComboBox, QLabel
from ui_qt.loader import load_ui

app = QApplication.instance() or QApplication([])
win = load_ui("main_window_existing.ui")

print("--- PushButtons ---")
for btn in win.findChildren(QPushButton):
    print(f"  {btn.objectName()}: text='{btn.text()}'")

print("\n--- CheckBoxes ---")
for chk in win.findChildren(QCheckBox):
    print(f"  {chk.objectName()}: text='{chk.text()}'")

print("\n--- ComboBoxes ---")
for cb in win.findChildren(QComboBox):
    print(f"  {cb.objectName()}: count={cb.count()}")

print("\n--- Labels of interest ---")
for lbl in win.findChildren(QLabel):
    name = lbl.objectName()
    if any(k in name.lower() for k in ["save", "status", "review", "time", "id", "badge"]):
        print(f"  {name}: text='{lbl.text()}'")
