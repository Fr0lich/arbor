"""PySide6 implementation of the Ignored Words Configuration Dialog."""
import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.ignored_words_dialog import load_ignored_words, save_ignored_words
from ui_qt.qss_tokens import BORDER, CARD, FONT_MONO, FONT_UI, SUBTEXT, SURFACE, TEXT


class QtIgnoredWordsDialog(QDialog):
    """Dialog for configuring the dictionary of ignored words for discrepancies."""

    def __init__(self, file_path: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle("Configure Ignored Words")
        self.resize(520, 560)
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
            QListWidget {{
                background-color: {CARD};
                color: {TEXT};
                border: 1px solid {BORDER};
                padding: 4px;
                font-family: {FONT_MONO};
                font-size: 12px;
            }}
            QListWidget::item {{
                padding: 4px 8px;
            }}
            QListWidget::item:selected {{
                background-color: #e9ece5;
                color: #000000;
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
            QPushButton#btn_save {{
                background-color: #000000;
                color: #ffffff;
                border: none;
                padding: 6px 18px;
            }}
            QPushButton#btn_save:hover {{
                background-color: #2c302e;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Title
        lbl_title = QLabel("CONFIGURE IGNORED WORDS")
        lbl_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT};")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(
            "Words or phrases in this list will be ignored during validation and discrepancy checks."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"color: {SUBTEXT}; font-size: 12px;")
        layout.addWidget(lbl_desc)

        # Add Word Input Row
        add_layout = QHBoxLayout()
        self.input_word = QLineEdit(self)
        self.input_word.setPlaceholderText("Enter word or phrase to ignore...")
        self.input_word.returnPressed.connect(self._add_word)
        add_layout.addWidget(self.input_word)

        btn_add = QPushButton("Add Word", self)
        btn_add.clicked.connect(self._add_word)
        add_layout.addWidget(btn_add)
        layout.addLayout(add_layout)

        # Word List
        self.list_widget = QListWidget(self)
        layout.addWidget(self.list_widget)

        # Variations Checkbox & Remove Button Row
        mid_layout = QHBoxLayout()
        self.chk_variations = QCheckBox("Ignore case and punctuation variations", self)
        mid_layout.addWidget(self.chk_variations)

        mid_layout.addStretch()

        btn_remove = QPushButton("Remove Selected", self)
        btn_remove.clicked.connect(self._remove_selected)
        mid_layout.addWidget(btn_remove)
        layout.addLayout(mid_layout)

        # Footer Actions
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        footer_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Save & Close", self)
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save_and_close)
        footer_layout.addWidget(btn_save)

        layout.addLayout(footer_layout)

        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.reject)

        self._load_data()

    def _load_data(self) -> None:
        """Load ignored words from disk."""
        words, variations = load_ignored_words(self.file_path)
        self.chk_variations.setChecked(variations)
        self.list_widget.clear()
        for w in words:
            self.list_widget.addItem(w)

    def _add_word(self) -> None:
        """Add entered word to list."""
        text = self.input_word.text().strip()
        if not text:
            return

        # Check duplicates
        existing = [
            self.list_widget.item(i).text().lower()
            for i in range(self.list_widget.count())
        ]
        if text.lower() in existing:
            QMessageBox.information(
                self, "Already Exists", f"'{text}' is already in the ignored words list."
            )
            return

        self.list_widget.addItem(text)
        self.input_word.clear()

    def _remove_selected(self) -> None:
        """Remove highlighted items from list."""
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))

    def _save_and_close(self) -> None:
        """Persist words to disk and close."""
        words = [
            self.list_widget.item(i).text()
            for i in range(self.list_widget.count())
        ]
        variations = self.chk_variations.isChecked()
        save_ignored_words(self.file_path, words, variations)
        self.accept()
