"""Validate every .ui file in ``qt designer/`` with QUiLoader.

Usage: python scripts/verify_ui.py [file.ui ...]   (default: all)
"""
import glob
import os
import sys

from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = QApplication.instance() or QApplication(sys.argv)

files = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, "qt designer", "**", "*.ui"), recursive=True))
failed = 0
for path in files:
    if not os.path.isabs(path) and not os.path.exists(path):
        path = os.path.join(ROOT, "qt designer", path)
    widget = QUiLoader().load(path)
    if widget is None:
        print(f"FAILED:   {path}")
        failed += 1
    else:
        print(f"VERIFIED: {widget.objectName()} loaded successfully with class {type(widget)}")
sys.exit(1 if failed else 0)
