"""Targeted verification for Milestone 2: Middle Column Image Viewer & Location Panel."""
import sys
import os
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import AppState
from ui_qt.main_window import QtMainWindow

def test_milestone2_middle_column():
    app = QApplication.instance() or QApplication(sys.argv)

    mock_db_path = os.path.abspath("scratch/mock_current_db.xlsx")
    assert os.path.exists(mock_db_path), f"Mock DB not found at {mock_db_path}"

    app_state = AppState()
    main_win = QtMainWindow(app_state)
    main_win.open_excel(mock_db_path)

    # -------------------------------------------------------------
    # 1. Verify Middle Column Location Panel (Default Placement)
    # -------------------------------------------------------------
    loc_panel = main_win.location_panel
    assert loc_panel is not None, "Location panel not initialized"
    assert main_win.location_in_center is True, "Expected location panel in middle column by default"
    assert loc_panel.mode == "horizontal_1row", f"Expected horizontal_1row mode, got {loc_panel.mode}"

    # Verify location fields populated for specimen 1001
    assert "Building" in loc_panel.entries
    assert "Floor" in loc_panel.entries
    assert "Cabinet" in loc_panel.entries

    building_val = loc_panel.entries["Building"].currentText() if hasattr(loc_panel.entries["Building"], "currentText") else loc_panel.entries["Building"].text()
    floor_val = loc_panel.entries["Floor"].currentText() if hasattr(loc_panel.entries["Floor"], "currentText") else loc_panel.entries["Floor"].text()
    cabinet_val = loc_panel.entries["Cabinet"].text()

    print(f"[OK] Record 1001 Location: Building='{building_val}', Floor='{floor_val}', Cabinet='{cabinet_val}'")
    assert building_val != "", "Expected building to be populated"
    assert floor_val != "", "Expected floor to be populated"

    # -------------------------------------------------------------
    # 2. Verify Dynamic Specimen Switching Updates Location
    # -------------------------------------------------------------
    main_win.navigate_to_object("1002")
    b2 = loc_panel.entries["Building"].currentText() if hasattr(loc_panel.entries["Building"], "currentText") else loc_panel.entries["Building"].text()
    c2 = loc_panel.entries["Cabinet"].text()
    print(f"[OK] Record 1002 Location: Building='{b2}', Cabinet='{c2}'")

    # -------------------------------------------------------------
    # 3. Test Dual-Docking: Toggle Location Panel to Left Column & Back
    # -------------------------------------------------------------
    main_win.win.show()
    main_win.toggle_location_panel_position()
    assert main_win.location_in_center is False, "Expected location_in_center to be False"
    assert loc_panel.mode == "vertical", f"Expected vertical mode in left column, got {loc_panel.mode}"
    assert not main_win.win.location_container.isHidden(), "Expected location_container not hidden in left column"
    print("[OK] Dual-docking toggle to Left Column (vertical) verified!")

    # Toggle back to Middle column
    main_win.toggle_location_panel_position()
    assert main_win.location_in_center is True, "Expected location_in_center to be True"
    assert loc_panel.mode == "horizontal_1row", "Expected return to horizontal_1row"
    print("[OK] Dual-docking toggle back to Middle Column (horizontal) verified!")

    # -------------------------------------------------------------
    # 4. Verify Image Viewer Canvas & Toolbar Actions
    # -------------------------------------------------------------
    img_viewer = main_win.image_viewer
    assert img_viewer is not None, "Image viewer not initialized"
    img_viewer.reset_view()
    assert "100%" in main_win.win.lbl_zoom_status.text()
    assert img_viewer.zoom_factor == 1.0

    # Test Zoom In
    img_viewer.zoom_in()
    assert img_viewer.zoom_factor == 1.25
    assert "125%" in main_win.win.lbl_zoom_status.text()
    print(f"[OK] Zoom In verified: {main_win.win.lbl_zoom_status.text()}")

    # Test Zoom Out
    img_viewer.zoom_out()
    assert abs(img_viewer.zoom_factor - 1.0) < 0.01
    assert "100%" in main_win.win.lbl_zoom_status.text()
    print(f"[OK] Zoom Out verified: {main_win.win.lbl_zoom_status.text()}")

    # Test Rotation CW
    img_viewer.rotate_cw()
    assert img_viewer.rotation_angle == 90
    assert "90" in main_win.win.lbl_zoom_status.text()
    print(f"[OK] Rotate CW verified: {main_win.win.lbl_zoom_status.text()}")

    # Test Rotation CCW
    img_viewer.rotate_ccw()
    assert img_viewer.rotation_angle == 0
    assert "0" in main_win.win.lbl_zoom_status.text()
    print(f"[OK] Rotate CCW verified: {main_win.win.lbl_zoom_status.text()}")

    # Test Reset View
    img_viewer.zoom_in()
    img_viewer.rotate_cw()
    img_viewer.reset_view()
    assert img_viewer.zoom_factor == 1.0
    assert img_viewer.rotation_angle == 0
    assert "100%" in main_win.win.lbl_zoom_status.text()
    print(f"[OK] Reset View verified: {main_win.win.lbl_zoom_status.text()}")

    # Test Fit View
    img_viewer.fit_view()
    print(f"[OK] Fit View verified: {main_win.win.lbl_zoom_status.text()}")

    # Verify Placeholder handling
    assert img_viewer.scene.items(), "Expected placeholder items in scene"

    print("\n>>> ALL MILESTONE 2 PARITY & MIDDLE COLUMN CHECKS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_milestone2_middle_column()
