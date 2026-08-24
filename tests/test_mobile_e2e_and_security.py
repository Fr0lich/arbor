"""
tests/test_mobile_e2e_and_security.py

Phase 5 Comprehensive End-to-End, Security, and Concurrency Verification Test Suite.
Tests:
- Thread safety under concurrent desktop edits, multi-mobile updates, and autosave snapshots.
- Mobile offline cache queueing and reconnection sync flush.
- Dual image resolution (online CDN priority with local fallback).
- Security fuzzing (path traversal/LFI permutations, token tampering).
- Full E2E lifecycle roundtrip (Mobile Update -> AppState -> Excel/SQLite Export).
"""

import os
import tempfile
import threading
import time
import pandas as pd
import pytest

from models import AppState
from repository import (
    ExcelRepository,
    SQLiteRepository,
    REVIEWED_COLUMN,
    REVIEWED_AT_COLUMN
)
from backend.mobile_server import MobileServerManager, _safe_resolve_local_image
from backend.tunnel import SSHTunnelManager
from ui.main_window import ObjectProgramUI


@pytest.fixture
def populated_app_state():
    """Creates a mock AppState populated with 50 test specimens."""
    app = AppState()
    app.config = {
        "has_images": True,
        "image_url_pattern": "https://www.unimus.no/photos/image/jpeg/O-V-OE-{num:04d}{suffix}.jpg",
        "image_mode": "online",
        "sheets": {
            "reg": "Registration",
            "obs": "Observation",
            "photo": "Photo",
            "log": "Log"
        },
        "ui_sections": {
            "problems": [{"name": "Genus_Problem"}],
            "location": [{"name": "Cabinet"}, {"name": "Drawer"}],
            "registration": [{"name": "Genus"}, {"name": "Species"}, {"name": "Family"}]
        }
    }
    app.config_name = "Linnaean Test Herbarium"
    app.excel_path = "C:/fake/path/linnaean_vault.xlsx"

    reg_rows = []
    obs_rows = []
    photo_rows = []

    for i in range(1, 51):
        oid = f"{1000 + i}"
        reg_rows.append({
            "ObjectID": oid,
            "Genus": "Quercus" if i % 2 == 0 else "Pinus",
            "Species": f"species_{i}",
            "Family": "Fagaceae" if i % 2 == 0 else "Pinaceae",
            "Cabinet": f"0{1 + (i % 5)}",
            "Drawer": f"1{i % 8}",
            "Notes": f"Original registration note {i}"
        })
        obs_rows.append({
            "ObjectID": oid,
            REVIEWED_COLUMN: False,
            REVIEWED_AT_COLUMN: None,
            "Genus_Problem": False,
            "Notes": ""
        })
        photo_rows.append({"ObjectID": oid, "Filename": f"{oid}_sheet.jpg"})

    app.df_reg = pd.DataFrame(reg_rows).set_index("ObjectID")
    app.df_obs = pd.DataFrame(obs_rows).set_index("ObjectID")
    app.df_photo = pd.DataFrame(photo_rows).set_index("ObjectID")
    app.df_log = pd.DataFrame()
    app._log_records = []
    app.undo_stacks = {}
    app.dirty = False
    return app


def test_concurrent_desktop_and_mobile_edits(populated_app_state):
    """Stress-tests thread safety with simultaneous desktop typing, multi-mobile writers,

    and background autosave copy snapshots under app_state.df_lock.
    """
    mgr = MobileServerManager(populated_app_state)
    client = mgr.app.test_client()
    headers = {"X-Session-Token": mgr.session_token}
    errors = []

    def desktop_writer():
        for i in range(1, 31):
            oid = f"{1000 + i}"
            try:
                with populated_app_state.df_lock:
                    if oid in populated_app_state.df_obs.index:
                        populated_app_state.df_obs.at[oid, "Notes"] = f"Desktop curator note on {oid}"
                time.sleep(0.002)
            except Exception as e:
                errors.append(f"Desktop writer error: {e}")

    def mobile_writer_a():
        for i in range(1, 31):
            oid = f"{1000 + i}"
            try:
                resp = client.post("/api/update", json={
                    "id": oid,
                    "reviewed": True
                }, headers=headers)
                if resp.status_code != 200:
                    errors.append(f"Mobile A status: {resp.status_code}")
                time.sleep(0.002)
            except Exception as e:
                errors.append(f"Mobile A error: {e}")

    def mobile_writer_b():
        for i in range(1, 31):
            oid = f"{1000 + i}"
            try:
                resp = client.post("/api/update", json={
                    "id": oid,
                    "observation": {"Genus_Problem": True}
                }, headers=headers)
                if resp.status_code != 200:
                    errors.append(f"Mobile B status: {resp.status_code}")
                time.sleep(0.002)
            except Exception as e:
                errors.append(f"Mobile B error: {e}")

    def autosave_copy_worker():
        for _ in range(40):
            try:
                with populated_app_state.df_lock:
                    _ = populated_app_state.df_obs.copy()
                    _ = populated_app_state.df_reg.copy()
                time.sleep(0.003)
            except Exception as e:
                errors.append(f"Autosave copy error: {e}")

    threads = [
        threading.Thread(target=desktop_writer, name="DesktopWriter"),
        threading.Thread(target=mobile_writer_a, name="MobileA"),
        threading.Thread(target=mobile_writer_b, name="MobileB"),
        threading.Thread(target=autosave_copy_worker, name="AutosaveWorker")
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrency errors occurred: {errors}"

    # Verify data integrity
    with populated_app_state.df_lock:
        for i in range(1, 31):
            oid = f"{1000 + i}"
            # Both mobile review and desktop notes should persist cleanly
            assert bool(populated_app_state.df_obs.at[oid, REVIEWED_COLUMN]) is True
            assert bool(populated_app_state.df_obs.at[oid, "Genus_Problem"]) is True
            assert populated_app_state.df_obs.at[oid, "Notes"] == f"Desktop curator note on {oid}"
        assert populated_app_state.dirty is True


def test_mobile_offline_cache_and_reconnect_sync(populated_app_state):
    """Simulates mobile offline queueing during network dropouts and automated flush on reconnection."""
    mgr = MobileServerManager(populated_app_state)
    client = mgr.app.test_client()
    headers = {"X-Session-Token": mgr.session_token}

    # 1. Simulate 5 edits recorded in mobile localStorage while offline
    offline_queue = [
        {"id": "1001", "reviewed": True, "observation": {"Notes": "Offline edit 1"}},
        {"id": "1002", "reviewed": True, "observation": {"Notes": "Offline edit 2"}},
        {"id": "1003", "reviewed": True, "observation": {"Notes": "Offline edit 3"}},
        {"id": "9999", "reviewed": True, "observation": {"Notes": "Invalid OID edit"}}, # Will fail gracefully
        {"id": "1004", "reviewed": True, "observation": {"Notes": "Offline edit 4"}}
    ]

    # 2. Simulate reconnection flush loop in client SPA
    retained_in_queue = []
    successful_commits = 0

    for item in offline_queue:
        resp = client.post("/api/update", json=item, headers=headers)
        if resp.status_code == 200:
            successful_commits += 1
        else:
            retained_in_queue.append(item)

    assert successful_commits == 4
    assert len(retained_in_queue) == 1
    assert retained_in_queue[0]["id"] == "9999"

    # Verify committed state in AppState
    with populated_app_state.df_lock:
        assert bool(populated_app_state.df_obs.at["1001", REVIEWED_COLUMN]) is True
        assert populated_app_state.df_obs.at["1001", "Notes"] == "Offline edit 1"
        assert bool(populated_app_state.df_obs.at["1004", REVIEWED_COLUMN]) is True
        assert populated_app_state.df_obs.at["1004", "Notes"] == "Offline edit 4"


def test_dual_image_resolution_and_cascading_fallback(populated_app_state):
    """Verifies that online CDN URLs are prioritized by default, and local streaming endpoints

    function correctly as fallbacks.
    """
    tmpdir = tempfile.mkdtemp()
    try:
        populated_app_state.image_folder = tmpdir
        populated_app_state.config["image_folder"] = tmpdir

        # Create dummy local photo for object 1001
        local_photo = os.path.join(tmpdir, "1001_sheet.jpg")
        with open(local_photo, "wb") as f:
            f.write(b"MOCK_JPEG_IMAGE_DATA")

        mgr = MobileServerManager(populated_app_state)
        client = mgr.app.test_client()
        headers = {"X-Session-Token": mgr.session_token}

        # 1. Mode = online: preferred_source must be 'online'
        resp = client.get("/api/object/1001", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        img_info = data["images"]

        assert img_info["preferred_source"] == "online"
        assert len(img_info["online_urls"]) == 4
        assert "https://www.unimus.no/photos/image/jpeg/O-V-OE-1001.jpg" in img_info["online_urls"]
        assert len(img_info["local_endpoints"]) == 1
        assert img_info["local_endpoints"][0] == "/api/image/1001/0"

        # 2. Local image streaming endpoint (with session token)
        img_resp = client.get("/api/image/1001/0", headers=headers)
        assert img_resp.status_code == 200
        assert img_resp.data == b"MOCK_JPEG_IMAGE_DATA"
        img_resp.close()

        # 3. Mode = folder (offline): preferred_source switches to 'local'
        populated_app_state.config["image_mode"] = "folder"
        resp_folder = client.get("/api/object/1001", headers=headers)
        data_folder = resp_folder.get_json()
        assert data_folder["images"]["preferred_source"] == "local"
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_security_lfi_and_auth_tampering(populated_app_state):
    """Fuzzes security defenses against path traversal, LFI, and unauthorized access."""
    tmpdir = tempfile.mkdtemp()
    try:
        populated_app_state.image_folder = tmpdir

        # Create a secret file outside the image directory
        secret_file = os.path.join(tempfile.gettempdir(), "secret_curator_data.txt")
        with open(secret_file, "w") as f:
            f.write("CONFIDENTIAL")

        mgr = MobileServerManager(populated_app_state)
        client = mgr.app.test_client()
        valid_headers = {"X-Session-Token": mgr.session_token}

        # 1. Auth Tampering: Missing and Invalid tokens
        assert client.get("/api/status").status_code == 401
        assert client.get("/api/status", headers={"X-Session-Token": "FORGED_TOKEN"}).status_code == 401
        assert client.post("/api/update", json={"id": "1001"}, headers={"X-Session-Token": ""}).status_code == 401

        # 2. LFI & Path Traversal vectors in df_photo
        malicious_vectors = [
            "../../secret_curator_data.txt",
            "..\\..\\secret_curator_data.txt",
            "%2e%2e%2fsecret_curator_data.txt",
            "/etc/passwd",
            "C:\\Windows\\System32\\cmd.exe",
            "../" * 10 + "windows/win.ini"
        ]

        for vec in malicious_vectors:
            populated_app_state.df_photo.at["1001", "Filename"] = vec
            resolved = _safe_resolve_local_image("1001", 0, populated_app_state)
            assert resolved is None, f"Failed to block traversal vector: {vec}"

            # Authenticated API request must reject out-of-bounds file with 404
            resp = client.get("/api/image/1001/0", headers=valid_headers)
            assert resp.status_code in (403, 404)
            resp.close()
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_e2e_full_lifecycle_roundtrip(populated_app_state):
    """Tests complete E2E lifecycle: Mobile Edit -> Tkinter Sync -> AppState -> SQLite & Excel Export."""
    mgr = MobileServerManager(populated_app_state)
    client = mgr.app.test_client()
    headers = {"X-Session-Token": mgr.session_token}

    # 1. Mobile Review Commit
    payload = {
        "id": "1005",
        "reviewed": True,
        "observation": {
            "Notes": "Verified in tray 12B during mobile walk",
            "Genus_Problem": False
        }
    }
    resp = client.post("/api/update", json=payload, headers=headers)
    assert resp.status_code == 200

    # 2. Simulate Tkinter Main Window event loop draining
    mock_ui = ObjectProgramUI.__new__(ObjectProgramUI)
    mock_ui.app = populated_app_state
    mock_ui.mobile_server_mgr = mgr
    mock_ui._cached_obs_dict = {"1005": {"Reviewed": False, "Notes": ""}}
    mock_ui.reviewed_var = None

    ObjectProgramUI._on_mobile_edit_received(mock_ui)
    assert mock_ui._cached_obs_dict["1005"]["Reviewed"] is True
    assert mock_ui._cached_obs_dict["1005"]["Notes"] == "Verified in tray 12B during mobile walk"

    # 3. Export to Excel and verify roundtrip persistence
    tmpdir = tempfile.mkdtemp()
    try:
        excel_out = os.path.join(tmpdir, "exported_arbor.xlsx")
        sqlite_out = os.path.join(tmpdir, "exported_arbor.db")

        # Save to SQLite
        SQLiteRepository.save_sqlite(
            sqlite_out,
            populated_app_state.df_reg,
            populated_app_state.df_obs,
            populated_app_state.df_photo,
            populated_app_state.df_log
        )
        assert os.path.exists(sqlite_out)

        # Export to Excel
        SQLiteRepository.export_to_excel(
            sqlite_out,
            excel_out,
            populated_app_state.config,
            df_reg=populated_app_state.df_reg,
            df_obs=populated_app_state.df_obs,
            df_log=populated_app_state.df_log,
            df_photo=populated_app_state.df_photo
        )
        assert os.path.exists(excel_out)

        # Load back with ExcelRepository and assert review status
        df_reg_in, df_obs_in, _, _ = ExcelRepository.load_excel(excel_out, populated_app_state.config)
        df_obs_in.set_index("ObjectID", inplace=True)

        assert bool(df_obs_in.at["1005", REVIEWED_COLUMN]) is True
        assert df_obs_in.at["1005", "Notes"] == "Verified in tray 12B during mobile walk"
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
