"""Helpers for loading Qt Designer .ui files from ``qt designer/``."""
import os

from PySide6.QtCore import QFile, QIODevice
from PySide6.QtUiTools import QUiLoader

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESIGNER_DIR = os.path.join(_ROOT, "qt designer")


def ui_path(name: str) -> str:
    """Absolute path of a .ui file inside the designer directory."""
    primary = os.path.join(DESIGNER_DIR, name)
    if os.path.exists(primary):
        return primary
    for root, _, files in os.walk(DESIGNER_DIR):
        if name in files:
            return os.path.join(root, name)
    return primary


def load_ui(name: str, parent=None):
    """Load ``qt designer/<name>`` and return the top-level widget (or raise)."""
    path = ui_path(name)
    f = QFile(path)
    if not f.open(QIODevice.ReadOnly):
        raise FileNotFoundError(path)
    try:
        widget = QUiLoader().load(f, parent)
    finally:
        f.close()
    if widget is None:
        raise RuntimeError(f"Failed to load UI file: {path}")
    return widget
