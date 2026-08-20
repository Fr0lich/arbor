import pytest
import tkinter as tk
from ui.image_toolbar import create_image_toolbar


@pytest.fixture
def tk_root():
    """Provides a hidden root Tk instance for component testing."""
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_toolbar_creation(tk_root):
    toolbar = create_image_toolbar(tk_root, design_mode="standard", dark_mode=False)
    assert toolbar is not None
    assert toolbar.design_mode == "standard"
    assert toolbar.dark_mode is False
    assert "zoom_in" in toolbar.buttons
    assert "zoom_out" in toolbar.buttons
    assert "rotate_cw" in toolbar.buttons
    assert "rotate_ccw" in toolbar.buttons
    assert "reset" in toolbar.buttons
    assert "fit" in toolbar.buttons


def test_toolbar_status_formatting(tk_root):
    toolbar = create_image_toolbar(tk_root, zoom_level=1.25, rotation_angle=90)
    status_text = toolbar._format_status_text()
    assert "125%" in status_text
    assert "90°" in status_text

    toolbar.set_status(2.50, 270)
    assert "250%" in toolbar._format_status_text()
    assert "270°" in toolbar._format_status_text()


def test_design_mode_toggle(tk_root):
    toggled_modes = []

    def on_toggle(mode):
        toggled_modes.append(mode)

    callbacks = {"design_toggle": on_toggle}
    toolbar = create_image_toolbar(tk_root, live_callbacks=callbacks, design_mode="standard")

    assert toolbar.design_mode == "standard"
    
    # Toggle to large mode
    toolbar.set_design_mode("large")
    assert toolbar.design_mode == "large"
    assert toolbar.buttons["zoom_in"].mode == "large"

    # Trigger toggle widget handler directly
    toolbar._handle_design_toggle("standard")
    assert toolbar.design_mode == "standard"
    assert "standard" in toggled_modes


def test_callbacks_invocation(tk_root):
    invoked = []

    callbacks = {
        "zoom_in": lambda: invoked.append("zoom_in"),
        "zoom_out": lambda: invoked.append("zoom_out"),
        "rotate_cw": lambda deg: invoked.append(f"rotate_cw_{deg}"),
        "rotate_ccw": lambda deg: invoked.append(f"rotate_ccw_{deg}"),
        "reset": lambda: invoked.append("reset"),
        "fit": lambda: invoked.append("fit"),
    }

    toolbar = create_image_toolbar(tk_root, live_callbacks=callbacks)

    toolbar._handle_zoom_in()
    assert "zoom_in" in invoked

    toolbar._handle_zoom_out()
    assert "zoom_out" in invoked

    toolbar._handle_rotate_cw()
    assert "rotate_cw_90" in invoked

    toolbar._handle_rotate_ccw()
    assert "rotate_ccw_-90" in invoked

    toolbar._handle_reset()
    assert "reset" in invoked

    toolbar._handle_fit()
    assert "fit" in invoked


def test_dark_mode_switch(tk_root):
    toolbar = create_image_toolbar(tk_root, dark_mode=False)
    assert toolbar.dark_mode is False

    toolbar.set_dark_mode(True)
    assert toolbar.dark_mode is True
    assert toolbar.colors["surface"] == "#1e1e2e"

    toolbar.set_dark_mode(False)
    assert toolbar.dark_mode is False
    assert toolbar.colors["surface"] == "#f9f9f9"
