import pytest
from datetime import datetime, timedelta
import pandas as pd
from backend.mobile_server import MobileServer
from models import AppState

@pytest.fixture
def mock_app_state():
    app = AppState()
    app.config = {
        "ui_sections": {
            "registration": [{"name": "Genus"}, {"name": "Species"}],
            "location": [{"name": "Cabinet"}],
            "problems": [{"name": "MissingLabel"}]
        }
    }
    app.df_reg = pd.DataFrame({
        "Genus": ["Pinus", "Betula"],
        "Species": ["sylvestris", "pendula"],
        "Cabinet": ["Cab 1", "Cab 2"]
    }, index=pd.Index([1001, 1002], name="ObjectID"))

    app.df_obs = pd.DataFrame({
        "Reviewed": [True, False],
        "Cabinet": ["Cab 1", "Cab 2"]
    }, index=pd.Index([1001, 1002], name="ObjectID"))

    # Pre-populate undo stack with a recent change for 1001
    now = datetime.now()
    app.undo_stacks = {
        "1001": [
            {
                "oid": "1001",
                "timestamp": now.isoformat()
            }
        ]
    }
    return app

def test_offline_mutation_queue_batch_update_success(mock_app_state):
    server = MobileServer(mock_app_state, port=5099)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    now = datetime.now()
    # A valid queued update (newer than any stack changes, or for an object without stack)
    future_time = (now + timedelta(minutes=5)).isoformat()

    payload = {
        "updates": [
            {
                "id": "1002",
                "reviewed": True,
                "timestamp": future_time,
                "observation": {"Cabinet": "Cab 88"}
            }
        ]
    }

    res = client.post('/api/batch_update', headers=headers, json=payload)
    assert res.status_code == 200
    assert res.json["updated_count"] == 1
    assert mock_app_state.df_obs.at[1002, "Cabinet"] == "Cab 88"

def test_offline_mutation_queue_conflict_rejection(mock_app_state):
    server = MobileServer(mock_app_state, port=5098)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    now = datetime.now()
    # An older queued update for 1001 (older than the stack change)
    past_time = (now - timedelta(minutes=5)).isoformat()

    payload = {
        "updates": [
            {
                "id": "1001",
                "reviewed": False,
                "timestamp": past_time,
                "observation": {"Cabinet": "Cab 99"} # Should be rejected
            }
        ]
    }

    res = client.post('/api/batch_update', headers=headers, json=payload)
    assert res.status_code == 200
    assert res.json.get("updated_count") == 0
    # Data should not be changed
    assert mock_app_state.df_obs.at[1001, "Cabinet"] == "Cab 1"


def test_v2_offline_indexeddb_mutation_queue_and_presence_parity(mock_app_state):
    """Test that V2 template includes IndexedDB offline queue methods and server triggers presence callback."""
    observed_presence = []
    server = MobileServer(mock_app_state, port=5097)
    server.on_presence_callback = lambda oid: observed_presence.append(oid)

    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    # 1. Test presence callback triggering on /api/presence
    p_res = client.post('/api/presence', headers=headers, json={"oid": "1002"})
    assert p_res.status_code == 200
    assert "1002" in observed_presence

    # 2. Test V2 template contains IndexedDB queue routines
    v2_res = client.get('/v2?token=' + server.session_token)
    assert v2_res.status_code == 200
    html = v2_res.get_data(as_text=True)

    assert 'initIndexedDB()' in html
    assert 'queued_mutations' in html
    assert 'queueMutation(payload)' in html
    assert 'flushQueuedMutations()' in html
    assert 'forceSaveImmediate()' in html
    assert 'id="offlineBannerText"' in html


def test_v2_settings_icedig_reference_table(mock_app_state):
    """Test that V2 settings modal contains ICEDIG reference table."""
    server = MobileServer(mock_app_state, port=5096)
    client = server.flask_app.test_client()
    v2_res = client.get('/v2?token=' + server.session_token)
    assert v2_res.status_code == 200
    html = v2_res.get_data(as_text=True)

    assert 'ICEDIG Missing Data Standards' in html
    assert 'unknown:missing' in html
    assert 'unknown:indecipherable' in html
    assert 'unknown:undigitized' in html
    assert 'withheld' in html


def test_v2_accidental_unload_and_pagehide_guards(mock_app_state):
    """Test that V2 template includes beforeunload, pagehide, and visibilitychange guards."""
    server = MobileServer(mock_app_state, port=5097)
    client = server.flask_app.test_client()
    v2_res = client.get('/v2?token=' + server.session_token)
    assert v2_res.status_code == 200
    html = v2_res.get_data(as_text=True)

    assert "window.addEventListener('beforeunload'" in html
    assert "window.addEventListener('pagehide'" in html
    assert "document.addEventListener('visibilitychange'" in html
    assert "forceSaveImmediate()" in html


def test_v2_adjustable_tactile_haptic_feedback(mock_app_state):
    """Test that V2 and V1 settings modal contain adjustable haptic feedback controls."""
    server = MobileServer(mock_app_state, port=5098)
    client = server.flask_app.test_client()
    
    # Check V2
    v2_res = client.get('/v2?token=' + server.session_token)
    assert v2_res.status_code == 200
    html_v2 = v2_res.get_data(as_text=True)

    assert 'id="settingEnableHaptics"' in html_v2
    assert 'id="btnHapticLight"' in html_v2
    assert 'id="btnHapticMedium"' in html_v2
    assert 'id="btnHapticStrong"' in html_v2
    assert 'testHapticFeedback()' in html_v2
    assert 'id="hapticsUnsupportedNote"' in html_v2
    assert 'HAPTIC_PROFILES' in html_v2
    assert 'triggerHaptic(' in html_v2

    # Check V1 Parity
    v1_res = client.get('/?token=' + server.session_token)
    assert v1_res.status_code == 200
    html_v1 = v1_res.get_data(as_text=True)

    assert 'id="settingEnableHaptics"' in html_v1
    assert 'id="btnHapticLight"' in html_v1
    assert 'id="btnHapticMedium"' in html_v1
    assert 'id="btnHapticStrong"' in html_v1
    assert 'testHapticFeedback()' in html_v1
    assert 'id="hapticsUnsupportedNote"' in html_v1


def test_mobile_autosave_setting_and_panel_toggle(mock_app_state, monkeypatch):
    """Test mobile_autosave_on_stop preference and MobilePanel toggle behavior."""
    import config
    from ui.mobile_panel import MobilePanel
    import tkinter as tk

    fake_prefs = {"mobile_autosave_on_stop": False}
    monkeypatch.setattr(config, "load_prefs", lambda: fake_prefs)
    monkeypatch.setattr(config, "save_prefs", lambda p: fake_prefs.update(p))

    root = tk.Tk()
    try:
        panel = MobilePanel(
            parent=root,
            app_state=mock_app_state,
            root_tk=root,
            port=5099
        )
        assert panel.auto_save_var.get() is False
        assert "OFF" in panel.btn_autosave_toggle.cget("text")

        # Toggle to ON
        panel._toggle_auto_save()
        assert panel.auto_save_var.get() is True
        assert fake_prefs["mobile_autosave_on_stop"] is True
        assert "ON" in panel.btn_autosave_toggle.cget("text")
        assert "ON" in panel.btn_active_autosave_toggle.cget("text")

        # Toggle back to OFF
        panel._toggle_auto_save()
        assert panel.auto_save_var.get() is False
        assert fake_prefs["mobile_autosave_on_stop"] is False
        assert "OFF" in panel.btn_autosave_toggle.cget("text")
    finally:
        root.destroy()


def test_mobile_dialog_end_session_autosave_and_prompt(mock_app_state, monkeypatch):
    """Test MobileDialog._end_session auto-save vs confirmation prompt branches."""
    import config
    from ui.mobile_dialog import MobileDialog
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    try:
        class DummyApp:
            def __init__(self):
                self.output_path = "dummy_collection.xlsx"

        class DummyParentUI:
            def __init__(self, root):
                self.root = root
                self.app = DummyApp()
                self.saved_actions = []

            def save_session(self, action, on_complete=None):
                self.saved_actions.append(action)

            def load_object(self, oid):
                pass

        parent_ui = DummyParentUI(root)

        # Case 1: dirty is False -> no save, no prompt
        mock_app_state.dirty = False
        dlg = MobileDialog(parent_ui, root, mock_app_state)
        dlg._end_session()
        assert len(parent_ui.saved_actions) == 0

        # Case 2: dirty is True, auto-save is ON -> silent save triggered
        mock_app_state.dirty = True
        monkeypatch.setattr(config, "load_prefs", lambda: {"mobile_autosave_on_stop": True})
        dlg2 = MobileDialog(parent_ui, root, mock_app_state)
        dlg2.panel.auto_save_var.set(True)
        dlg2._end_session()
        assert "MOBILE_SESSION_END" in parent_ui.saved_actions

        # Case 3: dirty is True, auto-save is OFF -> prompt shown (user says Yes)
        parent_ui.saved_actions.clear()
        mock_app_state.dirty = True
        monkeypatch.setattr(config, "load_prefs", lambda: {"mobile_autosave_on_stop": False})
        monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: True)
        dlg3 = MobileDialog(parent_ui, root, mock_app_state)
        dlg3.panel.auto_save_var.set(False)
        dlg3._end_session()
        assert "MOBILE_SESSION_END" in parent_ui.saved_actions

        # Case 4: dirty is True, auto-save is OFF -> prompt shown (user says No)
        parent_ui.saved_actions.clear()
        mock_app_state.dirty = True
        monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: False)
        dlg4 = MobileDialog(parent_ui, root, mock_app_state)
        dlg4.panel.auto_save_var.set(False)
        dlg4._end_session()
        assert len(parent_ui.saved_actions) == 0
    finally:
        root.destroy()

