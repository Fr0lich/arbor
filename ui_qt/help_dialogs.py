"""PySide6 implementation of Arbor Help, Shortcuts, and Documentation dialogs."""
import os
import sys
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ui_qt.qss_tokens import BORDER, CARD, FONT_MONO, FONT_UI, HAIRLINE, SUBTEXT, SURFACE, TEXT


class QtUserGuideDialog(QDialog):
    """Full-featured Arbor System User Guide modal rendering markdown documentation."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Arbor System User Guide")
        self.resize(780, 800)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {SURFACE};
                color: {TEXT};
                font-family: {FONT_UI};
            }}
            QTextBrowser {{
                background-color: {CARD};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 2px;
                padding: 12px;
                font-size: 13px;
                line-height: 1.4;
            }}
            QPushButton {{
                background-color: {SURFACE};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 0px;
                padding: 6px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #e9ece5;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header title
        lbl_title = QLabel("ARBOR USER GUIDE")
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {TEXT};")
        layout.addWidget(lbl_title)

        # Text browser
        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(True)
        layout.addWidget(self.browser)

        # Footer
        footer_layout = QHBoxLayout()
        lbl_hint = QLabel("Press Escape to close.")
        lbl_hint.setStyleSheet(f"color: {SUBTEXT}; font-style: italic; font-size: 11px;")
        footer_layout.addWidget(lbl_hint)

        footer_layout.addStretch()

        btn_close = QPushButton("Close", self)
        btn_close.clicked.connect(self.accept)
        footer_layout.addWidget(btn_close)

        layout.addLayout(footer_layout)

        # Shortcut: Esc closes
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.accept)

        self._load_guide()

    def _load_guide(self) -> None:
        """Find and render USER_GUIDE.md."""
        guide_path = None
        try:
            from utils import get_resource_path
            guide_path = get_resource_path("USER_GUIDE.md")
        except Exception:
            pass

        if not guide_path or not os.path.exists(guide_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            guide_path = os.path.join(base_dir, "USER_GUIDE.md")

        if os.path.exists(guide_path):
            try:
                with open(guide_path, "r", encoding="utf-8") as f:
                    md_text = f.read()
                self.browser.setMarkdown(md_text)
            except Exception as e:
                self.browser.setPlainText(f"Failed to read USER_GUIDE.md: {e}")
        else:
            self.browser.setPlainText("USER_GUIDE.md could not be found.")


class QtKeyboardShortcutsDialog(QDialog):
    """Searchable Keyboard Shortcuts HUD dialog matching the Tkinter design."""

    SHORTCUTS = [
        ("Ctrl+S", "Save active session to Excel/SQLite"),
        ("Ctrl+Q", "Toggle Focus Mode (compact review pane)"),
        ("Ctrl+G", "Open Filter objects dialog"),
        ("Ctrl+P", "Quick Peek preview of current object"),
        ("Ctrl+H", "Open Historical suggestions / book matcher"),
        ("Ctrl+N", "Create new blank Object"),
        ("Ctrl+Shift+N", "Quick create new sequential Object"),
        ("Ctrl+D", "Duplicate current object"),
        ("Ctrl+Shift+P / F3", "Open editable Problem Flags resolver"),
        ("Ctrl+Shift+L / F4", "Open editable Location window"),
        ("Right / Left Arrow", "Navigate to Next / Previous object"),
        ("Down / Up Arrow", "Navigate object list rows"),
        ("F11", "Toggle fullscreen"),
        ("Escape", "Close active popup / dialog"),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts HUD")
        self.resize(700, 560)
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
            QTableWidget {{
                background-color: {CARD};
                color: {TEXT};
                border: 1px solid {BORDER};
                gridline-color: {HAIRLINE};
                font-size: 12px;
            }}
            QTableWidget::item {{
                padding: 6px;
            }}
            QHeaderView::section {{
                background-color: #f2f5f1;
                color: {TEXT};
                border: none;
                border-bottom: 1px solid {BORDER};
                font-weight: bold;
                padding: 6px;
            }}
            QPushButton {{
                background-color: {SURFACE};
                color: {TEXT};
                border: 1px solid {BORDER};
                padding: 6px 16px;
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
        lbl_title = QLabel("KEYBOARD SHORTCUTS")
        lbl_title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT};")
        hdr_layout.addWidget(lbl_title)

        hdr_layout.addStretch()

        self.input_search = QLineEdit(self)
        self.input_search.setPlaceholderText("Search shortcuts (e.g. Save, Ctrl)...")
        self.input_search.setFixedWidth(240)
        self.input_search.textChanged.connect(self._filter_table)
        hdr_layout.addWidget(self.input_search)

        layout.addLayout(hdr_layout)

        # Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Key Combination", "Action Description"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        # Footer
        footer_layout = QHBoxLayout()
        lbl_hint = QLabel("Press Escape to close.")
        lbl_hint.setStyleSheet(f"color: {SUBTEXT}; font-style: italic; font-size: 11px;")
        footer_layout.addWidget(lbl_hint)
        footer_layout.addStretch()

        btn_close = QPushButton("Close", self)
        btn_close.clicked.connect(self.accept)
        footer_layout.addWidget(btn_close)
        layout.addLayout(footer_layout)

        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.accept)

        self._populate_table()

    def _populate_table(self) -> None:
        """Fill table with all shortcuts."""
        self.table.setRowCount(len(self.SHORTCUTS))
        mono_font = QFont("Courier New", 10, QFont.Weight.Bold)

        for row, (key, desc) in enumerate(self.SHORTCUTS):
            item_key = QTableWidgetItem(key)
            item_key.setFont(mono_font)
            item_key.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

            item_desc = QTableWidgetItem(desc)
            item_desc.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

            self.table.setItem(row, 0, item_key)
            self.table.setItem(row, 1, item_desc)

    def _filter_table(self, query: str) -> None:
        """Filter table rows matching search string."""
        q = query.strip().lower()
        for row in range(self.table.rowCount()):
            k_item = self.table.item(row, 0)
            d_item = self.table.item(row, 1)
            k_text = k_item.text().lower() if k_item else ""
            d_text = d_item.text().lower() if d_item else ""
            match = (q in k_text) or (q in d_text)
            self.table.setRowHidden(row, not match)


def show_about(parent: Optional[QWidget] = None) -> None:
    """Display the About dialog."""
    QMessageBox.information(
        parent,
        "About arbor",
        "Arbor Botanical Database Management System\nVersion 1.2\n(PySide6 Modernized)",
    )


def show_quick_help(parent: Optional[QWidget] = None) -> None:
    """Display the quick start shortcuts cheat sheet message box."""
    message = (
        "ARBOR KEYBOARD SHORTCUTS CHEAT SHEET\n\n"
        "Ctrl + S : Save session\n"
        "Ctrl + Q : Toggle Focus Mode\n"
        "Ctrl + G : Open Filter Menu\n"
        "Ctrl + H : Open Historical suggestions\n"
        "Ctrl + N : Create new blank Object\n"
        "Ctrl + Shift + N : Quick create new Object\n"
        "Ctrl + D : Duplicate current object\n"
        "Ctrl + Shift + P / F3 : Open editable Problem Flags window\n"
        "Ctrl + Shift + L / F4 : Open editable Location window\n"
        "Right Arrow / Left Arrow : Navigate Next / Prev object\n"
        "Down Arrow / Up Arrow : Navigate list rows"
    )
    QMessageBox.information(parent, "Quick Start", message)
