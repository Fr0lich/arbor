"""PySide6 implementation of the Loading Splash Dialog."""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ui_qt.qss_tokens import BORDER, CARD, FONT_MONO, FONT_UI, GREEN, SUBTEXT, SURFACE, TEXT


class QtLoadingDialog(QDialog):
    """Clean loading splash card displaying database load status and progress."""

    def __init__(self, parent: Optional[QWidget] = None, title: str = "Initializing Application"):
        super().__init__(parent)
        self.setWindowTitle("arbor — Loading Database")
        self.setFixedSize(460, 200)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {SURFACE};
                font-family: {FONT_UI};
            }}
            QFrame#card {{
                background-color: {CARD};
                border: 1px solid {BORDER};
                border-radius: 2px;
            }}
            QProgressBar {{
                border: 1px solid {BORDER};
                border-radius: 0px;
                background-color: #e9ece5;
                text-align: center;
                height: 16px;
                font-family: {FONT_MONO};
                font-size: 11px;
            }}
            QProgressBar::chunk {{
                background-color: {GREEN};
            }}
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)

        card = QFrame(self)
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 24, 20, 24)
        card_layout.setSpacing(14)

        # Header Title
        self.lbl_title = QLabel(title, card)
        self.lbl_title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT};")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.lbl_title)

        # Status Message
        self.lbl_status = QLabel("Loading Excel database...", card)
        self.lbl_status.setStyleSheet(f"font-family: {FONT_MONO}; font-size: 12px; color: {SUBTEXT};")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.lbl_status)

        # Progress Bar
        self.progress_bar = QProgressBar(card)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        card_layout.addWidget(self.progress_bar)

        root_layout.addWidget(card)

    def set_status(self, text: str) -> None:
        """Update current status description."""
        self.lbl_status.setText(text)

    def set_progress(self, percent: int) -> None:
        """Update progress bar percentage (0-100)."""
        self.progress_bar.setValue(max(0, min(100, percent)))

    def set_indeterminate(self, active: bool = True) -> None:
        """Switch between indeterminate (busy marquee) and determinate progress."""
        if active:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
