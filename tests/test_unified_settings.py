import os
import sys
import tkinter as tk
import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import config
from ui.unified_settings import UnifiedSettingsWindow

@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
        root.withdraw()
        yield root
        root.destroy()
    except Exception as e:
        pytest.skip(f"Tkinter display not available: {e}")

def test_unified_settings_initialization(tk_root):
    win = UnifiedSettingsWindow(tk_root, initial_tab="general")
    assert win.win.winfo_exists()
    assert win.active_tab == "general"
    assert "general" in win.tabs
    assert "appearance" in win.tabs
    assert "layout" in win.tabs
    assert "focus" in win.tabs
    assert "presets" in win.tabs
    assert "advanced" in win.tabs
    win.win.destroy()

def test_unified_settings_tab_navigation(tk_root):
    win = UnifiedSettingsWindow(tk_root, initial_tab="appearance")
    assert win.active_tab == "appearance"

    win.show_tab("focus")
    assert win.active_tab == "focus"

    win.show_tab("presets")
    assert win.active_tab == "presets"
    win.win.destroy()

def test_unified_settings_live_callbacks(tk_root):
    events = {}

    def _callback(val):
        events["dark_mode"] = val

    win = UnifiedSettingsWindow(tk_root, initial_tab="appearance", live_callbacks={"dark_mode": _callback})
    win.var_dark_mode.set(True)
    win._notify_live("dark_mode", True)

    assert events.get("dark_mode") is True
    win.win.destroy()

def test_unified_settings_save_prefs(tk_root, tmp_path, monkeypatch):
    test_prefs_file = str(tmp_path / "user_prefs.json")
    monkeypatch.setattr(config, "_PREFS_PATH", test_prefs_file)
    monkeypatch.setattr(config, "_prefs_cache", None)

    win = UnifiedSettingsWindow(tk_root, initial_tab="general")
    win.var_autosave_mins.set("15")
    win.var_dark_mode.set(True)
    win.var_location_2row.set(True)
    win.var_auto_advance.set(False)
    win.var_auto_advance_history.set(True)
    win.var_large_reviewed_btn.set(True)
    win.var_snap_lock.set(True)
    win.save_settings()

    loaded = config.load_prefs()
    assert loaded.get("autosave_interval") == 15
    assert loaded.get("dark_mode") is True
    assert loaded.get("location_2row") is True
    assert loaded.get("auto_advance_on_review") is False
    assert loaded.get("auto_advance_history") is True
    assert loaded.get("large_reviewed_button") is True
    assert loaded.get("snap_lock") is True


def test_unified_settings_live_callbacks_comprehensive(tk_root):
    events = {}

    def record(key, val):
        events[key] = val

    callbacks = {
        "dark_mode": lambda v: record("dark_mode", v),
        "problem_highlights": lambda v: record("problem_highlights", v),
        "problem_highlight_color": lambda v: record("problem_highlight_color", v),
        "large_reviewed_btn": lambda v: record("large_reviewed_btn", v),
        "snap_lock": lambda v: record("snap_lock", v),
        "location_2row": lambda v: record("location_2row", v),
        "image_stack": lambda v: record("image_stack", v),
    }

    win = UnifiedSettingsWindow(tk_root, initial_tab="appearance", live_callbacks=callbacks)
    win._notify_live("problem_highlights", False)
    assert events.get("problem_highlights") is False

    win._notify_live("problem_highlight_color", "Yellow")
    assert events.get("problem_highlight_color") == "Yellow"

    win._notify_live("large_reviewed_btn", True)
    assert events.get("large_reviewed_btn") is True

    win._notify_live("snap_lock", True)
    assert events.get("snap_lock") is True

    win._notify_live("location_2row", True)
    assert events.get("location_2row") is True

    win._notify_live("image_stack", True)
    assert events.get("image_stack") is True
    win.win.destroy()


def test_unified_settings_push_layout_to_app(tk_root):
    class MockApp:
        def __init__(self):
            self.show_list_var = tk.BooleanVar(value=True)
            self.show_search_var = tk.BooleanVar(value=True)
            self.show_reg_var = tk.BooleanVar(value=True)
            self.show_images_var = tk.BooleanVar(value=True)
            self.location_in_center_var = tk.BooleanVar(value=False)
            self.show_image_tools_var = tk.BooleanVar(value=True)
            self.show_bulk_edit_var = tk.BooleanVar(value=True)
            self.image_stack_var = tk.BooleanVar(value=False)
            self.large_reviewed_button_var = tk.BooleanVar(value=False)
            self.snap_lock_var = tk.BooleanVar(value=False)
            self.auto_advance_var = tk.BooleanVar(value=True)
            self.auto_advance_history_var = tk.BooleanVar(value=False)
            self.image_view_mode = "gallery"
            self.updated_reviewed_btn = False
            self.updated_image_view = False
            self.location_mode_set = None
            self.location_panel_horiz = type("LocPanel", (), {
                "set_layout_mode": lambda s, m: setattr(self, "location_mode_set", m)
            })()

        def update_reviewed_button_state(self):
            self.updated_reviewed_btn = True

        def update_image_view_button(self):
            pass

        def refresh_image_view(self):
            self.updated_image_view = True

    mock_app = MockApp()
    win = UnifiedSettingsWindow(tk_root, app_ref=mock_app, initial_tab="layout")
    win.var_large_reviewed_btn.set(True)
    win.var_snap_lock.set(True)
    win.var_location_2row.set(True)
    win.var_image_stack.set(True)
    win.var_auto_advance.set(False)
    win.var_auto_advance_history.set(True)

    win._push_layout_to_app()

    assert mock_app.large_reviewed_button_var.get() is True
    assert mock_app.snap_lock_var.get() is True
    assert mock_app.image_stack_var.get() is True
    assert mock_app.image_view_mode == "stack"
    assert mock_app.auto_advance_var.get() is False
    assert mock_app.auto_advance_history_var.get() is True
    win.win.destroy()


def test_unified_settings_reset_tutorials_action(tk_root, tmp_path, monkeypatch):
    from tkinter import messagebox
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)

    test_prefs_file = str(tmp_path / "user_prefs.json")
    monkeypatch.setattr(config, "_PREFS_PATH", test_prefs_file)
    monkeypatch.setattr(config, "_prefs_cache", None)

    p = {"completed_tutorials": ["step1", "step2"]}
    config.save_prefs(p)

    win = UnifiedSettingsWindow(tk_root, initial_tab="tools")
    win._execute_action("reset_tutorials")

    loaded = config.load_prefs()
    assert loaded.get("completed_tutorials") == []
    win.win.destroy()


def test_image_url_pattern_resolution_advanced(tk_root):
    from ui.image_handler import ImageHandlerMixin

    class DummyUI(ImageHandlerMixin):
        def __init__(self):
            self.app = type("App", (), {"config": {}})()

    handler = DummyUI()

    # Pattern with {id} and {suffix}
    handler.app.config["image_url_pattern"] = "https://example.com/photos/{id}{suffix}.png"
    urls = handler.build_online_image_urls("ABC-123")
    assert urls[0] == "https://example.com/photos/ABC-123.png"
    assert urls[1] == "https://example.com/photos/ABC-123-01.png"

    # Pattern with {num:04d} without {suffix}
    handler.app.config["image_url_pattern"] = "https://example.com/photos/IMG_{num:04d}.jpg"
    urls = handler.build_online_image_urls("7")
    assert urls[0] == "https://example.com/photos/IMG_0007.jpg"
    assert urls[1] == "https://example.com/photos/IMG_0007-01.jpg"


def test_toolbar_buttons_live_callback_and_persistence(tk_root, tmp_path, monkeypatch):
    test_prefs_file = str(tmp_path / "user_prefs.json")
    monkeypatch.setattr(config, "_PREFS_PATH", test_prefs_file)
    monkeypatch.setattr(config, "_prefs_cache", None)

    class MockApp:
        def __init__(self):
            self.toolbar_vars = {"Zoom": tk.BooleanVar(value=True), "Filter": tk.BooleanVar(value=False)}
            self.toggled_tb_called = False

        def _toggle_toolbar_buttons(self):
            self.toggled_tb_called = True

    mock_app = MockApp()
    win = UnifiedSettingsWindow(tk_root, app_ref=mock_app, initial_tab="layout")
    assert "Zoom" in win.draft_toolbar_vars
    assert "Filter" in win.draft_toolbar_vars

    # Modify draft vars
    win.draft_toolbar_vars["Filter"].set(True)
    win._push_layout_to_app()
    assert mock_app.toolbar_vars["Filter"].get() is True

    win.save_settings()
    loaded = config.load_prefs()
    assert "toolbar_buttons" in loaded
    assert loaded["toolbar_buttons"]["Filter"] is True


def test_secondary_nav_toggle_and_persistence(tk_root, tmp_path, monkeypatch):
    test_prefs_file = str(tmp_path / "user_prefs.json")
    monkeypatch.setattr(config, "_PREFS_PATH", test_prefs_file)
    monkeypatch.setattr(config, "_prefs_cache", None)

    class MockApp:
        def __init__(self):
            self.show_secondary_nav_var = tk.BooleanVar(value=False)
            self.applied_visibility = None

        def apply_secondary_nav_visibility(self, val):
            self.applied_visibility = val

    mock_app = MockApp()
    win = UnifiedSettingsWindow(tk_root, app_ref=mock_app, initial_tab="layout")
    assert win.var_show_secondary_nav.get() is False

    # Toggle to True
    win.var_show_secondary_nav.set(True)
    win._push_layout_to_app()
    assert mock_app.show_secondary_nav_var.get() is True
    assert mock_app.applied_visibility is True

    win.save_settings()
    loaded = config.load_prefs()
    assert loaded.get("show_secondary_nav") is True


def test_focus_section_visibility_synchronization(tk_root, tmp_path, monkeypatch):
    test_prefs_file = str(tmp_path / "user_prefs.json")
    monkeypatch.setattr(config, "_PREFS_PATH", test_prefs_file)
    monkeypatch.setattr(config, "_prefs_cache", None)

    class MockApp:
        def __init__(self):
            self.focus_mode_var = tk.BooleanVar(value=False)
            self.focus_fallback_var = tk.BooleanVar(value=True)
            self.focus_dynamic_update_var = tk.BooleanVar(value=False)
            self.focus_visibility_vars = {
                "Problems": tk.BooleanVar(value=True),
                "Location": tk.BooleanVar(value=True),
                "Genus": tk.BooleanVar(value=True)
            }
            self.reg_visibility_updated = False

        def update_reg_fields_visibility(self):
            self.reg_visibility_updated = True

    mock_app = MockApp()
    win = UnifiedSettingsWindow(tk_root, app_ref=mock_app, initial_tab="focus")
    assert win.var_focus_sec_problems.get() is True
    assert win.var_focus_sec_location.get() is True

    win.var_focus_mode.set(True)
    win.var_focus_sec_problems.set(False)
    win.var_focus_sec_location.set(False)
    win.draft_focus_visibility_vars["Genus"].set(False)

    win._push_layout_to_app()
    assert mock_app.focus_mode_var.get() is True
    assert mock_app.focus_visibility_vars["Problems"].get() is False
    assert mock_app.focus_visibility_vars["Location"].get() is False
    assert mock_app.focus_visibility_vars["Genus"].get() is False

    win.save_settings()
    loaded = config.load_prefs()
    assert loaded["focus_visibility"]["Problems"] is False
    assert loaded["focus_visibility"]["Location"] is False
    assert loaded["focus_visibility"]["Genus"] is False
    assert loaded["focus_mode"] is True


def test_bidirectional_settings_initialization_from_live_app(tk_root, tmp_path, monkeypatch):
    test_prefs_file = str(tmp_path / "user_prefs.json")
    monkeypatch.setattr(config, "_PREFS_PATH", test_prefs_file)
    monkeypatch.setattr(config, "_prefs_cache", None)

    # Initial preferences saved on disk (all defaults/light)
    config.save_prefs({"dark_mode": False, "show_list": True})

    # Main app modified dynamically in active session
    class LiveApp:
        def __init__(self):
            self.dark_mode_active = True
            self.show_list_var = tk.BooleanVar(value=False)
            self.show_search_var = tk.BooleanVar(value=False)
            self.show_reg_var = tk.BooleanVar(value=True)
            self.show_images_var = tk.BooleanVar(value=False)
            self.location_in_center_var = tk.BooleanVar(value=True)
            self.show_image_tools_var = tk.BooleanVar(value=False)
            self.show_bulk_edit_var = tk.BooleanVar(value=False)
            self.image_stack_var = tk.BooleanVar(value=True)
            self.large_reviewed_button_var = tk.BooleanVar(value=False)
            self.snap_lock_var = tk.BooleanVar(value=True)
            self.auto_advance_var = tk.BooleanVar(value=False)
            self.auto_advance_history_var = tk.BooleanVar(value=True)
            self.focus_mode_var = tk.BooleanVar(value=True)
            self.focus_fallback_var = tk.BooleanVar(value=False)
            self.focus_dynamic_update_var = tk.BooleanVar(value=True)
            self.focus_visibility_vars = {}
            self.toolbar_vars = {"Save": tk.BooleanVar(value=False)}

    app = LiveApp()
    win = UnifiedSettingsWindow(tk_root, app_ref=app, initial_tab="general")

    # Verify dialog loaded from live app rather than stale disk prefs
    assert win.var_dark_mode.get() is True
    assert win.var_show_list.get() is False
    assert win.var_show_search.get() is False
    assert win.var_show_images.get() is False
    assert win.var_location_center.get() is True
    assert win.var_show_image_tools.get() is False
    assert win.var_show_bulk_edit.get() is False
    assert win.var_image_stack.get() is True
    assert win.var_large_reviewed_btn.get() is False
    assert win.var_snap_lock.get() is True
    assert win.var_auto_advance.get() is False
    assert win.var_auto_advance_history.get() is True
    assert win.var_focus_mode.get() is True
    assert win.var_focus_fallback.get() is False
    assert win.var_focus_dynamic.get() is True
    assert win.draft_toolbar_vars["Save"].get() is False
    win.win.destroy()


def test_layout_preset_full_serialization(tk_root, tmp_path, monkeypatch):
    from tkinter import messagebox
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)

    test_prefs_file = str(tmp_path / "user_prefs.json")
    monkeypatch.setattr(config, "_PREFS_PATH", test_prefs_file)
    monkeypatch.setattr(config, "_prefs_cache", None)

    win = UnifiedSettingsWindow(tk_root, initial_tab="presets")
    win.var_show_list.set(False)
    win.var_location_center.set(True)
    win.var_location_2row.set(True)
    win.var_image_stack.set(True)
    win.draft_toolbar_vars = {"Export": tk.BooleanVar(value=False)}

    # Save custom layout preset
    p = config.load_prefs() or {}
    p.setdefault("layouts", {}).setdefault("saved", {})["CustomPro"] = {
        "show_list": win.var_show_list.get(),
        "show_search": win.var_show_search.get(),
        "show_reg": win.var_show_reg.get(),
        "show_images": win.var_show_images.get(),
        "location_in_center": win.var_location_center.get(),
        "location_2row": win.var_location_2row.get(),
        "show_image_tools": win.var_show_image_tools.get(),
        "show_bulk_edit": win.var_show_bulk_edit.get(),
        "image_stack": win.var_image_stack.get(),
        "large_reviewed_button": win.var_large_reviewed_btn.get(),
        "snap_lock": win.var_snap_lock.get(),
        "focus_problems": win.var_focus_mode.get(),
        "toolbar_buttons": {k: v.get() for k, v in win.draft_toolbar_vars.items()},
    }
    config.save_prefs(p)

    loaded = config.load_prefs()
    preset = loaded["layouts"]["saved"]["CustomPro"]
    assert preset["show_list"] is False
    assert preset["location_in_center"] is True
    assert preset["location_2row"] is True
    assert preset["image_stack"] is True
    assert preset["toolbar_buttons"]["Export"] is False
    win.win.destroy()


def test_auto_advance_independence(tk_root, tmp_path, monkeypatch):
    test_prefs_file = str(tmp_path / "user_prefs.json")
    monkeypatch.setattr(config, "_PREFS_PATH", test_prefs_file)
    monkeypatch.setattr(config, "_prefs_cache", None)

    # Test independence of auto_advance traces on a minimal app mock
    class MinimalApp:
        def __init__(self):
            self.auto_advance_var = tk.BooleanVar(value=False)
            self.auto_advance_history_var = tk.BooleanVar(value=False)

            def _on_auto_advance_changed(*args):
                p = config.load_prefs() or {}
                p["auto_advance_on_review"] = self.auto_advance_var.get()
                config.save_prefs(p)

            def _on_auto_advance_history_changed(*args):
                p = config.load_prefs() or {}
                p["auto_advance_history"] = self.auto_advance_history_var.get()
                config.save_prefs(p)

            self.auto_advance_var.trace_add("write", _on_auto_advance_changed)
            self.auto_advance_history_var.trace_add("write", _on_auto_advance_history_changed)

    app = MinimalApp()
    app.auto_advance_var.set(True)
    app.auto_advance_history_var.set(True)

    assert app.auto_advance_var.get() is True
    assert app.auto_advance_history_var.get() is True

    p = config.load_prefs()
    assert p["auto_advance_on_review"] is True
    assert p["auto_advance_history"] is True


def test_auto_resolve_conflicts_in_historical_resolver(tk_root, tmp_path, monkeypatch):
    test_prefs_file = str(tmp_path / "user_prefs.json")
    monkeypatch.setattr(config, "_PREFS_PATH", test_prefs_file)
    monkeypatch.setattr(config, "_prefs_cache", None)

    p = config.load_prefs() or {}
    p["auto_resolve_conflicts"] = True
    config.save_prefs(p)

    import pandas as pd
    from ui.object_problem_resolver import ObjectProblemResolver as HistoricalConflictResolverWindow

    class MockHistoricalApp:
        def __init__(self):
            self.root = tk_root
            self.auto_resolve_conflicts_var = tk.BooleanVar(value=True)
            self.auto_advance_history_var = tk.BooleanVar(value=False)
            self.problem_vars = {}
            self.problem_to_field = {}
            self.reg_vars = {}
            self.loaded_problem_states = {}
            self.reg_by_id = pd.DataFrame([{"Genus": ""}], index=["101"])
            self.app = type("AppObj", (), {
                "df_reg": pd.DataFrame([{"Genus": ""}], index=["101"]),
                "df_obs": pd.DataFrame([{"Prob": False}], index=["101"])
            })()

        def is_unknown(self, val):
            return val in ("", "nan", "UNKNOWN", "?")

        def update_dirty_ui(self):
            pass

        def log_action(self, *args, **kwargs):
            pass

    mock_app = MockHistoricalApp()
    suggestions = {
        "Genus": {"Pinus": {"Book1.xlsx"}}
    }

    resolver = HistoricalConflictResolverWindow(mock_app, "101", suggestions)
    # Since auto_resolve_conflicts is True and there is a single suggestion for an empty field,
    # res_vars["Genus"] should be pre-populated with "Pinus"
    assert resolver.res_vars["Genus"].get() == "Pinus"
    resolver.win.destroy()


def test_info_button_widget_interactions(tk_root):
    from ui.widgets import InfoButton, create_info_badge

    frame = tk.Frame(tk_root)
    frame.pack()

    info_btn = InfoButton(frame, text="Sample tooltip info text", icon="ⓘ")
    assert info_btn.get_text() == "Sample tooltip info text"

    # Test set_text
    info_btn.set_text("Updated explanation")
    assert info_btn.get_text() == "Updated explanation"

    # Test hover enter -> creates tip window
    assert info_btn.tip_window is None
    info_btn._on_enter()
    assert info_btn.tip_window is not None
    assert info_btn.tip_window.winfo_exists()

    # Test hover leave -> destroys tip window
    info_btn._on_leave()
    assert info_btn.tip_window is None

    # Test click toggle
    info_btn._on_click()
    assert info_btn.tip_window is not None
    info_btn._on_click()
    assert info_btn.tip_window is None

    # Test focus events
    info_btn._on_focus_in()
    assert info_btn.tip_window is not None
    info_btn._on_focus_out()
    assert info_btn.tip_window is None

    # Test factory helper
    badge = create_info_badge(frame, "Helper text")
    assert isinstance(badge, InfoButton)
    assert badge.get_text() == "Helper text"

    # Test dark mode detection
    class MockAppDark:
        dark_mode_active = True

    dark_btn = InfoButton(frame, text="Dark mode test", ui_ref=MockAppDark())
    assert dark_btn.is_dark_mode() is True
    dark_btn._on_enter()
    assert dark_btn.tip_window is not None
    dark_btn.destroy()

    frame.destroy()


def test_create_toggle_row_with_info_text(tk_root):
    from ui.widgets import create_toggle_row, InfoButton

    frame = tk.Frame(tk_root)
    frame.pack()
    var = tk.BooleanVar(value=True)

    row = create_toggle_row(frame, "Setting with Info", var, info_text="Detailed info here")
    info_buttons = [w for w in row.winfo_children() if isinstance(w, InfoButton)]
    assert len(info_buttons) == 1
    assert info_buttons[0].get_text() == "Detailed info here"

    frame.destroy()


def test_unified_settings_all_10_target_info_buttons(tk_root):
    from ui.unified_settings import UnifiedSettingsWindow, SETTING_INFO_TEXTS
    from ui.widgets import InfoButton

    expected_keys = [
        "focus_fallback",
        "focus_dynamic_update",
        "snap_lock",
        "image_url_pattern_override",
        "image_resampling_algorithm",
        "auto_advance_history",
        "autosave_archive_limit",
        "enable_excel_import_backup",
        "strict_input_validation",
    ]

    for k in expected_keys:
        assert k in SETTING_INFO_TEXTS
        assert len(SETTING_INFO_TEXTS[k]) > 10

    win = UnifiedSettingsWindow(tk_root, initial_tab="general")

    def _find_all_info_buttons(widget):
        btns = []
        for child in widget.winfo_children():
            if isinstance(child, InfoButton):
                btns.append(child)
            btns.extend(_find_all_info_buttons(child))
        return btns

    all_buttons = _find_all_info_buttons(win.win)
    all_texts = [b.get_text() for b in all_buttons]

    for k in expected_keys:
        expected_text = SETTING_INFO_TEXTS[k]
        assert expected_text in all_texts, f"Expected info text for '{k}' not found in rendered InfoButtons"

    win.win.destroy()





def test_ignored_words_embedded_in_tools_tab(tk_root):
    """Verify that ignored words dictionary is embedded in Unified Settings Tools tab."""
    class MockAppForIgnored:
        def __init__(self):
            self.ignored_words = ["cf.", "aff."]
            self.ignored_words_variations = tk.BooleanVar(value=True)
            self.saved = False

        def save_ignored_words(self):
            self.saved = True

    app = MockAppForIgnored()
    win = UnifiedSettingsWindow(tk_root, app_ref=app, initial_tab="tools")

    assert hasattr(win, "text_ignored_words")
    assert win.text_ignored_words.winfo_exists()
    current_text = win.text_ignored_words.get("1.0", "end").strip()
    assert "cf." in current_text
    assert "aff." in current_text

    # Edit words in text area
    win.text_ignored_words.delete("1.0", "end")
    win.text_ignored_words.insert("1.0", "var.\nsubsp.\nforma")
    win.var_ignored_variations.set(False)

    win.save_settings()

    assert app.saved is True
    assert app.ignored_words == ["var.", "subsp.", "forma"]
    assert app.ignored_words_variations.get() is False

    win.win.destroy()


def test_card_view_preview_and_profile_switching(tk_root):
    """Verify live card preview updates correctly when profiles and settings are modified."""
    win = UnifiedSettingsWindow(tk_root, initial_tab="appearance")

    # Assert preview widgets exist
    assert hasattr(win, "_preview_widgets")
    assert "tax_lbl" in win._preview_widgets
    assert "badge_lbl" in win._preview_widgets
    assert "loc_lbl" in win._preview_widgets

    # Default profile is standard
    assert "Quercus robur" in win._preview_widgets["tax_lbl"].cget("text")
    assert win._preview_widgets["badge_lbl"].cget("text") == "[ TAX ]"

    # Switch to compact profile
    win._apply_card_preset_in_settings("compact")
    assert win.var_card_density.get() == "compact"
    assert win.var_card_show_loc.get() is False
    assert win._preview_widgets["row3"].winfo_manager() != "pack"

    # Switch to full_detail profile
    win._apply_card_preset_in_settings("full_detail")
    assert win.var_card_density.get() == "expanded"
    assert win.var_card_show_author.get() is True
    assert "L." in win._preview_widgets["tax_lbl"].cget("text")
    assert win._preview_widgets["row3"].winfo_manager() == "pack"

    # Switch to minimalist profile
    win._apply_card_preset_in_settings("minimalist")
    assert win.var_card_show_badge.get() is False
    assert win._preview_widgets["badge_lbl"].cget("text") == ""
    assert win._preview_widgets["row3"].winfo_manager() != "pack"

    # Test sample record status switcher
    win._apply_card_preset_in_settings("standard")
    win.var_preview_status.set("reviewed")
    win._refresh_live_preview()
    assert win._preview_widgets["badge_lbl"].cget("text") == "[ REV ]"
    assert win._preview_widgets["cb_lbl"].cget("text") == "[☑]"
    assert "Fraxinus excelsior" in win._preview_widgets["tax_lbl"].cget("text")

    # Test persona alias routing in settings
    win._apply_card_persona_in_settings("taxonomist")
    assert win.var_card_density.get() == "expanded"
    assert win.var_card_show_author.get() is True
    assert win._preview_widgets["row3"].winfo_manager() == "pack"

    win._apply_card_persona_in_settings("collections_manager")
    assert win.var_card_show_badge.get() is False
    assert win._preview_widgets["badge_lbl"].cget("text") == ""

    win._apply_card_persona_in_settings("high_speed")
    assert win.var_card_density.get() == "compact"
    assert win.var_card_show_loc.get() is False

    win.win.destroy()


def test_directory_view_strip_setting_toggle_and_reset(tk_root):
    """Verify Directory View Strip toggle in Settings tab, persistence, and reset."""
    import config
    from ui.unified_settings import SETTING_INFO_TEXTS

    config.reset_directory_card_prefs_to_default()
    assert config.get_directory_card_prefs()["show_directory_view_strip"] is False

    win = UnifiedSettingsWindow(tk_root, initial_tab="appearance")

    # Assert setting info text exists
    assert "directory_view_strip" in SETTING_INFO_TEXTS
    assert "compact toolbar directly above the specimen directory" in SETTING_INFO_TEXTS["directory_view_strip"]

    # Assert default state of variable is False
    assert win.var_card_show_view_strip.get() is False

    # Toggle to True and sync live
    win.var_card_show_view_strip.set(True)
    win._sync_card_settings_live()
    assert config.get_directory_card_prefs()["show_directory_view_strip"] is True

    # Reset to default in UI
    win._reset_card_settings_to_default_ui()
    assert win.var_card_show_view_strip.get() is False
    assert config.get_directory_card_prefs()["show_directory_view_strip"] is False

    win.win.destroy()


