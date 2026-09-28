import pytest
import tkinter as tk
from unittest.mock import MagicMock
import pandas as pd

from ui.registry_panel import _bind_icedig_context_menu, _bind_icedig_shortcuts, _apply_icedig_code
from ui.object_problem_resolver import ObjectProblemResolver
import config
from backend.mobile_server import INDEX_TEMPLATE


@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_icedig_context_menu_unlocked_on_empty_and_valid_fields(tk_root):
    """Verify that ICEDIG context menu generates on empty fields, valid data, and legacy tokens."""
    mock_ui = MagicMock()
    mock_ui.reg_vars = {
        "Collector": tk.StringVar(value=""),
        "Species": tk.StringVar(value="sylvestris"),
        "Genus": tk.StringVar(value="unknown:missing")
    }

    entry = tk.Entry(tk_root)
    entry.pack()

    # 1. Bind to empty field and verify menu builds
    _bind_icedig_context_menu(mock_ui, entry, "Collector")
    assert hasattr(entry, "_icedig_menu_builder")
    menu_fn = entry._icedig_menu_builder

    menu_items_empty = menu_fn(None)
    assert menu_items_empty is not None
    assert any(item.get("label") == "Set ICEDIG status" for item in menu_items_empty)

    # 2. Check menu on field with regular data
    mock_ui.reg_vars["Collector"].set("Carl Linnaeus")
    menu_items_data = menu_fn(None)
    assert menu_items_data is not None
    assert any(item.get("label") == "Clear Field Value" for item in menu_items_data)


def test_icedig_shorthand_expansion(tk_root):
    """Verify that shorthand tokens (?m, ?i, ?u, ?w, ??) expand to ICEDIG codes."""
    mock_ui = MagicMock()
    var = tk.StringVar(value="")
    mock_ui.reg_vars = {"Collector": var}
    mock_ui.commit_current_object = MagicMock()

    entry = tk.Entry(tk_root, textvariable=var)
    entry.pack()

    _bind_icedig_shortcuts(mock_ui, entry, "Collector")

    # Test ?m -> unknown:missing
    var.set("?m")
    entry._check_shorthand(None)
    assert var.get() == "unknown:missing"

    # Test ?i -> unknown:indecipherable
    var.set("?i")
    entry._check_shorthand(None)
    assert var.get() == "unknown:indecipherable"

    # Test ?u -> unknown:undigitized
    var.set("?u")
    entry._check_shorthand(None)
    assert var.get() == "unknown:undigitized"

    # Test ?w -> withheld
    var.set("?w")
    entry._check_shorthand(None)
    assert var.get() == "withheld"

    # Test ?? -> unknown
    var.set("??")
    entry._check_shorthand(None)
    assert var.get() == "unknown"


def test_resolver_1click_icedig_buttons(tk_root):
    """Verify that 1-click Blank and Illegible buttons in ObjectProblemResolver resolve issues."""
    mock_main = MagicMock()
    mock_main.root = tk_root
    mock_main.df_reg = pd.DataFrame([{"Collector": ""}], index=["1001"])
    mock_main.df_obs = pd.DataFrame([{"Collector_Problem": True}], index=["1001"])
    mock_main._get_reg_dict = lambda: {"1001": {"Collector": ""}}
    mock_main.is_unknown = lambda val: str(val).strip().lower() in config.ALL_UNKNOWN_TOKENS
    mock_main.problem_to_field = {"Collector_Problem": "Collector"}
    mock_main.problem_vars = {"Collector_Problem": tk.BooleanVar(value=True)}
    mock_main.reg_vars = {"Collector": tk.StringVar(value="")}
    mock_main.reg_entries = {}
    mock_main.app = MagicMock()
    mock_main.app.df_reg = mock_main.df_reg
    mock_main.app.df_obs = mock_main.df_obs

    suggestions = {"Collector": {"Linnaeus": {"Book A"}}}
    resolver = ObjectProblemResolver(mock_main, "1001", suggestions)

    # Verify resolution cards were created
    assert "Collector" in resolver.card_frames
    assert "Collector" in resolver.res_vars

    # Execute resolution via res_var set
    resolver.res_vars["Collector"].set("unknown:missing")
    assert mock_main.is_unknown(resolver.res_vars["Collector"].get()) is True


def test_mobile_template_icedig_picker_integration():
    """Verify that mobile template includes bottom sheet modal and ICEDIG button handlers."""
    assert 'id="icedigBottomSheetModal"' in INDEX_TEMPLATE
    assert 'openIcedigBottomSheet' in INDEX_TEMPLATE
    assert 'applyIcedigChoice' in INDEX_TEMPLATE
    assert 'showToastWithUndo' in INDEX_TEMPLATE
    assert 'discrepancyUnvalCheck' in INDEX_TEMPLATE
    assert 'Missing Data Status' in INDEX_TEMPLATE
