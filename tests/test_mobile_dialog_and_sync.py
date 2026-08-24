"""
tests/test_mobile_dialog_and_sync.py

Comprehensive unit and integration tests for the desktop Mobile Companion Dialog
and real-time event synchronization (ui/mobile_dialog.py & ui/main_window.py).
"""

import os
import tkinter as tk
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from models import AppState
from repository import REVIEWED_COLUMN, REVIEWED_AT_COLUMN
from backend.mobile_server import MobileServerManager
from backend.tunnel import SSHTunnelManager
from ui.mobile_dialog import MobileCompanionDialog


@pytest.fixture
def tk_root():
    """Creates a headless Tk root window for UI tests."""
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def mock_main_ui(tk_root):
    """Creates a mock ObjectProgramUI object with necessary state attributes."""
    ui = MagicMock()
    ui.root = tk_root
    app = AppState()
    app.config = {"has_images": False}
    app.config_name = "Botanical Test Herbarium"
    app.current_object_id = "1001"
    app.df_reg = pd.DataFrame([
        {"ObjectID": "1001", "Genus": "Quercus", "Species": "robur"},
        {"ObjectID": "1002", "Genus": "Pinus", "Species": "sylvestris"}
    ]).set_index("ObjectID")
    app.df_obs = pd.DataFrame([
        {"ObjectID": "1001", REVIEWED_COLUMN: False, "Notes": ""},
        {"ObjectID": "1002", REVIEWED_COLUMN: False, "Notes": ""}
    ]).set_index("ObjectID")
    app.df_photo = pd.DataFrame()
    app.df_log = pd.DataFrame()
    app.undo_stacks = {}
    app.dirty = False

    ui.app = app
    ui.mobile_server_mgr = MobileServerManager(app, root_tk=tk_root)
    ui.mobile_tunnel_mgr = SSHTunnelManager(local_port=ui.mobile_server_mgr.port, session_token=ui.mobile_server_mgr.session_token)
    ui._mobile_dialog = None
    ui._cached_obs_dict = {
        "1001": {"Reviewed": False, "Notes": ""},
        "1002": {"Reviewed": False, "Notes": ""}
    }
    ui._cached_reviewed_dict = {"1001": False, "1002": False}
    ui.reviewed_var = tk.BooleanVar(value=False)
    ui.obs_entry_dict = {"Notes": tk.StringVar(value="")}
    return ui


def test_mobile_dialog_creation_and_teardown(mock_main_ui):
    dialog = MobileCompanionDialog(mock_main_ui, mock_main_ui.app)
    assert dialog.win.winfo_exists()
    assert dialog.server_mgr.is_running is True
    assert dialog.tunnel_mgr.status in ("starting", "connected", "stopped", "reconnecting")
    assert dialog._qr_image_tk is not None

    # Test activity logging
    dialog.log_activity("Test log line 1")
    log_content = dialog.log_text.get("1.0", "end")
    assert "Test log line 1" in log_content

    # Test dialog close (does not stop server daemon)
    dialog.on_close()
    assert not dialog.win.winfo_exists()
    assert dialog.server_mgr.is_running is True

    dialog.server_mgr.stop()
    dialog.tunnel_mgr.stop()


def test_on_mobile_edit_received_queue_draining(mock_main_ui):
    # Import the actual handler from ObjectProgramUI
    from ui.main_window import ObjectProgramUI

    # Enqueue a mock mobile edit for object 1001
    mock_main_ui.mobile_server_mgr.event_queue.put({
        "type": "update",
        "oid": "1001",
        "reviewed": True,
        "observation": {"Notes": "Verified in collection tray 4"},
        "timestamp": "12:00:00"
    })

    assert mock_main_ui.app.dirty is False
    assert mock_main_ui._cached_obs_dict["1001"]["Reviewed"] is False

    # Execute _on_mobile_edit_received
    ObjectProgramUI._on_mobile_edit_received(mock_main_ui)

    # Verify state updates
    assert mock_main_ui.app.dirty is True
    assert mock_main_ui._cached_obs_dict["1001"]["Reviewed"] is True
    assert mock_main_ui._cached_obs_dict["1001"]["Notes"] == "Verified in collection tray 4"
    assert mock_main_ui.reviewed_var.get() is True
    assert mock_main_ui.obs_entry_dict["Notes"].get() == "Verified in collection tray 4"


def test_teardown_in_on_close(mock_main_ui):
    from ui.main_window import ObjectProgramUI

    mock_main_ui.mobile_server_mgr.start()
    assert mock_main_ui.mobile_server_mgr.is_running is True

    # Call on_close teardown
    with patch.object(mock_main_ui.root, "destroy"):
        ObjectProgramUI.on_close(mock_main_ui)

    assert mock_main_ui.mobile_server_mgr.is_running is False
