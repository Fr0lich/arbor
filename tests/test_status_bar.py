"""Tests for decoupled StatusBarPanel and layout settings dead widget purge.

Verifies:
1. StatusBarPanel initializes cleanly without creating sb_top, sb_buttons_frame,
   sb_settings_btn, or sb_help_btn frames, and maintains height ~26px.
2. update_status(total=50, reviewed=25, problems=5) correctly formats telemetry.
3. Theme switching (apply_light_theme and apply_dark_theme) does not raise
   AttributeError or TclError.
"""

import pytest
import tkinter as tk
from tkinter import ttk

from ui.status_bar import StatusBarPanel
from ui.layout_settings import LayoutSettingsMixin


class MockApp:
    """Mock Application state for testing."""
    def __init__(self):
        self.active_object_ids = ["OBJ-001", "OBJ-002"]
        self.df_reg = None
        self.df_obs = None


class MockUI(LayoutSettingsMixin):
    """Mock MainWindow implementing LayoutSettingsMixin with minimal Tkinter structure."""
    def __init__(self, root):
        self.root = root
        self.app = MockApp()
        self.dark_mode_active = False

        # Status bar containers
        statusbar_bg = "#1c1b1b"
        self._status_bar_frame = tk.Frame(self.root, bg=statusbar_bg, height=26)
        self._status_bar_frame.pack(side="bottom", fill="x")

        # Mock collections expected by LayoutSettingsMixin.apply_theme
        self.reg_entries = {}
        self.location_entries = {}
        self.problem_switches = {}
        self.review_card_buttons = {}
        self.toolbar_buttons = {}
        self.toolbar_vars = {}
        self.filter_buttons = {}

        # Mock treeview for tag_configure
        self.object_list = ttk.Treeview(self.root)
        self.object_list.pack()

        # Instantiate decoupled status bar panel
        self.status_bar_panel = StatusBarPanel(self._status_bar_frame, self)

    def _open_unified(self):
        pass

    def open_help_window(self):
        pass

    def show_statistics(self):
        pass

    def open_log_viewer_window(self):
        pass


@pytest.fixture
def tk_env():
    """Create a hidden Tk root and MockUI instance for tests, destroying on teardown."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tkinter display unavailable in test environment")

    root.withdraw()
    ui = MockUI(root)
    root.update_idletasks()

    yield root, ui

    try:
        root.destroy()
    except Exception:
        pass


def test_status_bar_initialization_and_dead_widget_purge(tk_env):
    """Verify StatusBarPanel constructs cleanly at ~26px height without creating sb_top frames."""
    root, ui = tk_env
    panel = ui.status_bar_panel

    # Ensure sb_top and obsolete button stubs are None properties (not Tk widgets)
    assert panel.sb_top is None
    assert panel.sb_buttons_frame is None
    assert panel.sb_settings_btn is None
    assert panel.sb_help_btn is None

    # Verify stubs can be set without raising AttributeError
    panel.sb_top = "test_ignore"
    assert panel.sb_top is None

    # Verify ui backward-compatibility stubs do not hold live dead widgets
    assert not hasattr(ui, "sb_top") or getattr(ui, "sb_top") is None
    assert not hasattr(ui, "sb_buttons_frame") or getattr(ui, "sb_buttons_frame") is None
    assert not hasattr(ui, "sb_settings_btn") or getattr(ui, "sb_settings_btn") is None
    assert not hasattr(ui, "sb_help_btn") or getattr(ui, "sb_help_btn") is None

    # Verify sb_bottom points to the live status bar frame
    assert panel.sb_bottom == ui._status_bar_frame
    assert ui.sb_bottom == ui._status_bar_frame

    # Verify height is ~26px (within standard font/DPI variance 18px-34px)
    req_h = ui._status_bar_frame.winfo_reqheight()
    assert 18 <= req_h <= 34, f"Expected height ~26px, got {req_h}px"

    # Verify children: no child is or contains an sb_top frame
    children = ui._status_bar_frame.winfo_children()
    for child in children:
        assert getattr(child, "name", "") != "sb_top"

    # Verify critical specimen telemetry widgets exist and are packed
    assert "object_count" in panel.labels
    assert "reviewed" in panel.labels
    assert "problems" in panel.labels
    assert "last_save" in panel.labels
    assert panel.filter_active_badge is not None
    assert panel.filter_active_badge.winfo_exists()


def test_status_bar_update_status_telemetry(tk_env):
    """Verify update_status correctly formats OBJECT_COUNT, REVIEWED, and PROBLEMS."""
    root, ui = tk_env
    panel = ui.status_bar_panel

    # Test exact requirement values: total=50, reviewed=25, problems=5
    panel.update_status(total=50, reviewed=25, problems=5)

    assert panel.labels["object_count"].cget("text") == "OBJECT_COUNT: 50"
    assert panel.labels["reviewed"].cget("text") == "REVIEWED: 25"
    assert panel.labels["problems"].cget("text") == "PROBLEMS: 5"
    # When problems > 0, problems label foreground must highlight in red (#ff6b6b)
    assert panel.problems_lbl.cget("foreground") == "#ff6b6b"

    # Test with 0 problems and large count formatting
    panel.update_status(total=5000, reviewed="100%", problems=0, last_save="12:00:00")
    assert panel.labels["object_count"].cget("text") == "OBJECT_COUNT: 5,000"
    assert panel.labels["reviewed"].cget("text") == "REVIEWED: 100%"
    assert panel.labels["problems"].cget("text") == "PROBLEMS: 0"
    assert panel.labels["last_save"].cget("text") == "LAST_SAVE: 12:00:00"
    assert panel.problems_lbl.cget("foreground") == "#e2e2e2"


def test_status_bar_theme_switching_no_errors(tk_env):
    """Verify theme switching (apply_light_theme and apply_dark_theme) executes cleanly."""
    root, ui = tk_env

    # 1. Apply dark theme
    ui.apply_dark_theme()
    assert ui.dark_mode_active is True
    root.update_idletasks()

    # Verify status bar theming succeeded in dark mode (#141715)
    assert ui.sb_bottom.cget("background") == "#141715"

    # 2. Apply light theme
    ui.apply_light_theme()
    assert ui.dark_mode_active is False
    root.update_idletasks()

    # Verify status bar theming succeeded in light mode (#2c302e)
    assert ui.sb_bottom.cget("background") == "#2c302e"

    # 3. Toggle dark mode back and forth to ensure registration doesn't reference dead widgets
    ui.toggle_dark_mode()
    assert ui.dark_mode_active is True
    root.update_idletasks()
    assert ui.sb_bottom.cget("background") == "#141715"

    ui.toggle_dark_mode()
    assert ui.dark_mode_active is False
    root.update_idletasks()
    assert ui.sb_bottom.cget("background") == "#2c302e"
