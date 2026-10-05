"""PySide6 implementation of Arbor's Filter Objects Dialog.

Migrated from Tkinter ``ui/filter_dialog.py`` as part of the parallel UI migration.
Reuses ``backend.filter.FilterManager`` and ``models.AppState`` directly.
"""
from __future__ import annotations

import json
import os
from typing import Callable

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QKeySequence, QMouseEvent, QFont, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QRadioButton,
    QGroupBox,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QInputDialog,
    QMessageBox,
)

import config
from backend.filter import FilterManager
from repository import REVIEWED_COLUMN
from ui_qt.loader import load_ui
from ui_qt import qss_tokens


class QtTriStateRow(QFrame):
    """Tri-state filter row widget matching the Arbor UI design system.

    States:
    - "Ignore": No filter condition applied (default)
    - "Has": Record must have this attribute (Green checkmark, #e8f5e9 pill)
    - "Not": Record must NOT have this attribute (Red dash, #ffebee pill)

    Interaction:
    - Left-click: cycles forward (Ignore -> Has -> Not -> Ignore)
    - Right-click: cycles backward (Ignore -> Not -> Has -> Ignore)
    """

    state_changed = Signal(str, str)  # (key, state)
    STATES = ["Ignore", "Has", "Not"]

    def __init__(
        self,
        key: str,
        label_text: str,
        parent: QWidget | None = None,
        color_bar: str | None = None,
        initial_state: str = "Ignore",
    ):
        super().__init__(parent)
        self.key = key
        self.label_text = label_text
        self.state = initial_state if initial_state in self.STATES else "Ignore"
        self.color_bar = color_bar
        self.search_text = f"{key.lower()} {label_text.lower()}"

        self.setObjectName("tristate_row")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(8)

        # 1. State indicator box (20x20)
        self.btn_indicator = QLabel(" ", self)
        self.btn_indicator.setFixedSize(20, 20)
        self.btn_indicator.setAlignment(Qt.AlignCenter)
        indicator_font = QFont("JetBrains Mono", 10, QFont.Bold)
        self.btn_indicator.setFont(indicator_font)
        layout.addWidget(self.btn_indicator)

        # 2. Optional category color bar
        if self.color_bar:
            self.bar = QFrame(self)
            self.bar.setFixedSize(4, 16)
            self.bar.setStyleSheet(f"background-color: {self.color_bar}; border-radius: 1px;")
            layout.addWidget(self.bar)

        # 3. Label text
        self.lbl_text = QLabel(self.label_text, self)
        label_font = QFont("Segoe UI", 10)
        self.lbl_text.setFont(label_font)
        self.lbl_text.setStyleSheet(f"color: {qss_tokens.TEXT}; background: transparent;")
        layout.addWidget(self.lbl_text)

        layout.addStretch(1)

        # 4. Status Badge Pill
        self.lbl_badge = QLabel("IGNORE", self)
        self.lbl_badge.setFixedWidth(78)
        self.lbl_badge.setFixedHeight(20)
        self.lbl_badge.setAlignment(Qt.AlignCenter)
        badge_font = QFont("JetBrains Mono", 9, QFont.Bold)
        self.lbl_badge.setFont(badge_font)
        layout.addWidget(self.lbl_badge)

        self._update_visual()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.cycle(1)
            event.accept()
        elif event.button() == Qt.RightButton:
            self.cycle(-1)
            event.accept()
        else:
            super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        self.setStyleSheet("QFrame#tristate_row { background-color: #f2f5f1; border-radius: 2px; }")
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setStyleSheet("QFrame#tristate_row { background-color: transparent; }")
        super().leaveEvent(event)

    def cycle(self, delta: int = 1) -> None:
        curr = self.state if self.state in self.STATES else "Ignore"
        idx = self.STATES.index(curr)
        next_state = self.STATES[(idx + delta) % len(self.STATES)]
        self.set_state(next_state)

    def set_state(self, new_state: str, emit_signal: bool = True) -> None:
        s = str(new_state).strip().capitalize()
        if s in ("Has", "True", "1"):
            s = "Has"
        elif s in ("Not", "False", "-1"):
            s = "Not"
        else:
            s = "Ignore"

        self.state = s
        self._update_visual()
        if emit_signal:
            self.state_changed.emit(self.key, self.state)

    def _update_visual(self) -> None:
        if self.state == "Has":
            self.btn_indicator.setText("✓")
            self.btn_indicator.setStyleSheet(
                f"background-color: #e8f5e9; color: {qss_tokens.GREEN}; "
                f"border: 1px solid {qss_tokens.GREEN}; border-radius: 2px; font-weight: bold;"
            )
            self.lbl_badge.setText("HAS (✓)")
            self.lbl_badge.setStyleSheet(
                "background-color: #e8f5e9; color: #2e7d32; "
                "border: 1px solid #3a7d44; border-radius: 2px; font-weight: bold;"
            )
        elif self.state == "Not":
            self.btn_indicator.setText("−")
            self.btn_indicator.setStyleSheet(
                f"background-color: #ffebee; color: {qss_tokens.RED}; "
                f"border: 1px solid {qss_tokens.RED}; border-radius: 2px; font-weight: bold;"
            )
            self.lbl_badge.setText("NOT (−)")
            self.lbl_badge.setStyleSheet(
                f"background-color: #ffebee; color: {qss_tokens.RED}; "
                f"border: 1px solid {qss_tokens.RED}; border-radius: 2px; font-weight: bold;"
            )
        else:
            self.btn_indicator.setText(" ")
            self.btn_indicator.setStyleSheet(
                f"background-color: #ffffff; color: {qss_tokens.BORDER}; "
                f"border: 1px solid {qss_tokens.BORDER}; border-radius: 2px;"
            )
            self.lbl_badge.setText("IGNORE")
            self.lbl_badge.setStyleSheet(
                f"background-color: #f2f5f1; color: {qss_tokens.SUBTEXT}; "
                f"border: 1px solid {qss_tokens.HAIRLINE}; border-radius: 2px;"
            )


class QtLoadPresetDialog(QDialog):
    """Modal dialog to select and load a saved filter preset."""

    def __init__(self, presets: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.presets = presets
        self.selected_preset_name: str | None = None

        self.setWindowTitle("Load Preset")
        self.resize(380, 440)
        self.setStyleSheet(
            f"QDialog {{ background-color: {qss_tokens.SURFACE}; }}"
            f"QLabel {{ color: {qss_tokens.TEXT}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        lbl_title = QLabel("LOAD FILTER PRESET", self)
        lbl_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(f"Select a preset ({len(presets)} available) to apply:", self)
        lbl_desc.setStyleSheet(f"color: {qss_tokens.SUBTEXT}; font-size: 12px;")
        layout.addWidget(lbl_desc)

        sep = QFrame(self)
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {qss_tokens.HAIRLINE};")
        layout.addWidget(sep)

        self.list_widget = QListWidget(self)
        self.list_widget.setStyleSheet(
            f"QListWidget {{ background-color: {qss_tokens.CARD}; border: 1px solid {qss_tokens.BORDER}; "
            f"border-radius: 2px; font-family: 'Segoe UI', sans-serif; font-size: 13px; padding: 4px; }}"
            f"QListWidget::item {{ padding: 6px; }}"
            f"QListWidget::item:selected {{ background-color: {qss_tokens.GREEN}; color: #ffffff; }}"
        )
        for name in sorted(presets.keys()):
            self.list_widget.addItem(name)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        self.list_widget.itemDoubleClicked.connect(self._on_load_clicked)
        layout.addWidget(self.list_widget)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)
        btn_box.addStretch(1)

        btn_cancel = QPushButton("CANCEL", self)
        btn_cancel.setStyleSheet(
            f"QPushButton {{ background-color: {qss_tokens.SURFACE}; color: {qss_tokens.TEXT}; "
            f"border: 1px solid {qss_tokens.BORDER}; padding: 6px 14px; font-family: 'Segoe UI'; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {qss_tokens.CONTAINER}; }}"
        )
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_load = QPushButton("LOAD PRESET", self)
        btn_load.setStyleSheet(
            f"QPushButton {{ background-color: {qss_tokens.GREEN}; color: #ffffff; "
            f"border: 1px solid {qss_tokens.GREEN}; padding: 6px 16px; font-family: 'Segoe UI'; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: #2e6637; }}"
        )
        btn_load.clicked.connect(self._on_load_clicked)
        btn_box.addWidget(btn_load)

        layout.addLayout(btn_box)

    def _on_load_clicked(self) -> None:
        item = self.list_widget.currentItem()
        if item:
            self.selected_preset_name = item.text()
            self.accept()


class QtFilterDialog:
    """Controller for the PySide6 Filter Objects dialog."""

    def __init__(
        self,
        parent: QWidget | None = None,
        app_state=None,
        on_apply: Callable[[list[str]], None] | None = None,
        on_clear: Callable[[], None] | None = None,
    ):
        self.parent = parent
        self.app = app_state
        self.on_apply = on_apply
        self.on_clear = on_clear

        self.filter_manager = FilterManager()
        self.dialog: QDialog = load_ui("filter_dialog.ui", parent=parent)

        self.rows: dict[str, QtTriStateRow] = {}
        self.location_inputs: dict[str, QLineEdit] = {}

        self._init_metadata()
        self._build_rows()
        self._wire_signals()
        self.update_matched_count()

    def _init_metadata(self) -> None:
        """Extract problem and column maps from app_state or fallback defaults."""
        conf = getattr(self.app, "config", None)
        if not conf and hasattr(config, "DATABASE_CONFIGS"):
            conf = config.DATABASE_CONFIGS.get("Default (NHMO Vascular Plants)", {})

        sections = (conf or {}).get("ui_sections", {})

        self.problem_columns: list[str] = []
        self.problem_categories: dict[str, str] = {}
        self.problem_to_field: dict[str, str] = {}
        self.unknown_columns: list[str] = []
        self.unknown_to_field: dict[str, str] = {}
        self.location_fields: list[dict] = sections.get("location", [])

        for field in sections.get("problems", []):
            name = field.get("name")
            if not name:
                continue
            self.problem_columns.append(name)
            self.problem_categories[name] = field.get("category", "notes")
            if "maps_to" in field and field["maps_to"] and field["maps_to"] != "Other" and name != "Other_problem":
                self.problem_to_field[name] = field["maps_to"]
                unknown_name = name.replace("_Problem", "_Unknown")
                if "_Unknown" not in unknown_name:
                    unknown_name = name + "_Unknown"
                self.unknown_columns.append(unknown_name)
                self.unknown_to_field[unknown_name] = field["maps_to"]

    def _add_row(
        self,
        layout: QVBoxLayout,
        key: str,
        label: str,
        color_bar: str | None = None,
        initial_state: str = "Ignore",
    ) -> QtTriStateRow:
        row = QtTriStateRow(key, label, parent=self.dialog, color_bar=color_bar, initial_state=initial_state)
        row.state_changed.connect(lambda k, s: self.update_matched_count())
        layout.addWidget(row)
        self.rows[key] = row
        return row

    def _build_rows(self) -> None:
        """Populate the 4 tabs with Tri-State rows matching the Arbor catalog."""
        # -------------------------------------------------------------
        # TAB 1: Status & General
        # -------------------------------------------------------------
        p_status_layout = self.dialog.layout_processing_status
        self._add_row(p_status_layout, "Reviewed", "Reviewed", color_bar=qss_tokens.GREEN)
        self._add_row(p_status_layout, "Has_History", "Has Suggestions from Books", color_bar=qss_tokens.BORDER)
        self._add_row(p_status_layout, "Has_Unvalidated", "Has Unvalidated Source", color_bar=qss_tokens.BORDER)
        p_status_layout.addStretch(1)

        m_pres_layout = self.dialog.layout_metadata_presence
        self._add_row(m_pres_layout, "Has_Comment", "Has Comment")
        self._add_row(m_pres_layout, "Has_Location_Comment", "Has Location Comment")
        m_pres_layout.addStretch(1)

        old_tax_layout = self.dialog.layout_old_taxonomy
        # Prepend the tri-state toggle before the text input
        row_old_tax = QtTriStateRow("Search_Old_Taxonomy", "Search Old Taxonomy", parent=self.dialog, color_bar=qss_tokens.SUBTEXT)
        row_old_tax.state_changed.connect(lambda k, s: self.update_matched_count())
        old_tax_layout.insertWidget(0, row_old_tax)
        self.rows["Search_Old_Taxonomy"] = row_old_tax

        # -------------------------------------------------------------
        # TAB 2: Problems & History
        # -------------------------------------------------------------
        prob_cat = self.problem_categories

        # 1. Taxonomy & Scientific Identity
        tax_probs = [p for p in self.problem_columns if prob_cat.get(p) == "taxonomy"]
        if tax_probs:
            for p in tax_probs:
                self._add_row(self.dialog.layout_tax_problems, p, p.replace("_", " "), color_bar=qss_tokens.RED)
        else:
            self.dialog.group_tax_problems.setVisible(False)

        # 2. Collection Event & Provenance
        col_probs = [p for p in self.problem_columns if prob_cat.get(p) == "collection"]
        if col_probs:
            for p in col_probs:
                self._add_row(self.dialog.layout_col_problems, p, p.replace("_", " "), color_bar=qss_tokens.YELLOW)
        else:
            self.dialog.group_col_problems.setVisible(False)

        # 3. Physical Object & Storage
        phys_probs = [p for p in self.problem_columns if prob_cat.get(p) == "physical"]
        if phys_probs:
            for p in phys_probs:
                bar_col = qss_tokens.BORDER if "PlantPart" in p else "#795548"
                self._add_row(self.dialog.layout_phys_problems, p, p.replace("_", " "), color_bar=bar_col)
        else:
            self.dialog.group_phys_problems.setVisible(False)

        # 4. Other Discrepancies
        other_probs = [
            p for p in self.problem_columns
            if prob_cat.get(p) not in ("taxonomy", "collection", "physical", "media") and "Image" not in p
        ]
        if other_probs:
            for p in other_probs:
                self._add_row(self.dialog.layout_other_problems, p, p.replace("_", " "), color_bar=qss_tokens.HAIRLINE)
        else:
            self.dialog.group_other_problems.setVisible(False)

        # Global Aggregates & History
        g_layout = self.dialog.layout_global_problems
        self._add_row(g_layout, "Any_Problem", "Any problem (all error flags)", color_bar=qss_tokens.RED)
        self._add_row(g_layout, "Historical_Data", "Historical Data (Has / No History)", color_bar=qss_tokens.SUBTEXT)

        # Archival Gaps (Ukjent)
        u_layout = self.dialog.layout_unknown_problems
        self._add_row(u_layout, "Unknown", "Any settled 'Ukjent' field", color_bar=qss_tokens.YELLOW)
        self._add_row(u_layout, "Needs_ICEDIG_Review", "Needs ICEDIG Review", color_bar=qss_tokens.YELLOW)
        self._add_row(u_layout, "Has_ICEDIG_Code", "Has ICEDIG Code", color_bar=qss_tokens.GREEN)

        for col in self.unknown_columns:
            clean_name = col.replace("_Unknown", " Unknown").replace("_", " ")
            self._add_row(u_layout, col, clean_name, color_bar=qss_tokens.YELLOW)

        # -------------------------------------------------------------
        # TAB 3: Images
        # -------------------------------------------------------------
        img_layout = self.dialog.layout_images_checklist
        self._add_row(img_layout, "Has_Images", "Has Images", color_bar=qss_tokens.GREEN)
        self._add_row(img_layout, "Images_Missing", "Images Missing", color_bar=qss_tokens.RED)
        img_probs = [p for p in self.problem_columns if "Image" in p]
        for p in img_probs:
            if p not in ("Has_Images", "Images_Missing"):
                self._add_row(img_layout, p, p.replace("_", " "), color_bar=qss_tokens.RED)

        # Image Mode description
        img_mode = getattr(self.app, "image_mode", "online")
        if hasattr(self.dialog, "lbl_image_mode_info"):
            self.dialog.lbl_image_mode_info.setText(
                f"Active Image Mode: {img_mode.capitalize()} repository.\n"
                "Image queries resolve against local image folders or online image URLs based on startup configuration."
            )

        # -------------------------------------------------------------
        # TAB 4: Location
        # -------------------------------------------------------------
        self.location_inputs["Building"] = self.dialog.input_loc_building
        self.location_inputs["Floor"] = self.dialog.input_loc_floor
        self.location_inputs["Cabinet"] = self.dialog.input_loc_cabinet
        self.location_inputs["Drawer"] = self.dialog.input_loc_drawer

        # Build any extra dynamic location fields not in standard 4
        standard_locs = {"building", "floor", "cabinet", "drawer"}
        for field in self.location_fields:
            fname = field.get("name", "")
            if fname.lower() in standard_locs or not fname:
                continue

            row_layout = QHBoxLayout()
            row_layout.setSpacing(12)
            lbl = QLabel(fname, self.dialog)
            lbl.setMinimumWidth(140)
            lbl.setMaximumWidth(140)
            lbl.setStyleSheet("font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: bold; color: #2c302e;")
            inp = QLineEdit(self.dialog)
            inp.setPlaceholderText(f"Filter by {fname.lower()}...")
            inp.setClearButtonEnabled(True)
            inp.textChanged.connect(lambda: self.update_matched_count())
            row_layout.addWidget(lbl)
            row_layout.addWidget(inp)
            self.dialog.layout_location_extra.addLayout(row_layout)
            self.location_inputs[fname] = inp

    def _wire_signals(self) -> None:
        """Bind UI buttons, inputs, shortcuts, and presets."""
        self.dialog.input_filter_search.textChanged.connect(self._on_search_text_changed)
        self.dialog.radio_mode_and.toggled.connect(lambda: self.update_matched_count())
        self.dialog.radio_mode_or.toggled.connect(lambda: self.update_matched_count())

        for inp in self.location_inputs.values():
            inp.textChanged.connect(lambda: self.update_matched_count())
        self.dialog.input_old_taxonomy.textChanged.connect(lambda: self.update_matched_count())

        self.dialog.btn_load_preset.clicked.connect(self.load_preset)
        self.dialog.btn_save_preset.clicked.connect(self.save_preset)
        self.dialog.btn_clear_filter.clicked.connect(self.clear_filter)
        self.dialog.btn_cancel.clicked.connect(self.dialog.reject)
        self.dialog.btn_apply_filter.clicked.connect(self.apply_filter)

        # Shortcuts: Ctrl+Return to apply, Escape to close
        QShortcut(QKeySequence("Ctrl+Return"), self.dialog).activated.connect(self.apply_filter)
        QShortcut(QKeySequence("Ctrl+Enter"), self.dialog).activated.connect(self.apply_filter)
        QShortcut(QKeySequence("Escape"), self.dialog).activated.connect(self.dialog.reject)

    def _on_search_text_changed(self, text: str) -> None:
        """Dynamically filter visible rows based on live search box input."""
        q = text.strip().lower()

        # Track visible children per group box to auto-collapse empty sections
        group_counts: dict[QGroupBox, int] = {}

        for row in self.rows.values():
            is_visible = (not q) or (q in row.search_text)
            row.setVisible(is_visible)

            # Find parent groupbox
            parent = row.parentWidget()
            while parent and not isinstance(parent, QGroupBox) and parent != self.dialog:
                parent = parent.parentWidget()

            if isinstance(parent, QGroupBox):
                if is_visible:
                    group_counts[parent] = group_counts.get(parent, 0) + 1
                else:
                    group_counts.setdefault(parent, 0)

        # Hide group boxes whose rows are entirely filtered out
        if q:
            for grp, count in group_counts.items():
                grp.setVisible(count > 0)
        else:
            # Restore standard groups
            for grp in self.dialog.findChildren(QGroupBox):
                if grp != self.dialog.group_tax_problems and grp != self.dialog.group_col_problems:
                    grp.setVisible(True)
                else:
                    # Restore only if they had problem columns
                    if grp == self.dialog.group_tax_problems:
                        grp.setVisible(any(self.problem_categories.get(p) == "taxonomy" for p in self.problem_columns))
                    elif grp == self.dialog.group_col_problems:
                        grp.setVisible(any(self.problem_categories.get(p) == "collection" for p in self.problem_columns))

    def _get_preset_path(self) -> str:
        prefs_dir = os.path.dirname(getattr(config, "_PREFS_PATH", "user_prefs.json"))
        return os.path.join(prefs_dir, "filter_presets.json")

    def save_preset(self) -> None:
        """Prompt user for a preset name and save non-default values to JSON."""
        name, ok = QInputDialog.getText(self.dialog, "Save Preset", "Enter preset name:")
        if not ok or not name.strip():
            return
        name = name.strip()

        vars_to_save = {}
        for k, row in self.rows.items():
            if row.state in ("Has", "Not"):
                vars_to_save[k] = row.state

        locs = {k: inp.text().strip() for k, inp in self.location_inputs.items() if inp.text().strip()}

        preset = {
            "vars": vars_to_save,
            "locs": locs,
            "mode": "AND" if self.dialog.radio_mode_and.isChecked() else "OR",
            "old_taxonomy": self.dialog.input_old_taxonomy.text().strip(),
        }

        presets_file = self._get_preset_path()
        try:
            data = {}
            if os.path.exists(presets_file):
                with open(presets_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data[name] = preset
            with open(presets_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self.dialog, "Preset Saved", f"Successfully saved preset '{name}'.")
        except Exception as e:
            QMessageBox.critical(self.dialog, "Error", f"Failed to save preset: {e}")

    def load_preset(self) -> None:
        """Open preset picker and apply chosen preset."""
        presets_file = self._get_preset_path()
        if not os.path.exists(presets_file):
            QMessageBox.information(self.dialog, "Presets", "No presets saved yet.")
            return

        try:
            with open(presets_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self.dialog, "Error", f"Failed to load presets: {e}")
            return

        if not data:
            QMessageBox.information(self.dialog, "Presets", "No presets saved yet.")
            return

        picker = QtLoadPresetDialog(data, parent=self.dialog)
        if picker.exec() != QDialog.Accepted or not picker.selected_preset_name:
            return

        preset = data[picker.selected_preset_name]

        # Reset current filters before applying preset
        self.clear_filter(show_feedback=False)

        # Apply vars
        for k, v in preset.get("vars", {}).items():
            mapped_k = k
            if k == "Images_Missing":
                mapped_k = "Has_Images"
                v = "Not" if str(v).lower() in ("has", "true", "1") else "Has"
            elif k == "Not_Reviewed":
                mapped_k = "Reviewed"
                v = "Not" if str(v).lower() in ("has", "true", "1") else "Has"
            elif k in ("Comment_Not_Empty", "Comment_Empty"):
                mapped_k = "Has_Comment"
                if k == "Comment_Empty":
                    v = "Not" if str(v).lower() in ("has", "true", "1") else "Has"
            elif k in ("Extra_Not_Empty", "Extra_Empty"):
                mapped_k = "Has_Location_Comment"
                if k == "Extra_Empty":
                    v = "Not" if str(v).lower() in ("has", "true", "1") else "Has"

            if mapped_k in self.rows:
                self.rows[mapped_k].set_state(v, emit_signal=False)

        # Apply locs
        for k, val in preset.get("locs", {}).items():
            if k in self.location_inputs:
                self.location_inputs[k].setText(val)

        # Apply mode
        mode = preset.get("mode", "AND")
        if mode == "OR":
            self.dialog.radio_mode_or.setChecked(True)
        else:
            self.dialog.radio_mode_and.setChecked(True)

        if "old_taxonomy" in preset:
            self.dialog.input_old_taxonomy.setText(preset["old_taxonomy"])

        self.update_matched_count()

    def clear_filter(self, show_feedback: bool = True) -> None:
        """Reset all filter states to Ignore and empty location fields."""
        for row in self.rows.values():
            row.set_state("Ignore", emit_signal=False)

        for inp in self.location_inputs.values():
            inp.clear()

        self.dialog.input_old_taxonomy.clear()
        self.dialog.radio_mode_and.setChecked(True)
        self.update_matched_count()

        if self.on_clear:
            self.on_clear()

    def _build_filter_groups(self) -> tuple[dict, str, tuple[str, str, str], str]:
        """Construct the groups dictionary matching backend.filter.FilterManager."""
        groups = {
            "Problems": {},
            "Images": [],
            "Status": [],
            "Text": [],
        }

        for key, row in self.rows.items():
            val = row.state.upper()
            if val in ("HAS", "NOT"):
                if key in ("Has_Images", "Images_Missing") or (key in self.problem_columns and "Image" in key):
                    groups["Images"].append((key, val))
                elif (
                    key in ("Reviewed", "Has_History", "Has_Unvalidated", "Search_Old_Taxonomy", "Unknown", "Needs_ICEDIG_Review", "Has_ICEDIG_Code")
                    or key in self.unknown_columns
                ):
                    groups["Status"].append((key, val))
                elif key in ("Has_Comment", "Has_Location_Comment"):
                    groups["Text"].append((key, val))
                else:
                    groups["Problems"][key] = val

        mode = "AND" if self.dialog.radio_mode_and.isChecked() else "OR"

        bldg = self.location_inputs.get("Building", QLineEdit()).text().strip()
        floor = self.location_inputs.get("Floor", QLineEdit()).text().strip()
        cab = self.location_inputs.get("Cabinet", QLineEdit()).text().strip()
        loc_filters = (bldg, floor, cab)

        old_tax = self.dialog.input_old_taxonomy.text().strip()
        return groups, mode, loc_filters, old_tax

    def _compute_matches(self) -> list[str]:
        """Run FilterManager on the active AppState dataframes."""
        if not self.app or getattr(self.app, "df_reg", None) is None:
            return []

        df_reg = self.app.df_reg
        reg_dict = df_reg.to_dict(orient="index") if df_reg is not None else {}
        obs_df = getattr(self.app, "df_obs", None)
        obs_dict = obs_df.to_dict(orient="index") if obs_df is not None else {}

        history_set = getattr(self.app, "history_set", set())
        groups, mode, loc_filters, old_tax = self._build_filter_groups()

        matched = self.filter_manager.apply_filter(
            df_reg=df_reg,
            reg_dict=reg_dict,
            obs_dict=obs_dict,
            history_set=history_set,
            groups=groups,
            global_mode=mode,
            not_reviewed_only=False,
            location_filters=loc_filters,
            problem_columns=self.problem_columns,
            problem_to_field=self.problem_to_field,
            unknown_to_field=self.unknown_to_field,
            image_mode=getattr(self.app, "image_mode", "online"),
            df_unvalidated=getattr(self.app, "df_unvalidated", None),
            df_log=getattr(self.app, "df_log", None),
            old_taxonomy_query=old_tax,
            problem_categories=self.problem_categories,
        )
        return matched

    def update_matched_count(self) -> None:
        """Update footer matched records display."""
        if not self.app or getattr(self.app, "df_reg", None) is None:
            active_count = sum(1 for r in self.rows.values() if r.state != "Ignore")
            for inp in self.location_inputs.values():
                if inp.text().strip():
                    active_count += 1
            if self.dialog.input_old_taxonomy.text().strip():
                active_count += 1

            self.dialog.lbl_matched_count.setText(f"Active conditions: {active_count}")
            return

        total = len(self.app.df_reg)
        matched = self._compute_matches()
        shown = len(matched)

        if shown < total:
            self.dialog.lbl_matched_count.setText(f"Filter matches: {shown} / {total} objects")
            self.dialog.lbl_matched_count.setStyleSheet(
                f"font-family: 'JetBrains Mono', monospace; font-size: 11px; color: {qss_tokens.SEARCH_ORANGE}; font-weight: bold;"
            )
        else:
            self.dialog.lbl_matched_count.setText(f"All {total} objects match")
            self.dialog.lbl_matched_count.setStyleSheet(
                f"font-family: 'JetBrains Mono', monospace; font-size: 11px; color: {qss_tokens.SUBTEXT}; font-weight: bold;"
            )

    def apply_filter(self) -> None:
        """Apply active filter criteria to AppState and trigger callbacks."""
        matched = self._compute_matches()
        if self.app:
            self.app.active_object_ids = matched

        if self.on_apply:
            self.on_apply(matched)

        self.dialog.accept()

    def exec(self) -> int:
        return self.dialog.exec()

    def show(self) -> None:
        self.dialog.show()
