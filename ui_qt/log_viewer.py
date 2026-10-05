"""PySide6 implementation of the Error and Session Log Viewer."""
import os
import subprocess
import sys
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui_qt.qss_tokens import BORDER, CARD, FONT_MONO, FONT_UI, RED, SUBTEXT, SURFACE, TEXT


class QtErrorLogDialog(QDialog):
    """Scrollable, searchable log viewer window matching Tkinter's show_error_log_window."""

    def __init__(self, log_path: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)

        if log_path is None:
            try:
                from utils import get_session_log_path
                log_path = get_session_log_path()
            except Exception:
                log_path = ""

        self.log_path = log_path
        filename = os.path.basename(log_path) if log_path else "Current Session"
        self.setWindowTitle(f"Error Log — {filename}")
        self.resize(750, 540)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {SURFACE};
                color: {TEXT};
                font-family: {FONT_UI};
            }}
            QLineEdit {{
                background-color: {CARD};
                color: {TEXT};
                border: 1px solid {BORDER};
                padding: 6px 10px;
                font-family: {FONT_MONO};
                font-size: 12px;
            }}
            QPlainTextEdit {{
                background-color: #1a1a2e;
                color: #e0e0e0;
                border: 1px solid {BORDER};
                border-radius: 2px;
                font-family: {FONT_MONO};
                font-size: 12px;
                line-height: 1.3;
            }}
            QPushButton {{
                background-color: {SURFACE};
                color: {TEXT};
                border: 1px solid {BORDER};
                padding: 6px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #e9ece5;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header with Search
        hdr_layout = QHBoxLayout()
        lbl_title = QLabel("SESSION ERROR LOG")
        lbl_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT};")
        hdr_layout.addWidget(lbl_title)

        hdr_layout.addStretch()

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Filter lines (e.g. ERROR, Exception)...")
        self.search_input.setFixedWidth(260)
        self.search_input.textChanged.connect(self._filter_log)
        hdr_layout.addWidget(self.search_input)

        layout.addLayout(hdr_layout)

        # Log content text area
        self.text_area = QPlainTextEdit(self)
        self.text_area.setReadOnly(True)
        layout.addWidget(self.text_area)

        # Footer Actions
        footer_layout = QHBoxLayout()

        self.btn_copy = QPushButton("Copy to Clipboard", self)
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        footer_layout.addWidget(self.btn_copy)

        self.btn_explorer = QPushButton("Open in Explorer", self)
        self.btn_explorer.clicked.connect(self._open_in_explorer)
        footer_layout.addWidget(self.btn_explorer)

        footer_layout.addStretch()

        self.btn_close = QPushButton("Close", self)
        self.btn_close.clicked.connect(self.accept)
        footer_layout.addWidget(self.btn_close)

        layout.addLayout(footer_layout)

        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.accept)

        self._raw_lines: list[str] = []
        self._load_log()

    def _load_log(self) -> None:
        """Read log file and display lines."""
        if not self.log_path or not os.path.exists(self.log_path):
            self.text_area.setPlainText("(No errors have been logged yet in this session.)")
            return

        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self._raw_lines = content.splitlines()
            self.text_area.setPlainText(content)
        except Exception as exc:
            self.text_area.setPlainText(f"Could not read log file:\n{exc}")

    def _filter_log(self, query: str) -> None:
        """Filter log lines based on search text."""
        q = query.strip().lower()
        if not q:
            self.text_area.setPlainText("\n".join(self._raw_lines))
            return
        filtered = [line for line in self._raw_lines if q in line.lower()]
        self.text_area.setPlainText("\n".join(filtered))

    def _copy_to_clipboard(self) -> None:
        """Copy full log content to system clipboard."""
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.text_area.toPlainText())
            QMessageBox.information(self, "Copied", "Log contents copied to clipboard.")

    def _open_in_explorer(self) -> None:
        """Open containing folder in system file manager."""
        if not self.log_path or not os.path.exists(self.log_path):
            return
        target_dir = os.path.dirname(os.path.abspath(self.log_path))
        if sys.platform == "win32":
            subprocess.run(["explorer", f"/select,{os.path.abspath(self.log_path)}"])
        else:
            subprocess.run(["xdg-open", target_dir])
