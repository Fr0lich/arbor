import pytest
import pandas as pd
import json
import os
import threading
from models import AppState
from backend.mobile_server import MobileServer
from repository import ExcelRepository
import config


@pytest.fixture
def mock_app_state(tmp_path):
    app = AppState()
    app.config_name = "Botanical Herbarium"
    app.config = {
        "sheets": {"reg": "Registration", "obs": "Observation", "photo": "Photo", "log": "Log"},
        "ui_sections": {
            "registration": [
                {"name": "Genus"}, {"name": "Species"}, {"name": "Family"}, {"name": "Author"},
                {"name": "UID"}, {"name": "ProblemDescription"}
            ],
            "problems": [{"name": "MissingLabel", "label": "Missing Label", "maps_to": "ProblemDescription"}],
            "reg_groups": [{"name": "Taxonomy", "fields": ["Genus", "Species", "Family", "Author"]}],
            "location": [{"name": "Building"}, {"name": "Room"}, {"name": "Cabinet"}, {"name": "Shelf"}]
        },
        "image_url_pattern": "https://www.unimus.no/photos/image/jpeg/O-V-OE-{id}.jpg"
    }

    reg_data = {
        "ObjectID": ["1024", "1025", "1026"],
        "Genus": ["Pinus", "Betula", "Quercus"],
        "Species": ["sylvestris", "pendula", "robur"],
        "Family": ["Pinaceae", "Betulaceae", "Fagaceae"],
        "Author": ["L.", "Roth", "L."],
        "UID": ["u1024", "u1025", "u1026"],
        "ProblemDescription": ["", "", ""]
    }
    df_reg = pd.DataFrame(reg_data).set_index("ObjectID")

    obs_data = {
        "ObjectID": ["1024", "1025", "1026"],
        "Room": ["Room 304", "Room 304", "Room 305"],
        "Cabinet": ["C-12", "C-12", "C-15"],
        "Shelf": ["Shelf 3", "Shelf 4", "Shelf 1"],
        "Notes": ["Initial inspection note", "", ""],
        "Reviewed": [False, True, False],
        "ReviewedAt": ["", "2026-08-20T10:00:00", ""],
        "MissingLabel": [False, False, True]
    }
    df_obs = pd.DataFrame(obs_data).set_index("ObjectID")

    df_photo = pd.DataFrame({"ObjectID": ["1024", "1025", "1026"], "Images": ["1024.jpg", "", ""]}).set_index("ObjectID")
    df_log = pd.DataFrame()

    app.df_reg = df_reg
    app.df_obs = df_obs
    app.df_photo = df_photo
    app.df_log = df_log
    app.excel_path = str(tmp_path / "test_db.xlsx")
    app.output_path = app.excel_path
    app._log_records = []
    app.dirty = False

    return app


def test_mobile_server_api_flow(mock_app_state):
    server = MobileServer(mock_app_state, port=5099)
    client = server.flask_app.test_client()

    # 1. Unauthenticated request should return 401
    res = client.get('/api/status')
    assert res.status_code == 401

    # 2. Authenticate with PIN
    auth_res = client.post('/api/auth', json={"pin": server.pin})
    assert auth_res.status_code == 200
    token = auth_res.json["token"]
    assert token == server.session_token

    headers = {"X-Session-Token": token}

    # 3. GET /api/status
    status_res = client.get('/api/status', headers=headers)
    assert status_res.status_code == 200
    data = status_res.json
    assert data["status"] == "ok"
    assert data["total_objects"] == 3
    assert data["reviewed_count"] == 1
    assert data["pending_count"] == 2

    # 4. GET /api/objects with search
    obj_res = client.get('/api/objects?q=Pinus', headers=headers)
    assert obj_res.status_code == 200
    objs = obj_res.json["objects"]
    assert len(objs) == 1
    assert objs[0]["id"] == "1024"
    assert objs[0]["genus"] == "Pinus"

    # 5. GET /api/object/1024
    detail_res = client.get('/api/object/1024', headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json
    assert detail["id"] == "1024"
    assert detail["registration"]["Genus"] == "Pinus"
    assert detail["observation"]["Cabinet"] == "C-12"
    assert "https://www.unimus.no/photos/image/jpeg/O-V-OE-1024.jpg" in detail["images"]["online_urls"]

    # 6. POST /api/update - Modify fields & mark reviewed
    update_payload = {
        "id": "1024",
        "reviewed": True,
        "registration": {
            "Genus": "Pinus",
            "Species": "mugo"
        },
        "observation": {
            "Cabinet": "C-14",
            "Notes": "Verified in herbarium physical inspection"
        }
    }
    update_res = client.post('/api/update', json=update_payload, headers=headers)
    assert update_res.status_code == 200
    assert update_res.json["success"] is True

    # 7. Verify Data Integrity in AppState DataFrames
    assert mock_app_state.dirty is True
    assert mock_app_state.df_reg.at["1024", "Species"] == "mugo"
    assert mock_app_state.df_obs.at["1024", "Cabinet"] == "C-14"
    assert bool(mock_app_state.df_obs.at["1024", "Reviewed"]) is True

    # 8. Verify Undo Stack
    assert "1024" in mock_app_state.undo_stacks
    assert len(mock_app_state.undo_stacks["1024"]) == 1
    prev_snapshot = mock_app_state.undo_stacks["1024"][0]
    assert prev_snapshot["reg"]["Species"] == "sylvestris"
    assert prev_snapshot["obs"]["Cabinet"] == "C-12"

    # 9. Verify Audit Logging in _log_records and df_log
    assert len(mock_app_state._log_records) == 1
    log_entry = mock_app_state._log_records[0]
    assert log_entry["ObjectID"] == "1024"
    assert log_entry["Action"] == "REVIEWED"
    assert "Species" in log_entry["ChangedFields"]
    assert "Cabinet" in log_entry["LocationChanged"]
    assert "sylvestris" in log_entry["ChangedValues"] and "mugo" in log_entry["ChangedValues"]
    assert "C-12" in log_entry["LocationChangedValues"] and "C-14" in log_entry["LocationChangedValues"]

    assert not mock_app_state.df_log.empty
    assert "ObjectID" in mock_app_state.df_log.columns


def test_mobile_excel_roundtrip_persistence(mock_app_state, tmp_path):
    server = MobileServer(mock_app_state, port=5098)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    # Perform mobile edits on #1026
    payload = {
        "id": "1026",
        "reviewed": True,
        "registration": {
            "Genus": "Quercus",
            "Species": "petraea"  # changed from robur
        },
        "observation": {
            "Room": "Vault 2B",
            "Cabinet": "C-99",
            "Shelf": "Top",
            "Notes": "Mobile field inspection verified."
        }
    }
    client.post('/api/update', json=payload, headers=headers)

    # Save to Excel
    from repository import SQLiteRepository
    save_path = str(tmp_path / "exported_database.xlsx")
    SQLiteRepository.export_to_excel(
        sqlite_path=None,
        excel_path=save_path,
        config=mock_app_state.config,
        df_reg=mock_app_state.df_reg,
        df_obs=mock_app_state.df_obs,
        df_log=mock_app_state.df_log,
        df_photo=mock_app_state.df_photo
    )
    assert os.path.exists(save_path)

    # Re-read back from Excel
    loaded_reg, loaded_obs, loaded_photo, loaded_log = ExcelRepository.load_excel(
        save_path,
        mock_app_state.config
    )
    if "ObjectID" in loaded_reg.columns:
        loaded_reg = loaded_reg.set_index("ObjectID")
    if "ObjectID" in loaded_obs.columns:
        loaded_obs = loaded_obs.set_index("ObjectID")

    # Verify #1026 edits persisted
    assert loaded_reg.at["1026", "Species"] == "petraea"
    assert loaded_obs.at["1026", "Room"] == "Vault 2B"
    assert loaded_obs.at["1026", "Cabinet"] == "C-99"
    assert loaded_obs.at["1026", "Shelf"] == "Top"
    assert loaded_obs.at["1026", "Notes"] == "Mobile field inspection verified."
    assert bool(loaded_obs.at["1026", "Reviewed"]) is True

    # Verify Log sheet persisted
    assert not loaded_log.empty
    assert (loaded_log["ObjectID"].astype(str) == "1026").any()


def test_mobile_filtering_and_pagination(mock_app_state):
    server = MobileServer(mock_app_state, port=5097)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    # Test status=pending filter (1024, 1026 are pending, 1025 is reviewed)
    res_pending = client.get('/api/objects?status=pending', headers=headers)
    assert res_pending.status_code == 200
    pending_ids = [o["id"] for o in res_pending.json["objects"]]
    assert "1024" in pending_ids
    assert "1026" in pending_ids
    assert "1025" not in pending_ids

    # Test status=reviewed filter
    res_reviewed = client.get('/api/objects?status=reviewed', headers=headers)
    assert res_reviewed.status_code == 200
    reviewed_ids = [o["id"] for o in res_reviewed.json["objects"]]
    assert "1025" in reviewed_ids
    assert "1024" not in reviewed_ids

    # Test pagination
    res_paged = client.get('/api/objects?limit=1&offset=0', headers=headers)
    assert len(res_paged.json["objects"]) == 1
    assert res_paged.json["total_matching"] == 3


def test_get_local_ip():
    from backend.mobile_server import get_local_ip
    ip = get_local_ip()
    assert isinstance(ip, str)
    assert len(ip.split(".")) == 4


def test_mobile_host_app_lifecycle(mock_app_state):
    import tkinter as tk
    from ui.mobile_host_app import MobileHostApp

    root = tk.Tk()
    root.withdraw()
    try:
        host = MobileHostApp(root=root, app=mock_app_state)
        # Simulate pressing start button
        host.panel._on_start_btn_clicked()
        assert host.server is not None
        assert host.app == mock_app_state
        assert "Connecting" in host.url_var.get()
        assert host.panel.local_url_with_token.startswith("http://")
        if host.autosave_job:
            root.after_cancel(host.autosave_job)
        if host.tunnel:
            host.tunnel.stop()
        if host.server:
            host.server.stop()
    finally:
        root.destroy()


def test_schema_endpoint(mock_app_state):
    server = MobileServer(mock_app_state, port=5096)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    res = client.get('/api/schema', headers=headers)
    assert res.status_code == 200
    data = res.json
    assert data["config_name"] == "Botanical Herbarium"
    assert "ui_sections" in data
    assert "registration" in data["ui_sections"]
    assert "location" in data["ui_sections"]
    assert "problems" in data["ui_sections"]


def test_schema_safe_unconfigured_column_rejection(mock_app_state):
    server = MobileServer(mock_app_state, port=5096)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    # Attempt to send an unconfigured ghost field
    payload = {
        "id": "1024",
        "observation": {
            "CustomGhostField": "ShouldNotBeAdded",
            "Cabinet": "C-99"  # Configured field
        }
    }
    res = client.post('/api/update', json=payload, headers=headers)
    assert res.status_code == 200

    # Ensure configured field was updated
    assert mock_app_state.df_obs.at["1024", "Cabinet"] == "C-99"
    # Ensure unconfigured ghost field was NOT added as a new column to df_obs
    assert "CustomGhostField" not in mock_app_state.df_obs.columns


def test_problem_audit_logging(mock_app_state):
    server = MobileServer(mock_app_state, port=5095)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    payload = {
        "id": "1025",
        "observation": {
            "MissingLabel": True,
            "Shelf": "Shelf 9"
        }
    }
    res = client.post('/api/update', json=payload, headers=headers)
    assert res.status_code == 200

    log_entry = mock_app_state._log_records[-1]
    assert "MissingLabel" in log_entry["ProblemsChanged"]
    assert "Shelf" in log_entry["LocationChanged"]
    assert "Shelf 9" in log_entry["LocationChangedValues"]


def test_mobile_objects_mixed_and_numeric_dtypes(mock_app_state):
    # Set numeric/integer cabinet and problem flags in df_obs and df_reg
    mock_app_state.df_reg["Cabinet"] = [101, 102, 103]  # integers in df_reg
    mock_app_state.df_obs["Cabinet"] = [201, None, 203]  # integers & NaNs in df_obs
    mock_app_state.df_obs["MissingLabel"] = [True, False, False]

    server = MobileServer(mock_app_state, port=5094)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    # Test /api/objects GET request
    res = client.get('/api/objects', headers=headers)
    assert res.status_code == 200
    data = res.json
    assert data["total_matching"] == 3
    assert "cabinets" in data["facets"]
    # 201 should override 101, 102 should be fallback, 203 should override 103
    assert "201" in data["facets"]["cabinets"]
    assert "102" in data["facets"]["cabinets"]
    assert "203" in data["facets"]["cabinets"]

    # Test filtering by cabinet (numeric string)
    res_filt = client.get('/api/objects?cabinet=201', headers=headers)
    assert res_filt.status_code == 200
    assert res_filt.json["total_matching"] == 1
    assert res_filt.json["objects"][0]["id"] == "1024"

    # Test filtering by has_problems
    res_prob = client.get('/api/objects?has_problems=true', headers=headers)
    assert res_prob.status_code == 200
    assert res_prob.json["total_matching"] == 1
    assert res_prob.json["objects"][0]["id"] == "1024"

