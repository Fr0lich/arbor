"""Unit tests for High-DPI NavigationBar geometry and Modal mousewheel scroll consistency."""

import tkinter as tk
from unittest.mock import MagicMock
import pytest
import config
from ui.navigation_bar import NavigationBar
from ui.create_collection_dialog import CreateCollectionDialog
from ui.dialogs import StartupDialog


def test_navigation_bar_high_dpi_geometry_scaling():
    """Verify NavigationBar geometry scales dynamically with sc() under UI_SCALE = 1.0 and 1.5."""
    orig_scale = config.UI_SCALE
    root = tk.Tk()
    root.withdraw()

    try:
        # 1. Test at UI_SCALE = 1.0
        config.UI_SCALE = 1.0
        app1 = MagicMock()
        app1.toolbar_buttons = {}
        app1.toolbar_vars = {}
        app1.add_tooltip = lambda widget, text: None
        parent_frame1 = tk.Frame(root)
        parent_frame1.pack()

        NavigationBar.build_nav_ui(app1, parent_frame1)

        # Verify scaled geometry at 1.0
        nav_bar_height_1 = int(app1.nav_bar.cget("height"))
        assert nav_bar_height_1 == 48

        title_padx_1 = int(app1.nav_title_lbl.cget("padx"))
        assert title_padx_1 == 16

        # Verify progress bar length at 1.0
        progress_len_1 = int(app1.image_scan_progress.cget("length"))
        assert progress_len_1 == 140

        # Verify data_status is created for backward compatibility but NOT packed
        assert hasattr(app1, "data_status")
        assert app1.data_status.winfo_manager() == ""

        # 2. Test at UI_SCALE = 1.5
        config.UI_SCALE = 1.5
        app2 = MagicMock()
        app2.toolbar_buttons = {}
        app2.toolbar_vars = {}
        app2.add_tooltip = lambda widget, text: None
        parent_frame2 = tk.Frame(root)
        parent_frame2.pack()

        NavigationBar.build_nav_ui(app2, parent_frame2)

        # Verify scaled geometry at 1.5: 48 -> 72, 16 -> 24, 140 -> 210
        nav_bar_height_2 = int(app2.nav_bar.cget("height"))
        assert nav_bar_height_2 == 72

        title_padx_2 = int(app2.nav_title_lbl.cget("padx"))
        assert title_padx_2 == 24

        progress_len_2 = int(app2.image_scan_progress.cget("length"))
        assert progress_len_2 == 210

    finally:
        config.UI_SCALE = orig_scale
        root.destroy()


def test_create_collection_dialog_canvas_scroll_binding():
    """Verify CreateCollectionDialog canvas receives ScrollTag_<id> and does not hijack root bind_all."""
    root = tk.Tk()
    root.withdraw()

    try:
        dialog = CreateCollectionDialog(root)

        assert hasattr(dialog, "canvas")
        assert hasattr(dialog, "scrollable_frame")

        tag = f"ScrollTag_{id(dialog.canvas)}"

        # Check tag in canvas bindtags
        assert tag in dialog.canvas.bindtags()

        # Check tag in scrollable_frame bindtags
        assert tag in dialog.scrollable_frame.bindtags()

        # Canvas itself has mousewheel and linux buttons bound
        canvas_bindings = dialog.canvas.bind()
        assert "<MouseWheel>" in canvas_bindings
        assert "<Button-4>" in canvas_bindings
        assert "<Button-5>" in canvas_bindings

        # Global root has no destructive mousewheel hijacking
        assert "<MouseWheel>" not in root.bind()

        dialog.win.destroy()
    finally:
        root.destroy()


def test_startup_dialog_scroll_binding_and_scaling():
    """Verify StartupDialog canvas mousewheel binding and coordinate scaling."""
    root = tk.Tk()
    root.withdraw()

    try:
        mock_app = MagicMock()
        startup = StartupDialog(root, mock_app)

        assert hasattr(startup, "canvas")
        assert hasattr(startup, "_outer")

        tag = f"ScrollTag_{id(startup.canvas)}"

        # Verify tag in canvas and inner frame bindtags
        assert tag in startup.canvas.bindtags()
        assert tag in startup._outer.bindtags()

        # Verify canvas bindings
        canvas_bindings = startup.canvas.bind()
        assert "<MouseWheel>" in canvas_bindings
        assert "<Button-4>" in canvas_bindings
        assert "<Button-5>" in canvas_bindings

        # Global root has no destructive mousewheel hijacking
        assert "<MouseWheel>" not in root.bind()

        startup.win.destroy()
    finally:
        root.destroy()


def test_bind_mousewheel_tag_routing():
    """Verify non-destructive mousewheel tag routing from scroll_helper."""
    from ui.scroll_helper import bind_mousewheel
    root = tk.Tk()
    root.withdraw()
    try:
        canvas = tk.Canvas(root, height=200, width=200)
        canvas.pack()

        frame = tk.Frame(canvas)
        label = tk.Label(frame, text="Inside scroll frame")
        label.pack()

        bind_mousewheel(canvas, frame)

        tag = f"ScrollTag_{id(canvas)}"
        assert tag in frame.bindtags()
        assert tag in label.bindtags()
        assert "<MouseWheel>" not in root.bind()
    finally:
        root.destroy()


def test_show_about_fetches_dynamic_version():
    """Verify show_about dynamically reads config.APP_VERSION and TkVersion."""
    import config
    from ui import help_dialogs

    root = tk.Tk()
    root.withdraw()
    try:
        mock_ui = MagicMock()
        mock_ui.root = root
        mock_ui.dark_mode_active = False
        mock_ui.app = None

        help_dialogs.show_about(mock_ui)
        about_win = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][0]
        assert about_win.title() == "About Arbor"

        # Inspect labels inside about window to ensure dynamic config.APP_VERSION is shown
        found_version = False
        for child in about_win.winfo_children():
            for sub in getattr(child, "winfo_children", lambda: [])():
                for row in getattr(sub, "winfo_children", lambda: [])():
                    for lbl in getattr(row, "winfo_children", lambda: [])():
                        if isinstance(lbl, tk.Label) and config.APP_VERSION in lbl.cget("text"):
                            found_version = True
        assert found_version, f"Expected {config.APP_VERSION} to be displayed in About dialog"
        about_win.destroy()
    finally:
        root.destroy()


def test_show_shortcuts_data_contains_canonical_keys():
    """Verify show_shortcuts data registry contains Space, Ctrl+S, Ctrl+Enter, keycaps, and Excel impacts."""
    from ui.keybindings import get_canonical_shortcuts, KeybindingManager

    shortcuts = get_canonical_shortcuts()
    assert len(shortcuts) >= 10
    assert KeybindingManager.get_shortcuts_registry() == shortcuts

    # Must contain Space, Ctrl+S, Ctrl+Enter with visual keycaps
    keys_upper = " ".join(item[1] for item in shortcuts).upper()
    assert "[ SPACE ]" in keys_upper
    assert "[ CTRL ] + [ S ]" in keys_upper
    assert "[ CTRL ] + [ ENTER ]" in keys_upper

    # Must contain dual-depth Excel translation bridge impacts
    excel_text = " ".join(item[3] for item in shortcuts if len(item) > 3)
    assert "Reviewed" in excel_text and "Excel" in excel_text
    assert ".xlsx" in excel_text

    # Zero barcode references in shortcuts registry
    full_text = " ".join(" ".join(item) for item in shortcuts)
    assert "barcode" not in full_text.lower()


def test_show_main_help_locates_and_parses_user_guide():
    """Verify show_main_help loads USER_GUIDE.md and provides chapter bookmarks."""
    from ui import help_dialogs

    root = tk.Tk()
    root.withdraw()
    try:
        mock_ui = MagicMock()
        mock_ui.root = root
        mock_ui.dark_mode_active = False

        help_dialogs.show_main_help(mock_ui)
        help_win = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][0]
        assert "Arbor System User Guide" in help_win.title()

        # Locate text widget
        txt_widget = None
        for child in help_win.winfo_children():
            for sub in getattr(child, "winfo_children", lambda: [])():
                if isinstance(sub, tk.Text):
                    txt_widget = sub
        assert txt_widget is not None
        text_content = txt_widget.get("1.0", "end")
        assert "Welcome to Arbor" in text_content or "Trainee Work Manual" in text_content
        assert "barcode" not in text_content.lower()

        help_win.destroy()
    finally:
        root.destroy()


def test_setting_info_texts_dual_depth_and_lexicon():
    """Verify SETTING_INFO_TEXTS in ui/unified_settings.py has dual-depth learning and no banned terms."""
    from ui.unified_settings import SETTING_INFO_TEXTS

    assert len(SETTING_INFO_TEXTS) >= 10

    banned_terms = ["schema", "rest api", "daemon", "relational join", "serialization", "barcode"]

    for key, text in SETTING_INFO_TEXTS.items():
        lower_text = text.lower()
        for banned in banned_terms:
            assert banned not in lower_text, f"Banned term '{banned}' found in setting '{key}' tooltip"

    # Critical settings must mention Excel/safety impacts
    assert "excel" in SETTING_INFO_TEXTS["focus_fallback"].lower()
    assert "excel" in SETTING_INFO_TEXTS["auto_advance_history"].lower()
    assert "excel" in SETTING_INFO_TEXTS["mobile_autosave_on_stop"].lower()
    assert ".xlsx" in SETTING_INFO_TEXTS["mobile_autosave_on_stop"].lower()



