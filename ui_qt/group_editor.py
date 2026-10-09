"""Controller for the Specimen Group Editor Dialog in Qt (wrapping group_editor.ui)."""
from __future__ import annotations

import copy
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QInputDialog,
    QListWidgetItem,
    QMessageBox,
    QWidget,
)

from models import AppState
from ui_qt.loader import load_ui


class QtGroupEditorDialog:
    """Controller for managing specimen groups and their member assignments."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        app_state: Optional[AppState] = None,
        on_changed: Optional[Callable[[dict[str, list[str]]], None]] = None,
    ):
        self.app = app_state or AppState()
        self.parent = parent
        self.on_changed = on_changed
        self.win = load_ui("group_editor.ui", parent)

        # Initialize specimen_groups on app_state if not present
        if not hasattr(self.app, "specimen_groups") or self.app.specimen_groups is None:
            self.app.specimen_groups = self._init_groups_from_state()

        # Working copy of groups: {group_name: [oid, ...]}
        self.groups: dict[str, list[str]] = copy.deepcopy(self.app.specimen_groups)

        self._wire_signals()
        self.refresh_groups_list()

    def _init_groups_from_state(self) -> dict[str, list[str]]:
        """Construct initial groups dictionary from AppState or df_reg."""
        groups: dict[str, list[str]] = {}
        if self.app.df_reg is not None and "Group" in self.app.df_reg.columns:
            for grp, df_sub in self.app.df_reg.groupby("Group"):
                grp_name = str(grp).strip()
                if grp_name and grp_name != "<NA>" and grp_name != "nan":
                    groups[grp_name] = [str(x) for x in df_sub.index]
        return groups

    def _wire_signals(self) -> None:
        """Connect UI signals to controller methods."""
        if hasattr(self.win, "list_groups"):
            self.win.list_groups.currentItemChanged.connect(self._on_group_selection_changed)

        if hasattr(self.win, "btn_add_group"):
            self.win.btn_add_group.clicked.connect(self.create_group)

        if hasattr(self.win, "input_group_name"):
            self.win.input_group_name.returnPressed.connect(self.create_group)

        if hasattr(self.win, "btn_rename_group"):
            self.win.btn_rename_group.clicked.connect(self.rename_group)

        if hasattr(self.win, "btn_delete_group"):
            self.win.btn_delete_group.clicked.connect(self.delete_group)

        if hasattr(self.win, "btn_add_current"):
            self.win.btn_add_current.clicked.connect(self.add_current_object)

        if hasattr(self.win, "btn_add_filtered"):
            self.win.btn_add_filtered.clicked.connect(self.add_filtered_objects)

        if hasattr(self.win, "btn_remove_member"):
            self.win.btn_remove_member.clicked.connect(self.remove_selected_member)

        if hasattr(self.win, "btn_close"):
            self.win.btn_close.clicked.connect(self._on_close)

    def refresh_groups_list(self, select_name: Optional[str] = None) -> None:
        """Populate the left groups list widget with group names and member counts."""
        if not hasattr(self.win, "list_groups"):
            return

        self.win.list_groups.clear()
        target_item = None

        for name in sorted(self.groups.keys()):
            count = len(self.groups[name])
            item = QListWidgetItem(f"{name} ({count})")
            item.setData(Qt.UserRole, name)
            self.win.list_groups.addItem(item)
            if select_name and name == select_name:
                target_item = item

        if target_item:
            self.win.list_groups.setCurrentItem(target_item)
        elif self.win.list_groups.count() > 0:
            self.win.list_groups.setCurrentRow(0)
        else:
            self._refresh_members_list(None)

    def _selected_group_name(self) -> Optional[str]:
        """Return the bare name of the currently selected group."""
        if not hasattr(self.win, "list_groups"):
            return None
        item = self.win.list_groups.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    def _on_group_selection_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        """Slot called when selected group changes."""
        grp_name = current.data(Qt.UserRole) if current else None
        self._refresh_members_list(grp_name)

    def _refresh_members_list(self, group_name: Optional[str]) -> None:
        """Populate right members list for the specified group."""
        if not hasattr(self.win, "list_members"):
            return

        self.win.list_members.clear()
        if not group_name or group_name not in self.groups:
            return

        members = self.groups[group_name]
        reg_df = self.app.df_reg

        for oid in members:
            label = str(oid)
            if reg_df is not None and oid in reg_df.index:
                genus = str(reg_df.at[oid, "Genus"]) if "Genus" in reg_df.columns else ""
                species = str(reg_df.at[oid, "Species"]) if "Species" in reg_df.columns else ""
                if genus and genus not in ("<NA>", "nan", "None"):
                    label = f"{oid} — {genus} {species}".strip()

            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, str(oid))
            self.win.list_members.addItem(item)

    def create_group(self) -> None:
        """Create a new group with the name entered in input_group_name."""
        if not hasattr(self.win, "input_group_name"):
            return

        name = self.win.input_group_name.text().strip()
        if not name:
            return

        if name in self.groups:
            QMessageBox.warning(self.win, "Duplicate Group", f"Group '{name}' already exists.")
            return

        self.groups[name] = []
        self.win.input_group_name.clear()
        self.persist_changes()
        self.refresh_groups_list(select_name=name)

    def rename_group(self) -> None:
        """Prompt to rename the currently selected group."""
        current_name = self._selected_group_name()
        if not current_name:
            QMessageBox.information(self.win, "Select Group", "Please select a group to rename.")
            return

        new_name, ok = QInputDialog.getText(
            self.win,
            "Rename Group",
            f"Enter new name for group '{current_name}':",
            text=current_name,
        )
        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()
        if new_name == current_name:
            return

        if new_name in self.groups:
            QMessageBox.warning(self.win, "Duplicate Group", f"Group '{new_name}' already exists.")
            return

        self.groups[new_name] = self.groups.pop(current_name)
        self.persist_changes()
        self.refresh_groups_list(select_name=new_name)

    def delete_group(self) -> None:
        """Delete the currently selected group."""
        current_name = self._selected_group_name()
        if not current_name:
            return

        reply = QMessageBox.question(
            self.win,
            "Delete Group",
            f"Are you sure you want to delete group '{current_name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        del self.groups[current_name]
        self.persist_changes()
        self.refresh_groups_list()

    def add_current_object(self) -> None:
        """Assign current_object_id to the selected group."""
        current_group = self._selected_group_name()
        if not current_group:
            QMessageBox.information(self.win, "Select Group", "Please select a group first.")
            return

        oid = self.app.current_object_id
        if not oid:
            QMessageBox.information(self.win, "No Active Object", "No specimen is currently selected in the main workspace.")
            return

        oid = str(oid)
        if oid in self.groups[current_group]:
            QMessageBox.information(self.win, "Already Member", f"Object #{oid} is already in '{current_group}'.")
            return

        self.groups[current_group].append(oid)
        self.persist_changes()
        self.refresh_groups_list(select_name=current_group)

    def add_filtered_objects(self) -> None:
        """Assign all active_object_ids to the selected group."""
        current_group = self._selected_group_name()
        if not current_group:
            QMessageBox.information(self.win, "Select Group", "Please select a group first.")
            return

        oids = [str(x) for x in self.app.active_object_ids]
        if not oids:
            QMessageBox.information(self.win, "No Objects", "There are no active objects in the current view.")
            return

        added_count = 0
        group_members = set(self.groups[current_group])
        for oid in oids:
            if oid not in group_members:
                self.groups[current_group].append(oid)
                group_members.add(oid)
                added_count += 1

        self.persist_changes()
        self.refresh_groups_list(select_name=current_group)
        QMessageBox.information(self.win, "Objects Added", f"Added {added_count} objects to '{current_group}'.")

    def remove_selected_member(self) -> None:
        """Remove selected specimen from the active group."""
        current_group = self._selected_group_name()
        if not current_group or not hasattr(self.win, "list_members"):
            return

        item = self.win.list_members.currentItem()
        if not item:
            return

        oid = item.data(Qt.UserRole)
        if oid in self.groups[current_group]:
            self.groups[current_group].remove(oid)
            self.persist_changes()
            self.refresh_groups_list(select_name=current_group)

    def persist_changes(self) -> None:
        """Commit in-memory changes to AppState."""
        self.app.specimen_groups = copy.deepcopy(self.groups)
        self.app.dirty = True

        # Sync with Group column in df_reg if present
        if self.app.df_reg is not None and "Group" in self.app.df_reg.columns:
            for grp, members in self.groups.items():
                valid_members = [m for m in members if m in self.app.df_reg.index]
                if valid_members:
                    self.app.df_reg.loc[valid_members, "Group"] = grp

        if self.on_changed:
            try:
                self.on_changed(self.app.specimen_groups)
            except Exception:
                pass

    def _on_close(self) -> None:
        """Handle dialog close button."""
        self.persist_changes()
        self.win.accept()

    def exec(self) -> int:
        """Display modal dialog and return exit code."""
        return self.win.exec()
