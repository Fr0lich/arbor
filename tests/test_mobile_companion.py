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
    assert log_entry["Action"] == "MOBILE_EDIT"
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
    loaded_reg, loaded_obs, loaded_photo, loaded_log, loaded_unval = ExcelRepository.load_excel(
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


def test_mixed_int64_and_str_index_matching(tmp_path):
    """Verify that integer vs string index dtypes across df_reg and df_obs are handled seamlessly."""
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
    }, index=pd.Index([1001, 1002], name="ObjectID"))  # int64 index

    app.df_obs = pd.DataFrame({
        "Reviewed": [True, False],
        "Cabinet": ["Cab 1", "Cab 2"]
    }, index=pd.Index(["1001", "1002"], name="ObjectID"))  # str index

    server = MobileServer(app, port=5093)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    # 1. Status filter matching with mismatched index dtypes
    res_rev = client.get('/api/objects?status=reviewed', headers=headers)
    assert res_rev.status_code == 200
    assert res_rev.json["total_matching"] == 1
    assert res_rev.json["objects"][0]["id"] == "1001"

    # 2. Detail lookup with string ID
    res_det = client.get('/api/object/1001', headers=headers)
    assert res_det.status_code == 200
    assert res_det.json["scientific_name"] == "Pinus sylvestris"

    # 3. Update single object with string ID
    res_upd = client.post('/api/update', headers=headers, json={
        "id": "1001",
        "reviewed": True,
        "observation": {"Cabinet": "Cab 99"}
    })
    assert res_upd.status_code == 200
    assert app.df_obs.at["1001", "Cabinet"] == "Cab 99"

    # 4. Batch update with string IDs
    res_batch = client.post('/api/batch_update', headers=headers, json={
        "updates": [
            {"id": "1002", "reviewed": True, "observation": {"Cabinet": "Cab 88"}}
        ]
    })
    assert res_batch.status_code == 200
    assert res_batch.json["updated_count"] == 1
    assert app.df_obs.at["1002", "Cabinet"] == "Cab 88"


def test_sse_headers_and_initial_connect_handshake(mock_app_state):
    """Verify SSE endpoint returns anti-buffering headers and an immediate connected event."""
    server = MobileServer(mock_app_state, port=5092)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    response = client.get('/api/events', headers=headers)
    assert response.status_code == 200
    assert response.headers.get("Content-Type") == "text/event-stream; charset=utf-8"
    assert "no-cache" in response.headers.get("Cache-Control", "")
    assert response.headers.get("X-Accel-Buffering") == "no"
    assert response.headers.get("Connection") == "keep-alive"

    # Read the first event yielded by the generator
    first_line = next(response.iter_encoded())
    decoded = first_line.decode('utf-8')
    assert "data: " in decoded
    parsed = json.loads(decoded.replace("data: ", "").strip())
    assert parsed["type"] == "connected"


def test_status_flags_and_six_tier_badge_parity():
    """Verify all 6 badge status states, specific problem history isolation, facets, and endpoint parity."""
    from backend.mobile_server import is_unknown, compute_status_flags, get_history_set, get_problem_to_field_map, get_historical_cache

    # 1. Test is_unknown helper
    assert is_unknown("ukjent") is True
    assert is_unknown("Unknown") is True
    assert is_unknown("?") is True
    assert is_unknown("-") is True
    assert is_unknown("nan") is True
    assert is_unknown("") is False
    assert is_unknown(None) is False
    assert is_unknown("Pinus") is False

    # 2. Build test objects representing each priority tier & isolation rules
    app = AppState()
    app.config = {
        "ui_sections": {
            "registration": [{"name": "Genus"}, {"name": "Species"}, {"name": "Author"}],
            "location": [{"name": "Cabinet"}],
            "problems": [
                {"name": "MissingLabel", "maps_to": "Genus"},
                {"name": "Species_Problem", "maps_to": "Species"}
            ]
        }
    }

    # Specimens:
    # 1: OK (Reviewed = True)
    # 2: ERR+HIS (MissingLabel = True -> maps to Genus, Historical DB has Genus)
    # 3: ERR (MissingLabel = True, Not in Historical DB)
    # 4: CFCT (No flags, Genus = '?' is unknown, Historical DB has Genus)
    # 5: UKN (No flags, Genus = '?' is unknown, Historical DB has no Genus)
    # 6: UNREV (Clean default unreviewed)
    # 7: ERR (Species_Problem = True -> maps to Species, Historical DB has Genus but NO Species)
    # 8: ERR+HIS (Species_Problem = True -> maps to Species, Historical DB HAS Species)
    # 9: REV+ERR (Reviewed = True and MissingLabel = True)
    app.df_reg = pd.DataFrame({
        "Genus": ["Pinus", "Betula", "Quercus", "?", "?", "Fagus", "Acer", "Ulmus", "Fraxinus"],
        "Species": ["sylvestris", "pendula", "robur", "alba", "incana", "sylvatica", "platanoides", "glabra", "excelsior"],
        "Author": ["L.", "Roth", "L.", "L.", "L.", "L.", "L.", "Huds.", "L."],
        "Cabinet": ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"]
    }, index=pd.Index(["1", "2", "3", "4", "5", "6", "7", "8", "9"], name="ObjectID"))

    app.df_obs = pd.DataFrame({
        "Reviewed": [True, False, False, False, False, False, False, False, True],
        "MissingLabel": [False, True, True, False, False, False, False, False, True],
        "Species_Problem": [False, False, False, False, False, False, True, True, False],
        "Cabinet": ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"]
    }, index=pd.Index(["1", "2", "3", "4", "5", "6", "7", "8", "9"], name="ObjectID"))

    # Historical DBs:
    # Obj 2: Has Genus = 'Betula' (resolves MissingLabel)
    # Obj 4: Has Genus = 'Salix' (resolves unknown Genus)
    # Obj 7: Has Genus = 'Acer' (does NOT resolve Species_Problem, Species is empty)
    # Obj 8: Has Species = 'glabra' (resolves Species_Problem)
    hist_df = pd.DataFrame({
        "Genus": ["Betula", "Salix", "Acer", "Ulmus"],
        "Species": ["", "", "", "glabra"]
    }, index=pd.Index(["2", "4", "7", "8"], name="ObjectID"))
    app.historical_dbs = [{"name": "HistDB1", "reg_by_id": hist_df}]

    server = MobileServer(app, port=5091)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    # Verify get_history_set & get_historical_cache
    presence_set, fields_by_oid = get_historical_cache(app)
    assert "2" in presence_set
    assert "4" in presence_set
    assert "7" in presence_set
    assert "8" in presence_set
    assert "1" not in presence_set
    assert fields_by_oid["7"] == {"Genus"}
    assert fields_by_oid["8"] == {"Genus", "Species"}

    # 3. GET /api/objects - Test full list & facets
    res = client.get('/api/objects', headers=headers)
    assert res.status_code == 200
    data = res.json
    assert data["total_matching"] == 9

    # Verify serialized object flags
    by_id = {o["id"]: o for o in data["objects"]}
    
    # Obj 1: OK
    assert by_id["1"]["review_status"] == "reviewed"
    assert by_id["1"]["has_flags"] is False
    assert by_id["1"]["has_history"] is False
    assert by_id["1"]["problems_have_history"] is False
    assert by_id["1"]["has_unknown"] is False

    # Obj 9: REV+ERR
    assert by_id["9"]["review_status"] == "reviewed"
    assert by_id["9"]["has_flags"] is True

    # Obj 2: ERR+HIS (MissingLabel has historical Genus)
    assert by_id["2"]["review_status"] == "pending"
    assert by_id["2"]["has_flags"] is True
    assert by_id["2"]["has_history"] is True
    assert by_id["2"]["problems_have_history"] is True

    # Obj 3: ERR (MissingLabel but no history at all)
    assert by_id["3"]["review_status"] == "pending"
    assert by_id["3"]["has_flags"] is True
    assert by_id["3"]["has_history"] is False
    assert by_id["3"]["problems_have_history"] is False

    # Obj 7: ERR (Species_Problem is active, object exists in History, but History only has Genus, NOT Species)
    assert by_id["7"]["review_status"] == "pending"
    assert by_id["7"]["has_flags"] is True
    assert by_id["7"]["has_history"] is True
    assert by_id["7"]["problems_have_history"] is False

    # Obj 8: ERR+HIS (Species_Problem is active, and History HAS Species)
    assert by_id["8"]["review_status"] == "pending"
    assert by_id["8"]["has_flags"] is True
    assert by_id["8"]["has_history"] is True
    assert by_id["8"]["problems_have_history"] is True

    # Obj 4: CFCT (Unknown Genus resolved by historical Genus)
    assert by_id["4"]["review_status"] == "pending"
    assert by_id["4"]["has_flags"] is False
    assert by_id["4"]["has_history"] is True
    assert by_id["4"]["problems_have_history"] is True

    # Obj 5: UKN (Unknown Genus with no historical data)
    assert by_id["5"]["review_status"] == "pending"
    assert by_id["5"]["has_flags"] is False
    assert by_id["5"]["has_history"] is False
    assert by_id["5"]["problems_have_history"] is False
    assert by_id["5"]["has_unknown"] is True

    # Obj 6: UNREV
    assert by_id["6"]["review_status"] == "pending"
    assert by_id["6"]["has_flags"] is False
    assert by_id["6"]["has_history"] is False
    assert by_id["6"]["problems_have_history"] is False
    assert by_id["6"]["has_unknown"] is False

    # 4. Test status filter query parameters
    res_reviewed = client.get('/api/objects?status=reviewed', headers=headers)
    assert set(o["id"] for o in res_reviewed.json["objects"]) == {"1", "9"}

    res_flagged = client.get('/api/objects?status=flagged', headers=headers)
    assert set(o["id"] for o in res_flagged.json["objects"]) == {"2", "3", "7", "8", "9"}

    res_unknown = client.get('/api/objects?status=unknown', headers=headers)
    assert set(o["id"] for o in res_unknown.json["objects"]) == {"4", "5"}

    # 5. Test detail endpoint /api/object/<oid>
    detail7 = client.get('/api/object/7', headers=headers).json
    assert detail7["has_flags"] is True
    assert detail7["has_history"] is True
    assert detail7["problems_have_history"] is False
    assert detail7["review_status"] == "pending"

    detail8 = client.get('/api/object/8', headers=headers).json
    assert detail8["has_flags"] is True
    assert detail8["has_history"] is True
    assert detail8["problems_have_history"] is True
    assert detail8["review_status"] == "pending"

    # 6. Test update endpoint /api/update returning recalculations
    upd_res = client.post('/api/update', headers=headers, json={
        "id": "6",
        "observation": {"MissingLabel": True}
    })
    assert upd_res.status_code == 200
    upd_data = upd_res.json
    assert upd_data["success"] is True
    assert upd_data["has_flags"] is True

def test_mobile_undo_redo(mock_app_state):
    server = MobileServer(mock_app_state, port=5103)
    client = server.flask_app.test_client()

    # Authenticate
    client.post('/api/auth', json={"pin": server.pin})
    token = server.session_token
    headers = {"X-Session-Token": token}

    # Verify initial state
    assert mock_app_state.df_reg.at["1024", "Species"] == "sylvestris"

    # 1. Update the record
    upd_payload = {
        "id": "1024",
        "reviewed": True,
        "registration": {"Species": "mugo"},
        "observation": {"Cabinet": "C-14"}
    }
    client.post('/api/update', json=upd_payload, headers=headers)

    assert mock_app_state.df_reg.at["1024", "Species"] == "mugo"
    assert mock_app_state.df_obs.at["1024", "Cabinet"] == "C-14"

    # 2. Check recent_edits endpoint
    recent_res = client.get('/api/recent_edits', headers=headers)
    assert recent_res.status_code == 200
    edits = recent_res.json["edits"]
    assert len(edits) == 1
    assert edits[0]["oid"] == "1024"
    assert "mugo" not in edits[0]["summary"] # Only field names are in summary

    # 3. Call Undo
    undo_res = client.post('/api/undo', json={"oid": "1024"}, headers=headers)
    assert undo_res.status_code == 200

    # Verify rollback in DataFrames
    assert mock_app_state.df_reg.at["1024", "Species"] == "sylvestris"
    assert mock_app_state.df_obs.at["1024", "Cabinet"] == "C-12"

    # Verify recent_edits is cleared
    recent_res_2 = client.get('/api/recent_edits', headers=headers)
    assert len(recent_res_2.json["edits"]) == 0

    # Verify log_records is cleaned
    log_oids = [log.get("ObjectID") for log in mock_app_state._log_records]
    assert "1024" not in log_oids


def test_mobile_back_button_navigation_template():
    """Verify INDEX_TEMPLATE contains the leave confirmation modal, history API integration, and popstate handling."""
    from backend.mobile_server import INDEX_TEMPLATE

    # 1. Leave confirmation modal DOM elements and text
    assert 'id="leaveConfirmModal"' in INDEX_TEMPLATE
    assert "do you want to leave the database? (you might need to resync)" in INDEX_TEMPLATE
    assert "cancelLeaveModal()" in INDEX_TEMPLATE
    assert "confirmLeaveModal()" in INDEX_TEMPLATE

    # 2. History API usage and popstate handler
    assert "history.replaceState" in INDEX_TEMPLATE
    assert "history.pushState" in INDEX_TEMPLATE
    assert "window.addEventListener('popstate'" in INDEX_TEMPLATE
    assert "showListView(false)" in INDEX_TEMPLATE


def test_mobile_action_name_reviewed_when_only_reviewed_changes(mock_app_state):
    server = MobileServer(mock_app_state, port=5104)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    # Only mark reviewed without editing any other fields
    payload = {
        "id": "1024",
        "reviewed": True
    }
    res = client.post('/api/update', json=payload, headers=headers)
    assert res.status_code == 200
    assert res.json["success"] is True

    assert len(mock_app_state._log_records) == 1
    log_entry = mock_app_state._log_records[-1]
    assert log_entry["Action"] == "REVIEWED"
    assert log_entry["ChangedFields"] == "Reviewed"

    # Only mark unreviewed
    payload_unrev = {
        "id": "1024",
        "reviewed": False
    }
    res_unrev = client.post('/api/update', json=payload_unrev, headers=headers)
    assert res_unrev.status_code == 200
    assert res_unrev.json["success"] is True

    log_entry_unrev = mock_app_state._log_records[-1]
    assert log_entry_unrev["Action"] == "NOT_REVIEWED"


def test_mobile_undo_with_integer_index_and_desktop_log_protection():
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
        "Species": ["sylvestris", "pendula"]
    }, index=pd.Index([1001, 1002], name="ObjectID"))  # int64 index

    app.df_obs = pd.DataFrame({
        "Reviewed": [False, False],
        "Cabinet": ["Cab 1", "Cab 2"]
    }, index=pd.Index([1001, 1002], name="ObjectID"))

    # Simulate existing desktop EDIT log entry for 1001
    app._log_records = [
        {
            "Timestamp": "2026-09-01T12:00:00",
            "Action": "EDIT",
            "ObjectID": "1001",
            "ChangedFields": "Genus",
            "ChangedValues": 'Genus: "Abies" -> "Pinus"',
            "ProblemsChanged": "",
            "ProblemsChangedValues": "",
            "LocationChanged": "",
            "LocationChangedValues": "",
            "User": "Desktop-User"
        }
    ]

    server = MobileServer(app, port=5105)
    client = server.flask_app.test_client()
    headers = {"X-Session-Token": server.session_token}

    # 1. Perform mobile edit using string ID "1001"
    res_upd = client.post('/api/update', headers=headers, json={
        "id": "1001",
        "registration": {"Species": "mugo"}
    })
    assert res_upd.status_code == 200
    assert app.df_reg.at[1001, "Species"] == "mugo"

    # Check that undo_stacks uses resolved int key 1001
    assert 1001 in app.undo_stacks
    assert len(app._log_records) == 2
    assert app._log_records[-1]["Action"] == "MOBILE_EDIT"

    # 2. Perform mobile undo using string ID "1001"
    res_undo = client.post('/api/undo', headers=headers, json={"oid": "1001"})
    assert res_undo.status_code == 200
    assert res_undo.json["success"] is True

    # Check that data was reverted
    assert app.df_reg.at[1001, "Species"] == "sylvestris"

    # Check that desktop EDIT log entry was preserved and only mobile log was popped
    assert len(app._log_records) == 1
    assert app._log_records[0]["Action"] == "EDIT"
    assert app._log_records[0]["User"] == "Desktop-User"


def test_historical_value_dirty_tracking_in_template():
    from backend.mobile_server import INDEX_TEMPLATE

    # Verify applyHistoricalValue marks field and problem dirty
    assert "function applyHistoricalValue(field, value)" in INDEX_TEMPLATE
    assert "markDirty(field);" in INDEX_TEMPLATE
    assert "markDirty(exactProb);" in INDEX_TEMPLATE

    # Verify undoHistoricalValue marks field dirty and restores problem flag
    assert "function undoHistoricalValue(field, originalValue)" in INDEX_TEMPLATE
    assert "currentRecord.observation[exactProb] = true;" in INDEX_TEMPLATE
    assert "document.getElementById(`prob_${exactProb}`)" in INDEX_TEMPLATE


def test_mobile_ui_ux_improvements():
    from backend.mobile_server import INDEX_TEMPLATE

    # 1. Toast position at bottom-24
    assert 'id="toast"' in INDEX_TEMPLATE
    assert 'fixed bottom-24 left-4 right-4' in INDEX_TEMPLATE
    assert 'function showToast' in INDEX_TEMPLATE

    # 2. Persistent search box in top header
    assert 'id="searchBox"' in INDEX_TEMPLATE
    assert 'id="searchClearBtn"' in INDEX_TEMPLATE
    assert 'id="btnFilterModalTrigger"' in INDEX_TEMPLATE

    # 3. Offline syncing feedback in flushQueuedMutations
    assert 'function flushQueuedMutations()' in INDEX_TEMPLATE
    assert 'Syncing queued edits' in INDEX_TEMPLATE or 'Syncing' in INDEX_TEMPLATE
    assert 'animate-spin' in INDEX_TEMPLATE

    # 4. Advanced filters clear button and active indicator
    assert 'id="filterActiveBadge"' in INDEX_TEMPLATE
    assert 'function clearAdvancedFilters()' in INDEX_TEMPLATE
    assert 'function updateFilterIndicator()' in INDEX_TEMPLATE
    assert 'Clear All' in INDEX_TEMPLATE

    # 5. Prominent Walk Mode active state
    assert 'function toggleWakeLock()' in INDEX_TEMPLATE
    assert 'bg-amber-400' in INDEX_TEMPLATE


def test_unvalidated_sources_sync_and_endpoints(mock_app_state):
    import pandas as pd
    mock_app_state.df_unvalidated = pd.DataFrame([
        {"ObjectID": "1024", "Field_Name": "Species", "Unvalidated_Comment": "Old label faded"},
        {"ObjectID": "1024", "Field_Name": "Family", "Unvalidated_Comment": "Needs confirmation"}
    ])

    server = MobileServer(mock_app_state, port=5104)
    client = server.flask_app.test_client()

    client.post('/api/auth', json={"pin": server.pin})
    token = server.session_token
    headers = {"X-Session-Token": token}

    # 1. /api/objects should report has_unvalidated=True for 1024 and False for 1025
    res = client.get('/api/objects', headers=headers)
    assert res.status_code == 200
    objs = res.json["objects"]
    obj_1024 = next(o for o in objs if o["id"] == "1024")
    obj_1025 = next(o for o in objs if o["id"] == "1025")
    assert obj_1024["has_unvalidated"] is True
    assert obj_1025["has_unvalidated"] is False

    # 2. /api/object/1024 should return unvalidated_sources list
    res_det = client.get('/api/object/1024', headers=headers)
    assert res_det.status_code == 200
    sources = res_det.json["unvalidated_sources"]
    assert len(sources) == 2
    assert {"field": "Species", "comment": "Old label faded"} in sources
    assert {"field": "Family", "comment": "Needs confirmation"} in sources

    # 3. Update via /api/update with modified unvalidated sources
    upd_payload = {
        "id": "1024",
        "unvalidated_sources": [
            {"field": "Genus", "comment": "Handwritten note"}
        ]
    }
    upd_res = client.post('/api/update', json=upd_payload, headers=headers)
    assert upd_res.status_code == 200

    # Verify mock_app_state.df_unvalidated updated
    df_u = mock_app_state.df_unvalidated
    matches = df_u[df_u["ObjectID"] == "1024"]
    assert len(matches) == 1
    assert matches.iloc[0]["Field_Name"] == "Genus"
    assert matches.iloc[0]["Unvalidated_Comment"] == "Handwritten note"

    # 4. Batch update unvalidated sources for another object
    batch_payload = {
        "updates": [
            {
                "id": "1025",
                "unvalidated_sources": [
                    {"field": "Author", "comment": "Illegible"}
                ]
            }
        ]
    }
    batch_res = client.post('/api/batch_update', json=batch_payload, headers=headers)
    assert batch_res.status_code == 200

    matches_1025 = mock_app_state.df_unvalidated[mock_app_state.df_unvalidated["ObjectID"] == "1025"]
    assert len(matches_1025) == 1
    assert matches_1025.iloc[0]["Field_Name"] == "Author"
    assert matches_1025.iloc[0]["Unvalidated_Comment"] == "Illegible"


def test_index_route_rendering_and_cache_headers(mock_app_state):
    server = MobileServer(mock_app_state, port=5099)
    client = server.flask_app.test_client()

    # Hit GET / with token param
    res = client.get(f'/?token={server.session_token}')
    assert res.status_code == 200
    assert "text/html" in res.content_type
    assert "Arbor Companion" in res.get_data(as_text=True)
    assert res.headers.get("Cache-Control") == "no-cache, no-store, must-revalidate, max-age=0"
    assert res.headers.get("Pragma") == "no-cache"



