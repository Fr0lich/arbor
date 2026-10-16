"""Test script verifying Milestone 1 data binding in QtMainWindow."""
import sys
import os
import pytest
from PySide6.QtWidgets import QApplication

# Ensure Arbor root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import AppState
import config
from ui_qt.main_window import QtMainWindow

def test_milestone1_data_binding():
    app = QApplication.instance() or QApplication(sys.argv)
    
    mock_db_path = os.path.abspath("scratch/mock_current_db.xlsx")
    assert os.path.exists(mock_db_path), f"Mock DB not found at {mock_db_path}"

    app_state = AppState()
    main_win = QtMainWindow(app_state)
    
    # Open the mock excel database
    main_win.open_excel(mock_db_path)

    # 1. Verify Tree Population & Real String ObjectIDs
    tree = main_win.win.tree_objects
    assert tree.topLevelItemCount() == 25, f"Expected 25 items, got {tree.topLevelItemCount()}"

    item_0 = tree.topLevelItem(0)
    assert item_0.text(1) == "1001", f"Expected ID 1001, got {item_0.text(1)}"
    assert "Pinus" in item_0.text(2), f"Expected Pinus in taxon, got {item_0.text(2)}"

    item_1 = tree.topLevelItem(1)
    assert item_1.text(1) == "1002", f"Expected ID 1002, got {item_1.text(1)}"

    # 2. Verify Middle Column Context Bar for Initial Selection (1001)
    assert "ID: 1001" in main_win.win.lbl_id_badge.text()
    assert "Pinus sylvestris" in main_win.win.lbl_specimen_name.text()
    assert main_win.win.lbl_status_badge.text() != ""

    # 3. Verify Right Column Registration Form for 1001
    assert hasattr(main_win, "registry_panel")
    reg_panel = main_win.registry_panel
    assert reg_panel is not None
    assert "Genus" in reg_panel.reg_entries
    assert "Species" in reg_panel.reg_entries
    assert "Collector" in reg_panel.reg_entries

    assert reg_panel.reg_entries["Genus"].text() == "Pinus"
    assert reg_panel.reg_entries["Species"].text() == "sylvestris"
    collector_1001 = reg_panel.reg_entries["Collector"].text()
    assert collector_1001 != "", "Expected collector name to be populated"
    print(f"[OK] Record 1001: {reg_panel.reg_entries['Genus'].text()} {reg_panel.reg_entries['Species'].text()} | Collector: {collector_1001}")

    # 4. Switch Selection to Record 1002 and Verify Dynamic Update
    main_win.navigate_to_object("1002")
    assert "ID: 1002" in main_win.win.lbl_id_badge.text()
    assert "Betula" in main_win.win.lbl_specimen_name.text()
    assert reg_panel.reg_entries["Genus"].text() == "Betula"
    assert reg_panel.reg_entries["Species"].text() == "pendula"
    print(f"[OK] Record 1002: {reg_panel.reg_entries['Genus'].text()} {reg_panel.reg_entries['Species'].text()}")

    # 5. Switch Selection to Record 1003 (Pinuss mugo - deliberate typo)
    main_win.navigate_to_object("1003")
    assert "ID: 1003" in main_win.win.lbl_id_badge.text()
    assert "Pinuss" in main_win.win.lbl_specimen_name.text()
    assert reg_panel.reg_entries["Genus"].text() == "Pinuss"
    assert reg_panel.reg_entries["Species"].text() == "mugo"
    print(f"[OK] Record 1003: {reg_panel.reg_entries['Genus'].text()} {reg_panel.reg_entries['Species'].text()}")

    # 6. Switch Selection to Record 1004 (Abies alba)
    main_win.navigate_to_object("1004")
    assert "ID: 1004" in main_win.win.lbl_id_badge.text()
    assert "Abies" in main_win.win.lbl_specimen_name.text()
    assert reg_panel.reg_entries["Genus"].text() == "Abies"
    assert reg_panel.reg_entries["Species"].text() == "alba"
    status_text = main_win.win.lbl_status_badge.text()
    print(f"[OK] Record 1004: {reg_panel.reg_entries['Genus'].text()} {reg_panel.reg_entries['Species'].text()} | Status: {status_text}")

    print("\n>>> ALL MILESTONE 1 PARITY & DATA BINDING CHECKS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_milestone1_data_binding()
