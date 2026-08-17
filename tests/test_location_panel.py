import pytest
import tkinter as tk
from ui.location_panel import LocationPanel, create_location_panel


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
        root.withdraw()
        yield root
        root.destroy()
    except Exception as e:
        pytest.skip(f"Tkinter display not available: {e}")


def test_location_panel_init_vertical(tk_root):
    panel = create_location_panel(tk_root, mode="vertical")
    assert isinstance(panel, LocationPanel)
    assert panel.mode == "vertical"
    data = panel.get_data()
    assert "Stored as" in data
    assert "Building" in data
    assert "Floor" in data
    assert "Cabinet" in data
    assert "Extra" in data
    assert "Loaned out" in data


def test_location_panel_init_horizontal_modes(tk_root):
    panel_1row = create_location_panel(tk_root, mode="horizontal_1row")
    assert panel_1row.mode == "horizontal_1row"
    
    panel_2row = create_location_panel(tk_root, mode="horizontal_2row")
    assert panel_2row.mode == "horizontal_2row"


def test_set_layout_mode_switch(tk_root):
    panel = create_location_panel(tk_root, mode="vertical")
    assert panel.mode == "vertical"
    
    panel.set_layout_mode("horizontal_1row")
    assert panel.mode == "horizontal_1row"
    
    panel.set_layout_mode("horizontal_2row")
    assert panel.mode == "horizontal_2row"


def test_set_dark_mode(tk_root):
    panel = create_location_panel(tk_root, dark_mode=False)
    assert panel.dark_mode is False
    
    panel.set_dark_mode(True)
    assert panel.dark_mode is True


def test_data_get_set(tk_root):
    panel = create_location_panel(tk_root)
    sample = {
        "Stored as": "Mounted on wooden platform",
        "Building": "Lid's hus",
        "Floor": "2",
        "Cabinet": "C-12",
        "Extra": "Lower shelf",
        "Loaned out": "True"
    }
    panel.set_data(sample)
    data = panel.get_data()
    assert data["Stored as"] == "Mounted on wooden platform"
    assert data["Building"] == "Lid's hus"
    assert data["Floor"] == "2"
    assert data["Cabinet"] == "C-12"
    assert data["Extra"] == "Lower shelf"
    assert data["Loaned out"] == "True"


def test_callbacks_fire(tk_root):
    events = []
    
    callbacks = {
        "on_field_change": lambda f, v: events.append(("field_change", f, v)),
        "on_commit": lambda d: events.append(("commit", d)),
        "on_preset_applied": lambda p, d: events.append(("preset_applied", p)),
        "on_preset_saved": lambda p, d: events.append(("preset_saved", p)),
        "on_loan_toggle": lambda active: events.append(("loan_toggle", active)),
    }
    
    panel = create_location_panel(tk_root, live_callbacks=callbacks)
    
    # Trigger field change
    panel.location_vars["Building"].set("Økern")
    assert any(e[0] == "field_change" and e[1] == "Building" and e[2] == "Økern" for e in events)
    
    # Trigger preset apply
    panel.apply_active_preset()
    assert any(e[0] == "preset_applied" for e in events)
    assert any(e[0] == "commit" for e in events)
